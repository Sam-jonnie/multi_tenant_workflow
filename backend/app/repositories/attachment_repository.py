from sqlalchemy import Select, select
from sqlalchemy.orm import Session, joinedload

from app.core.utils import escape_like
from app.models.attachment import Attachment
from app.repositories.query_utils import order_by_clauses, paginate
from app.schemas.attachment import AttachmentListQuery


class AttachmentRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, attachment_id: int) -> Attachment | None:
        return self.db.scalar(
            select(Attachment)
            .options(joinedload(Attachment.uploaded_by), joinedload(Attachment.project))
            .where(Attachment.id == attachment_id)
        )

    def add(self, attachment: Attachment) -> Attachment:
        self.db.add(attachment)
        self.db.flush()
        return attachment

    def delete(self, attachment: Attachment) -> None:
        self.db.delete(attachment)

    def list_for_project(
        self, project_id: int, query: AttachmentListQuery
    ) -> tuple[list[Attachment], int]:
        stmt = select(Attachment).where(
            Attachment.project_id == project_id, Attachment.task_id.is_(None)
        )
        return self._page(stmt, query)

    def list_for_task(
        self, task_id: int, query: AttachmentListQuery
    ) -> tuple[list[Attachment], int]:
        stmt = select(Attachment).where(Attachment.task_id == task_id)
        return self._page(stmt, query)

    def paths_for_project(self, project_id: int) -> list[str]:
        """Includes task files: used to clean the disk when a project is deleted."""
        return list(
            self.db.scalars(
                select(Attachment.storage_path).where(Attachment.project_id == project_id)
            ).all()
        )

    def paths_for_task(self, task_id: int) -> list[str]:
        return list(
            self.db.scalars(
                select(Attachment.storage_path).where(Attachment.task_id == task_id)
            ).all()
        )

    def _page(
        self, stmt: Select[tuple[Attachment]], query: AttachmentListQuery
    ) -> tuple[list[Attachment], int]:
        if query.search:
            stmt = stmt.where(Attachment.filename.ilike(f"%{escape_like(query.search)}%", escape="\\"))
        return paginate(
            self.db,
            stmt,
            query,
            order_by=order_by_clauses(Attachment.created_at, query.sort_order, Attachment.id),
            options=[joinedload(Attachment.uploaded_by)],
        )