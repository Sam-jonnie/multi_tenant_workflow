from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.context import OrgContext, ProjectContext, TaskContext
from app.core.enums import AuditAction, AuditEntity, OrgRole, TaskPriority, TaskStatus
from app.core.exceptions import BadRequestError, ConflictError, ForbiddenError
from app.core.permissions import has_min_role
from app.core.rules import ensure_project_writable
from app.core.storage import storage
from app.core.workflow import (
    STATUSES_BLOCKED_BY_DEPENDENCIES,
    STATUSES_REQUIRING_ASSIGNEE,
    TASK_TRANSITIONS,
    ensure_transition,
)
from app.models.project import Project
from app.models.task import Task, TaskAssignmentHistory
from app.repositories.attachment_repository import AttachmentRepository
from app.repositories.membership_repository import MembershipRepository
from app.repositories.project_repository import ProjectMemberRepository
from app.repositories.task_dependency_repository import TaskDependencyRepository
from app.repositories.task_repository import TaskAssignmentRepository, TaskRepository
from app.repositories.user_repository import UserRepository
from app.schemas.common import PageParams
from app.schemas.task import TaskCreate, TaskListQuery, TaskMove, TaskUpdate
from app.services.audit_service import AuditService


class TaskService:
    def __init__(self, db: Session, audit: AuditService) -> None:
        self.db = db
        self.audit = audit
        self.tasks = TaskRepository(db)
        self.history = TaskAssignmentRepository(db)
        self.dependencies = TaskDependencyRepository(db)
        self.attachments = AttachmentRepository(db)
        self.users = UserRepository(db)
        self.org_members = MembershipRepository(db)
        self.project_members = ProjectMemberRepository(db)

    # ---------- CRUD ----------
    def create(self, pctx: ProjectContext, data: TaskCreate) -> Task:
        project = pctx.project
        user = pctx.org.user
        ensure_project_writable(project)

        if data.assignee_id is not None:
            if not has_min_role(pctx.org.role, OrgRole.PROJECT_MANAGER):
                raise ForbiddenError("TASK_ASSIGN_DENIED", "Only project managers can assign tasks.")
            self._validate_assignee(project, data.assignee_id)

        task = Task(
            project_id=project.id,
            title=data.title,
            description=data.description,
            priority=data.priority,
            status=data.status,
            due_date=data.due_date,
            estimated_hours=data.estimated_hours,
            reporter_id=user.id,
            assignee_id=data.assignee_id,
            position=self.tasks.max_position(project.id, data.status) + 1,
        )
        self.tasks.add(task)
        self._log(AuditAction.TASK_CREATED, task, project, user.id, title=task.title)
        if data.assignee_id is not None:
            self._record_assignment(task, None, data.assignee_id, user.id)
            self._log(
                AuditAction.TASK_ASSIGNED,
                task,
                project,
                user.id,
                from_user_id=None,
                to_user_id=data.assignee_id,
            )
        self.db.commit()
        self.db.refresh(task)
        return task

    def list_tasks(self, ctx: OrgContext, query: TaskListQuery) -> tuple[list[Task], int]:
        member_user_id = None if ctx.is_admin else ctx.user.id
        return self.tasks.list_for_org(ctx.organization.id, query, member_user_id, ctx.user.id)

    def update(self, tctx: TaskContext, data: TaskUpdate) -> Task:
        task = tctx.task
        ensure_project_writable(task.project)
        changes = data.model_dump(exclude_unset=True)
        for field, value in changes.items():
            setattr(task, field, value)
        if changes:
            self._log(
                AuditAction.TASK_UPDATED,
                task,
                task.project,
                tctx.user.id,
                changed_fields=sorted(changes),
            )
        self.db.commit()
        self.db.refresh(task)
        return task

    def change_priority(self, tctx: TaskContext, priority: TaskPriority) -> Task:
        task = tctx.task
        ensure_project_writable(task.project)
        old_priority = task.priority
        if priority == old_priority:
            return task
        task.priority = priority
        self._log(
            AuditAction.TASK_UPDATED,
            task,
            task.project,
            tctx.user.id,
            changed_fields=["priority"],
            from_priority=old_priority.value,
            to_priority=priority.value,
        )
        self.db.commit()
        self.db.refresh(task)
        return task

    def delete(self, tctx: TaskContext) -> None:
        if not tctx.can_delete:
            raise ForbiddenError(
                "TASK_DELETE_DENIED", "Only a project manager or the reporter can delete a task."
            )
        task = tctx.task
        ensure_project_writable(task.project)

        file_paths = self.attachments.paths_for_task(task.id)  # rows vanish by cascade
        self._log(AuditAction.TASK_DELETED, task, task.project, tctx.user.id, title=task.title)
        self.tasks.delete(task)
        self.db.commit()
        storage.delete_many(file_paths)  # only after the commit succeeded

    # ---------- workflow ----------
    def change_status(self, tctx: TaskContext, new_status: TaskStatus) -> Task:
        task = tctx.task
        ensure_project_writable(task.project)
        old_status = task.status
        ensure_transition(
            TASK_TRANSITIONS,
            old_status,
            new_status,
            code="INVALID_TASK_STATUS_TRANSITION",
            entity="task",
        )
        self._ensure_assignee_present(task, new_status)
        self._ensure_dependencies_satisfied(task, new_status)
        self._apply_status(task, new_status, position=None)
        self._log(
            AuditAction.TASK_STATUS_CHANGED,
            task,
            task.project,
            tctx.user.id,
            from_status=old_status.value,
            to_status=new_status.value,
            via="status",
        )
        self.db.commit()
        self.db.refresh(task)
        return task

    def move(self, tctx: TaskContext, data: TaskMove) -> Task:
        task = tctx.task
        ensure_project_writable(task.project)
        old_status = task.status
        status_changes = data.status != old_status
        if status_changes:  # moving to another column = a status change
            ensure_transition(
                TASK_TRANSITIONS,
                old_status,
                data.status,
                code="INVALID_TASK_STATUS_TRANSITION",
                entity="task",
            )
            self._ensure_assignee_present(task, data.status)
            self._ensure_dependencies_satisfied(task, data.status)
        self._apply_status(task, data.status, position=data.position)
        if status_changes:  # a pure reorder inside a column is not worth an audit row
            self._log(
                AuditAction.TASK_STATUS_CHANGED,
                task,
                task.project,
                tctx.user.id,
                from_status=old_status.value,
                to_status=data.status.value,
                via="move",
            )
        self.db.commit()
        self.db.refresh(task)
        return task

    # ---------- assignment ----------
    def assign(self, tctx: TaskContext, assignee_id: int | None) -> Task:
        task = tctx.task
        ensure_project_writable(task.project)
        old_assignee_id = task.assignee_id
        if assignee_id == old_assignee_id:
            return task  # nothing changed, nothing to record

        if assignee_id is not None:
            self._validate_assignee(task.project, assignee_id)
        elif task.status in STATUSES_REQUIRING_ASSIGNEE:
            raise ConflictError(
                "TASK_ASSIGNEE_REQUIRED",
                f"A task in '{task.status}' must keep an assignee. Reassign it instead.",
            )

        self._record_assignment(task, old_assignee_id, assignee_id, tctx.user.id)
        task.assignee_id = assignee_id
        self._log(
            AuditAction.TASK_ASSIGNED,
            task,
            task.project,
            tctx.user.id,
            from_user_id=old_assignee_id,
            to_user_id=assignee_id,
        )
        self.db.commit()
        self.db.refresh(task)
        return task

    def assignment_history(self, tctx: TaskContext, params: PageParams):
        return self.history.list_for_task(tctx.task.id, params)

    # ---------- helpers ----------
    def _log(
        self,
        action: AuditAction,
        task: Task,
        project: Project,
        user_id: int,
        **metadata: object,
    ) -> None:
        self.audit.log(
            action,
            entity_type=AuditEntity.TASK,
            entity_id=task.id,
            user_id=user_id,
            organization_id=project.organization_id,
            metadata={"project_id": project.id, **metadata},
        )

    @staticmethod
    def _ensure_assignee_present(task: Task, new_status: TaskStatus) -> None:
        if new_status in STATUSES_REQUIRING_ASSIGNEE and task.assignee_id is None:
            raise ConflictError(
                "TASK_ASSIGNEE_REQUIRED",
                f"Assign the task to someone before moving it to '{new_status}'.",
            )

    def _ensure_dependencies_satisfied(self, task: Task, new_status: TaskStatus) -> None:
        if new_status not in STATUSES_BLOCKED_BY_DEPENDENCIES:
            return
        blockers = self.dependencies.unresolved_prerequisites(task.id)
        if blockers:
            raise ConflictError(
                "TASK_BLOCKED_BY_DEPENDENCIES",
                f"Finish the {len(blockers)} prerequisite task(s) "
                f"before moving this task to '{new_status}'.",
                details=[
                    {"task_id": b.id, "title": b.title, "status": b.status.value}
                    for b in blockers
                ],
            )

    def _validate_assignee(self, project: Project, user_id: int) -> None:
        user = self.users.get_by_id(user_id)
        membership = self.org_members.get(project.organization_id, user_id)
        if user is None or membership is None:
            raise BadRequestError(
                "ASSIGNEE_NOT_IN_ORGANIZATION", "Assignee does not belong to this organization."
            )
        if not user.is_active or not membership.is_active:
            raise BadRequestError("ASSIGNEE_INACTIVE", "Inactive users cannot receive tasks.")
        if membership.role == OrgRole.VIEWER:
            raise BadRequestError("ASSIGNEE_IS_VIEWER", "Viewers cannot be assigned tasks.")
        if self.project_members.get(project.id, user_id) is None:
            raise BadRequestError(
                "ASSIGNEE_NOT_PROJECT_MEMBER", "Assignee is not a member of this project."
            )

    def _record_assignment(
        self, task: Task, from_id: int | None, to_id: int | None, changed_by_id: int
    ) -> None:
        self.history.add(
            TaskAssignmentHistory(
                task_id=task.id,
                from_user_id=from_id,
                to_user_id=to_id,
                changed_by_id=changed_by_id,
            )
        )

    def _apply_status(self, task: Task, new_status: TaskStatus, position: int | None) -> None:
        old_status = task.status
        if new_status != old_status:
            if new_status == TaskStatus.DONE:
                task.completed_at = datetime.now(UTC)
            elif old_status == TaskStatus.DONE:
                task.completed_at = None

        if position is None:
            if new_status == old_status:
                return  # same column, no position given: nothing to do
            position = self.tasks.max_position(task.project_id, new_status, task.id) + 1
        else:
            self.tasks.shift_positions(task.project_id, new_status, position, task.id)

        task.status = new_status
        task.position = position