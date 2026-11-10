from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.context import CommentContext, ProjectContext, TaskContext
from app.core.enums import AuditAction, AuditEntity
from app.core.exceptions import BadRequestError
from app.core.mentions import extract_mentions
from app.core.rules import ensure_project_writable
from app.models.comment import Comment
from app.models.project import Project
from app.models.user import User
from app.repositories.comment_repository import CommentRepository
from app.schemas.comment import CommentCreate, CommentListQuery, CommentUpdate
from app.services.audit_service import AuditService

MAX_MENTIONS = 20


class CommentService:
    def __init__(self, db: Session, audit: AuditService) -> None:
        self.db = db
        self.audit = audit
        self.comments = CommentRepository(db)

    # ---------- create ----------
    def add_to_project(self, pctx: ProjectContext, data: CommentCreate) -> Comment:
        return self._create(pctx, task_id=None, body=data.body)

    def add_to_task(self, tctx: TaskContext, data: CommentCreate) -> Comment:
        return self._create(tctx.project, task_id=tctx.task.id, body=data.body)

    def _create(self, pctx: ProjectContext, task_id: int | None, body: str) -> Comment:
        project = pctx.project
        user = pctx.org.user
        ensure_project_writable(project)

        mentioned = self._resolve_mentions(project, user.id, body)
        comment = Comment(
            project_id=project.id, task_id=task_id, author_id=user.id, body=body
        )
        comment.mentions = mentioned
        self.comments.add(comment)

        self.audit.log(
            AuditAction.COMMENT_ADDED,
            entity_type=AuditEntity.COMMENT,
            entity_id=comment.id,
            user_id=user.id,
            organization_id=project.organization_id,
            metadata={
                "project_id": project.id,
                "task_id": task_id,
                "mentioned_user_ids": [u.id for u in mentioned],
            },
        )
        self.db.commit()
        self.db.refresh(comment)
        return comment  # Day 6: send notifications to `mentioned` here

    # ---------- read ----------
    def list_for_project(
        self, pctx: ProjectContext, query: CommentListQuery
    ) -> tuple[list[Comment], int]:
        return self.comments.list_for_project(pctx.project.id, query)

    def list_for_task(
        self, tctx: TaskContext, query: CommentListQuery
    ) -> tuple[list[Comment], int]:
        return self.comments.list_for_task(tctx.task.id, query)

    # ---------- update / delete (permissions were checked by the dependency) ----------
    def update(self, cctx: CommentContext, data: CommentUpdate) -> Comment:
        comment = cctx.comment
        ensure_project_writable(comment.project)
        if data.body == comment.body:
            return comment

        old_ids = {u.id for u in comment.mentions}
        new_mentions = self._resolve_mentions(comment.project, cctx.user.id, data.body)

        comment.body = data.body
        comment.mentions = new_mentions
        comment.edited_at = datetime.now(UTC)

        self.audit.log(
            AuditAction.COMMENT_UPDATED,
            entity_type=AuditEntity.COMMENT,
            entity_id=comment.id,
            user_id=cctx.user.id,
            organization_id=comment.project.organization_id,
            metadata={
                "project_id": comment.project_id,
                "task_id": comment.task_id,
                "new_mentioned_user_ids": [u.id for u in new_mentions if u.id not in old_ids],
            },
        )
        self.db.commit()
        self.db.refresh(comment)
        return comment  # Day 6: notify only the users in new_mentioned_user_ids

    def delete(self, cctx: CommentContext) -> None:
        comment = cctx.comment
        ensure_project_writable(comment.project)
        self.audit.log(
            AuditAction.COMMENT_DELETED,
            entity_type=AuditEntity.COMMENT,
            entity_id=comment.id,
            user_id=cctx.user.id,
            organization_id=comment.project.organization_id,
            metadata={"project_id": comment.project_id, "task_id": comment.task_id},
        )
        self.comments.delete(comment)
        self.db.commit()

    # ---------- helpers ----------
    def _resolve_mentions(self, project: Project, author_id: int, body: str) -> list[User]:
        usernames = extract_mentions(body)
        if not usernames:
            return []
        if len(usernames) > MAX_MENTIONS:
            raise BadRequestError(
                "TOO_MANY_MENTIONS", f"A comment can mention at most {MAX_MENTIONS} people."
            )
        return self.comments.resolve_mentions(
            project.organization_id, project.id, usernames, exclude_user_id=author_id
        )