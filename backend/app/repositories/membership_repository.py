from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, contains_eager

from app.core.enums import OrgRole
from app.models.organization import OrganizationMember
from app.models.user import User
from app.schemas.common import PageParams


class MembershipRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, org_id: int, user_id: int) -> OrganizationMember | None:
        return self.db.scalar(
            select(OrganizationMember).where(
                OrganizationMember.organization_id == org_id,
                OrganizationMember.user_id == user_id,
            )
        )

    def add(self, membership: OrganizationMember) -> OrganizationMember:
        self.db.add(membership)
        self.db.flush()
        return membership

    def delete(self, membership: OrganizationMember) -> None:
        self.db.delete(membership)

    def count_active_admins(self, org_id: int) -> int:
        return (
            self.db.scalar(
                select(func.count())
                .select_from(OrganizationMember)
                .where(
                    OrganizationMember.organization_id == org_id,
                    OrganizationMember.role == OrgRole.ORG_ADMIN,
                    OrganizationMember.is_active.is_(True),
                )
            )
            or 0
        )

    def list_for_org(
        self,
        org_id: int,
        params: PageParams,
        search: str | None = None,
        role: OrgRole | None = None,
        is_active: bool | None = None,
    ) -> tuple[list[OrganizationMember], int]:
        stmt = (
            select(OrganizationMember)
            .join(OrganizationMember.user)
            .where(OrganizationMember.organization_id == org_id)
        )
        if search:
            pattern = f"%{search}%"
            stmt = stmt.where(
                or_(
                    User.full_name.ilike(pattern),
                    User.email.ilike(pattern),
                    User.username.ilike(pattern),
                )
            )
        if role is not None:
            stmt = stmt.where(OrganizationMember.role == role)
        if is_active is not None:
            stmt = stmt.where(OrganizationMember.is_active == is_active)

        total = self.db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        items = self.db.scalars(
            stmt.options(contains_eager(OrganizationMember.user))
            .order_by(User.full_name)
            .offset(params.offset)
            .limit(params.page_size)
        ).all()
        return list(items), total