from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.workflow import DEPENDENCY_SATISFIED_STATUSES
from app.models.project import Project
from app.models.task import Task
from app.models.task_dependency import TaskDependency


class TaskDependencyRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, task_id: int, depends_on_id: int) -> TaskDependency | None:
        return self.db.scalar(
            select(TaskDependency).where(
                TaskDependency.task_id == task_id,
                TaskDependency.depends_on_id == depends_on_id,
            )
        )

    def add(self, dependency: TaskDependency) -> TaskDependency:
        self.db.add(dependency)
        self.db.flush()
        return dependency

    def delete(self, dependency: TaskDependency) -> None:
        self.db.delete(dependency)

    def prerequisites(self, task_id: int) -> list[Task]:
        """Tasks that must be finished before `task_id` can start."""
        stmt = (
            select(Task)
            .join(TaskDependency, TaskDependency.depends_on_id == Task.id)
            .where(TaskDependency.task_id == task_id)
            .options(joinedload(Task.assignee))
            .order_by(Task.id)
        )
        return list(self.db.scalars(stmt).unique().all())

    def dependents(self, task_id: int) -> list[Task]:
        """Tasks that are waiting for `task_id`."""
        stmt = (
            select(Task)
            .join(TaskDependency, TaskDependency.task_id == Task.id)
            .where(TaskDependency.depends_on_id == task_id)
            .options(joinedload(Task.assignee))
            .order_by(Task.id)
        )
        return list(self.db.scalars(stmt).unique().all())

    def unresolved_prerequisites(self, task_id: int) -> list[Task]:
        stmt = (
            select(Task)
            .join(TaskDependency, TaskDependency.depends_on_id == Task.id)
            .where(
                TaskDependency.task_id == task_id,
                Task.status.not_in(DEPENDENCY_SATISFIED_STATUSES),
            )
            .order_by(Task.id)
        )
        return list(self.db.scalars(stmt).all())

    def edges_for_project(self, project_id: int) -> list[tuple[int, int]]:
        stmt = (
            select(TaskDependency.task_id, TaskDependency.depends_on_id)
            .join(Task, Task.id == TaskDependency.task_id)
            .where(Task.project_id == project_id)
        )
        return list(self.db.execute(stmt).tuples().all())

    def lock_project(self, project_id: int) -> None:
        """Hold a row lock until commit so two requests can't add edges at once."""
        self.db.execute(select(Project.id).where(Project.id == project_id).with_for_update())