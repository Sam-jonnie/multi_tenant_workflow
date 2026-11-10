from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session, joinedload

from app.core.enums import TaskSortBy, TaskStatus
from app.core.utils import escape_like
from app.core.workflow import TERMINAL_TASK_STATUSES
from app.models.project import Project, ProjectMember
from app.models.task import Task, TaskAssignmentHistory
from app.repositories.query_utils import order_by_clauses, paginate
from app.schemas.common import PageParams
from app.schemas.task import TaskListQuery

SORT_COLUMNS = {
    TaskSortBy.TITLE: func.lower(Task.title),
    TaskSortBy.PRIORITY: Task.priority,
    TaskSortBy.STATUS: Task.status,
    TaskSortBy.POSITION: Task.position,
    TaskSortBy.DUE_DATE: Task.due_date,
    TaskSortBy.CREATED_AT: Task.created_at,
    TaskSortBy.UPDATED_AT: Task.updated_at,
}


def _start_of_day(day: date) -> datetime:
    return datetime.combine(day, time.min, tzinfo=UTC)


class TaskRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, task_id: int) -> Task | None:
        return self.db.scalar(
            select(Task)
            .options(
                joinedload(Task.assignee), joinedload(Task.reporter), joinedload(Task.project)
            )
            .where(Task.id == task_id)
        )

    def add(self, task: Task) -> Task:
        self.db.add(task)
        self.db.flush()
        return task

    def delete(self, task: Task) -> None:
        self.db.delete(task)

    def max_position(
        self, project_id: int, status: TaskStatus, exclude_task_id: int | None = None
    ) -> int:
        stmt = select(func.max(Task.position)).where(
            Task.project_id == project_id, Task.status == status
        )
        if exclude_task_id is not None:
            stmt = stmt.where(Task.id != exclude_task_id)
        value = self.db.scalar(stmt)
        return -1 if value is None else value

    def shift_positions(
        self, project_id: int, status: TaskStatus, from_position: int, exclude_task_id: int
    ) -> None:
        """Make room: push every task at or after from_position one slot down."""
        self.db.execute(
            update(Task)
            .where(
                Task.project_id == project_id,
                Task.status == status,
                Task.position >= from_position,
                Task.id != exclude_task_id,
            )
            .values(position=Task.position + 1)
            .execution_options(synchronize_session=False)
        )

    def count_open_assigned(self, project_id: int, user_id: int) -> int:
        return (
            self.db.scalar(
                select(func.count())
                .select_from(Task)
                .where(
                    Task.project_id == project_id,
                    Task.assignee_id == user_id,
                    Task.status.not_in(TERMINAL_TASK_STATUSES),
                )
            )
            or 0
        )

    def list_for_org(
        self,
        org_id: int,
        query: TaskListQuery,
        member_user_id: int | None,
        current_user_id: int,
    ) -> tuple[list[Task], int]:
        stmt = (
            select(Task)
            .join(Project, Project.id == Task.project_id)
            .where(Project.organization_id == org_id)  # tenant boundary
        )
        if member_user_id is not None:  # non-admins: only projects they belong to
            stmt = stmt.where(
                Task.project_id.in_(
                    select(ProjectMember.project_id).where(ProjectMember.user_id == member_user_id)
                )
            )
        if query.project_id is not None:
            stmt = stmt.where(Task.project_id == query.project_id)
        if query.status is not None:
            stmt = stmt.where(Task.status == query.status)
        if query.priority is not None:
            stmt = stmt.where(Task.priority == query.priority)
        if query.assignee_id is not None:
            stmt = stmt.where(Task.assignee_id == query.assignee_id)
        if query.mine:
            stmt = stmt.where(Task.assignee_id == current_user_id)
        if query.overdue:
            today = datetime.now(UTC).date()
            stmt = stmt.where(
                Task.due_date < today, Task.status.not_in(TERMINAL_TASK_STATUSES)
            )
        if query.search:
            pattern = f"%{escape_like(query.search)}%"
            stmt = stmt.where(
                or_(
                    Task.title.ilike(pattern, escape="\\"),
                    Task.description.ilike(pattern, escape="\\"),
                )
            )
        if query.due_from:
            stmt = stmt.where(Task.due_date >= query.due_from)
        if query.due_to:
            stmt = stmt.where(Task.due_date <= query.due_to)
        if query.created_from:
            stmt = stmt.where(Task.created_at >= _start_of_day(query.created_from))
        if query.created_to:
            next_day = query.created_to + timedelta(days=1)
            stmt = stmt.where(Task.created_at < _start_of_day(next_day))

        return paginate(
            self.db,
            stmt,
            query,
            order_by=order_by_clauses(SORT_COLUMNS[query.sort_by], query.sort_order, Task.id),
            options=[joinedload(Task.assignee), joinedload(Task.reporter)],
        )


class TaskAssignmentRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, entry: TaskAssignmentHistory) -> TaskAssignmentHistory:
        self.db.add(entry)
        self.db.flush()
        return entry

    def list_for_task(
        self, task_id: int, params: PageParams
    ) -> tuple[list[TaskAssignmentHistory], int]:
        stmt = select(TaskAssignmentHistory).where(TaskAssignmentHistory.task_id == task_id)
        return paginate(
            self.db,
            stmt,
            params,
            order_by=[TaskAssignmentHistory.created_at.desc(), TaskAssignmentHistory.id.desc()],
            options=[
                joinedload(TaskAssignmentHistory.from_user),
                joinedload(TaskAssignmentHistory.to_user),
                joinedload(TaskAssignmentHistory.changed_by),
            ],
        )