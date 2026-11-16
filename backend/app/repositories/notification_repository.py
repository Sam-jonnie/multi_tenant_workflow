from collections.abc import Sequence

from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session, joinedload

from app.core.enums import OrgRole
from app.models.notification import Notification
from app.models.organization import OrganizationMember
from app.models.project import ProjectMember
from app.models.user import User
from app.repositories.query_utils import paginate
from app.schemas.notification import NotificationListQuery


class NotificationRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add_all(self, notifications: Sequence[Notification]) -> None:
        self.db.add_all(notifications)
        self.db.flush()  # assigns ids, still inside the caller's transaction

    def get_for_recipient(self, notification_id: int, user_id: int) -> Notification | None:
        return self.db.scalar(
            select(Notification)
            .options(joinedload(Notification.actor))
            .where(Notification.id == notification_id, Notification.recipient_id == user_id)
        )

    def list_for_user(
        self, org_id: int, user_id: int, query: NotificationListQuery
    ) -> tuple[list[Notification], int]:
        stmt = select(Notification).where(
            Notification.organization_id == org_id,  # tenant boundary
            Notification.recipient_id == user_id,
        )
        if query.is_read is not None:
            stmt = stmt.where(Notification.is_read == query.is_read)
        if query.type is not None:
            stmt = stmt.where(Notification.type == query.type)

        return paginate(
            self.db,
            stmt,
            query,
            order_by=[Notification.created_at.desc(), Notification.id.desc()],
            options=[joinedload(Notification.actor)],
        )

    def unread_count(self, org_id: int, user_id: int) -> int:
        return (
            self.db.scalar(
                select(func.count())
                .select_from(Notification)
                .where(
                    Notification.organization_id == org_id,
                    Notification.recipient_id == user_id,
                    Notification.is_read.is_(False),
                )
            )
            or 0
        )

    def mark_all_read(self, org_id: int, user_id: int) -> int:
        """One UPDATE statement for any number of rows."""
        result = self.db.execute(
            update(Notification)
            .where(
                Notification.organization_id == org_id,
                Notification.recipient_id == user_id,
                Notification.is_read.is_(False),
            )
            .values(is_read=True, read_at=func.now())
            .execution_options(synchronize_session=False)
        )
        return result.rowcount  # type: ignore[attr-defined]

    def eligible_recipient_ids(
        self, org_id: int, project_id: int, user_ids: set[int]
    ) -> set[int]:
        """Of these users, who may actually be told about something in this project?"""
        if not user_ids:
            return set()
        stmt = (
            select(User.id)
            .join(OrganizationMember, OrganizationMember.user_id == User.id)
            .where(
                User.id.in_(sorted(user_ids)),
                User.is_active.is_(True),
                OrganizationMember.organization_id == org_id,
                OrganizationMember.is_active.is_(True),
                or_(
                    OrganizationMember.role == OrgRole.ORG_ADMIN,
                    User.id.in_(
                        select(ProjectMember.user_id).where(ProjectMember.project_id == project_id)
                    ),
                ),
            )
        )
        return set(self.db.scalars(stmt).all())