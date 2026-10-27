from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.organization import Organization, OrganizationMember
from app.schemas.common import PageParams


class OrganizationRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, org_id: int) -> Organization | None:
        return self.db.get(Organization, org_id)

    def get_by_slug(self, slug: str) -> Organization | None:
        return self.db.scalar(select(Organization).where(Organization.slug == slug))

    def add(self, org: Organization) -> Organization:
        self.db.add(org)
        self.db.flush()
        return org

    def list_for_user(self, user_id: int, params: PageParams) -> tuple[list[Organization], int]:
        stmt = (
            select(Organization)
            .join(OrganizationMember, OrganizationMember.organization_id == Organization.id)
            .where(
                OrganizationMember.user_id == user_id,
                OrganizationMember.is_active.is_(True),
                Organization.is_active.is_(True),
            )
        )
        return self._paginate(stmt, params)

    def list_all(self, params: PageParams) -> tuple[list[Organization], int]:
        return self._paginate(select(Organization), params)

    def _paginate(self, stmt, params: PageParams) -> tuple[list[Organization], int]:
        total = self.db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        items = self.db.scalars(
            stmt.order_by(Organization.name).offset(params.offset).limit(params.page_size)
        ).all()
        return list(items), total