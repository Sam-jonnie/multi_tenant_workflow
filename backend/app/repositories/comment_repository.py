from sqlalchemy import Select, or_, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.core.enums import OrgRole
from app.models.comment import Comment
from app.models.organization import OrganizationMember
from app.models.project import ProjectMember
from app.models.user import User
from app.repositories.query_utils import order_by_clauses, paginate
from app.schemas.comment import CommentListQuery


class CommentRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, comment_id: int) -> Comment | None:
        return self.db.scalar(
            select(Comment)
            .options(
                joinedload(Comment.author),
                joinedload(Comment.project),
                selectinload(Comment.mentions),
            )
            .where(Comment.id == comment_id)
        )

    def add(self, comment: Comment) -> Comment:
        self.db.add(comment)
        self.db.flush()
        return comment

    def delete(self, comment: Comment) -> None:
        self.db.delete(comment)

    def list_for_project(
        self, project_id: int, query: CommentListQuery
    ) -> tuple[list[Comment], int]:
        stmt = select(Comment).where(Comment.project_id == project_id, Comment.task_id.is_(None))
        return self._page(stmt, query)

    def list_for_task(self, task_id: int, query: CommentListQuery) -> tuple[list[Comment], int]:
        stmt = select(Comment).where(Comment.task_id == task_id)
        return self._page(stmt, query)

    def _page(
        self, stmt: Select[tuple[Comment]], query: CommentListQuery
    ) -> tuple[list[Comment], int]:
        return paginate(
            self.db,
            stmt,
            query,
            order_by=order_by_clauses(Comment.created_at, query.sort_order, Comment.id),
            options=[joinedload(Comment.author), selectinload(Comment.mentions)],
        )

    def resolve_mentions(
        self, org_id: int, project_id: int, usernames: set[str], exclude_user_id: int
    ) -> list[User]:
        """Usernames -> users who may actually see this project. Others are dropped."""
        can_see_project = or_(
            OrganizationMember.role == OrgRole.ORG_ADMIN,
            User.id.in_(select(ProjectMember.user_id).where(ProjectMember.project_id == project_id)),
        )
        stmt = (
            select(User)
            .join(OrganizationMember, OrganizationMember.user_id == User.id)
            .where(
                User.username.in_(sorted(usernames)),
                User.id != exclude_user_id,
                User.is_active.is_(True),
                OrganizationMember.organization_id == org_id,
                OrganizationMember.is_active.is_(True),
                can_see_project,
            )
            .order_by(User.username)
        )
        return list(self.db.scalars(stmt).all())