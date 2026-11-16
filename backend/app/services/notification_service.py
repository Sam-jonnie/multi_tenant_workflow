from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.core.context import OrgContext
from app.core.delivery import NotificationEvent, deliver_notifications
from app.core.enums import NotificationEntity, NotificationType, TaskStatus
from app.core.exceptions import ForbiddenError
from app.models.comment import Comment
from app.models.notification import Notification
from app.models.project import Project
from app.models.task import Task
from app.models.user import User
from app.repositories.notification_repository import NotificationRepository
from app.schemas.notification import NotificationListQuery

TITLE_LIMIT = 200
MESSAGE_LIMIT = 500
SNIPPET_LIMIT = 120


def _clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _label(status: TaskStatus) -> str:
    return status.value.replace("_", " ")


def _to_event(notification: Notification) -> NotificationEvent:
    created = notification.created_at or datetime.now(UTC)
    return NotificationEvent(
        id=notification.id,
        recipient_id=notification.recipient_id,
        organization_id=notification.organization_id,
        type=notification.type.value,
        title=notification.title,
        message=notification.message,
        entity_type=notification.entity_type.value,
        entity_id=notification.entity_id,
        project_id=notification.project_id,
        created_at=created.isoformat(),
    )


class NotificationService:
    """Creating a notification adds rows to the CURRENT transaction (so they commit or roll
    back with the action). `dispatch()` pushes them to users and is called AFTER commit."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = NotificationRepository(db)
        self._pending: list[Notification] = []

    # ---------- reading (REST) ----------
    def list_for_user(
        self, ctx: OrgContext, query: NotificationListQuery
    ) -> tuple[list[Notification], int]:
        return self.repo.list_for_user(ctx.organization.id, ctx.user.id, query)

    def unread_count(self, ctx: OrgContext) -> int:
        return self.repo.unread_count(ctx.organization.id, ctx.user.id)

    def mark_read(self, user: User, notification_id: int) -> Notification:
        notification = self.repo.get_for_recipient(notification_id, user.id)
        if notification is None:  # missing and "someone else's" give the same answer
            raise ForbiddenError(
                "NOTIFICATION_ACCESS_DENIED", "You do not have access to this notification."
            )
        if not notification.is_read:
            notification.is_read = True
            notification.read_at = datetime.now(UTC)
            self.db.commit()
        return notification

    def mark_all_read(self, ctx: OrgContext) -> int:
        updated = self.repo.mark_all_read(ctx.organization.id, ctx.user.id)
        self.db.commit()
        return updated

    # ---------- events ----------
    def task_assigned(
        self,
        task: Task,
        project: Project,
        actor: User,
        old_assignee_id: int | None,
        new_assignee_id: int | None,
    ) -> None:
        payload = {
            "task_id": task.id,
            "from_user_id": old_assignee_id,
            "to_user_id": new_assignee_id,
        }
        if new_assignee_id is not None:
            self._create(
                NotificationType.TASK_ASSIGNED,
                [new_assignee_id],
                project=project,
                actor=actor,
                title="Task assigned to you",
                message=f'{actor.full_name} assigned you "{task.title}" in {project.name}.',
                entity_type=NotificationEntity.TASK,
                entity_id=task.id,
                payload=payload,
            )
        if old_assignee_id is not None and old_assignee_id != new_assignee_id:
            what = (
                f'unassigned you from "{task.title}"'
                if new_assignee_id is None
                else f'reassigned "{task.title}" to someone else'
            )
            self._create(
                NotificationType.TASK_REASSIGNED,
                [old_assignee_id],
                project=project,
                actor=actor,
                title="Task reassigned",
                message=f"{actor.full_name} {what}.",
                entity_type=NotificationEntity.TASK,
                entity_id=task.id,
                payload=payload,
            )

    def task_status_changed(
        self,
        task: Task,
        project: Project,
        actor: User,
        old_status: TaskStatus,
        new_status: TaskStatus,
    ) -> None:
        self._create(
            NotificationType.TASK_STATUS_CHANGED,
            [task.reporter_id, task.assignee_id],
            project=project,
            actor=actor,
            title="Task status changed",
            message=(
                f'{actor.full_name} moved "{task.title}" '
                f"from {_label(old_status)} to {_label(new_status)}."
            ),
            entity_type=NotificationEntity.TASK,
            entity_id=task.id,
            payload={
                "task_id": task.id,
                "from_status": old_status.value,
                "to_status": new_status.value,
            },
        )

    def comment_added(
        self,
        comment: Comment,
        project: Project,
        actor: User,
        task: Task | None,
        mentioned: list[User],
    ) -> None:
        mentioned_ids = {user.id for user in mentioned}
        self._notify_mentions(comment, project, actor, task, mentioned_ids)

        # People who were mentioned already get one notification; they don't get a second.
        watchers = (
            [task.reporter_id, task.assignee_id] if task is not None else [project.owner_id]
        )
        self._create(
            NotificationType.COMMENT_ADDED,
            [uid for uid in watchers if uid not in mentioned_ids],
            project=project,
            actor=actor,
            title="New comment",
            message=f"{actor.full_name} commented on {self._where(project, task)}: "
            f"{_clip(comment.body, SNIPPET_LIMIT)}",
            entity_type=NotificationEntity.COMMENT,
            entity_id=comment.id,
            payload=self._comment_payload(comment),
        )

    def mentioned_in_comment(
        self,
        comment: Comment,
        project: Project,
        actor: User,
        task: Task | None,
        users: list[User],
    ) -> None:
        """For an EDITED comment: only the newly mentioned people."""
        self._notify_mentions(comment, project, actor, task, {user.id for user in users})

    def project_member_added(self, project: Project, actor: User, user_id: int) -> None:
        self._create(
            NotificationType.PROJECT_MEMBER_ADDED,
            [user_id],
            project=project,
            actor=actor,
            title="Added to a project",
            message=f'{actor.full_name} added you to the project "{project.name}".',
            entity_type=NotificationEntity.PROJECT,
            entity_id=project.id,
            payload={"project_id": project.id},
        )

    # ---------- delivery ----------
    def dispatch(self) -> None:
        """Call AFTER db.commit(). Only committed notifications are ever pushed."""
        if not self._pending:
            return
        events = [_to_event(n) for n in self._pending]
        self._pending = []
        deliver_notifications(events)

    # ---------- helpers ----------
    def _notify_mentions(
        self,
        comment: Comment,
        project: Project,
        actor: User,
        task: Task | None,
        user_ids: set[int],
    ) -> None:
        self._create(
            NotificationType.USER_MENTIONED,
            user_ids,
            project=project,
            actor=actor,
            title="You were mentioned",
            message=f"{actor.full_name} mentioned you on {self._where(project, task)}: "
            f"{_clip(comment.body, SNIPPET_LIMIT)}",
            entity_type=NotificationEntity.COMMENT,
            entity_id=comment.id,
            payload=self._comment_payload(comment),
        )

    @staticmethod
    def _where(project: Project, task: Task | None) -> str:
        return f'task "{task.title}"' if task is not None else f'project "{project.name}"'

    @staticmethod
    def _comment_payload(comment: Comment) -> dict[str, Any]:
        return {"comment_id": comment.id, "task_id": comment.task_id}

    def _create(
        self,
        notification_type: NotificationType,
        recipient_ids: Iterable[int | None],
        *,
        project: Project,
        actor: User,
        title: str,
        message: str,
        entity_type: NotificationEntity,
        entity_id: int | None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        # a set removes duplicates; nobody is notified about their own action
        wanted = {rid for rid in recipient_ids if rid is not None and rid != actor.id}
        eligible = self.repo.eligible_recipient_ids(project.organization_id, project.id, wanted)
        if not eligible:
            return

        rows = [
            Notification(
                organization_id=project.organization_id,
                recipient_id=recipient_id,
                actor_id=actor.id,
                project_id=project.id,
                type=notification_type,
                title=_clip(title, TITLE_LIMIT),
                message=_clip(message, MESSAGE_LIMIT),
                entity_type=entity_type,
                entity_id=entity_id,
                payload=payload or {},
            )
            for recipient_id in sorted(eligible)
        ]
        self.repo.add_all(rows)
        self._pending.extend(rows)