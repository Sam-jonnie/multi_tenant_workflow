from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.context import TaskContext
from app.core.exceptions import BadRequestError, ConflictError, NotFoundError
from app.core.graph import would_create_cycle
from app.core.rules import ensure_project_writable
from app.core.workflow import DEPENDENCY_SATISFIED_STATUSES, STATUSES_BLOCKED_BY_DEPENDENCIES
from app.models.task import Task
from app.models.task_dependency import TaskDependency
from app.repositories.task_dependency_repository import TaskDependencyRepository
from app.repositories.task_repository import TaskRepository


class TaskDependencyService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.tasks = TaskRepository(db)
        self.dependencies = TaskDependencyRepository(db)

    def list_for_task(self, tctx: TaskContext) -> tuple[list[Task], list[Task]]:
        task_id = tctx.task.id
        return self.dependencies.prerequisites(task_id), self.dependencies.dependents(task_id)

    def add(self, tctx: TaskContext, depends_on_id: int) -> tuple[list[Task], list[Task]]:
        task = tctx.task
        ensure_project_writable(task.project)

        if depends_on_id == task.id:
            raise BadRequestError("SELF_DEPENDENCY", "A task cannot depend on itself.")

        # Same answer for "doesn't exist" and "belongs to another project/tenant".
        prerequisite = self.tasks.get_by_id(depends_on_id)
        if prerequisite is None or prerequisite.project_id != task.project_id:
            raise NotFoundError("TASK_NOT_FOUND_IN_PROJECT", "Task not found in this project.")

        if self.dependencies.get(task.id, prerequisite.id):
            raise ConflictError("DEPENDENCY_EXISTS", "This dependency already exists.")

        self.dependencies.lock_project(task.project_id)
        edges = self.dependencies.edges_for_project(task.project_id)
        if would_create_cycle(edges, task.id, prerequisite.id):
            raise ConflictError(
                "CIRCULAR_DEPENDENCY",
                "This dependency would create a circular chain of tasks.",
            )

        if (
            task.status in STATUSES_BLOCKED_BY_DEPENDENCIES
            and prerequisite.status not in DEPENDENCY_SATISFIED_STATUSES
        ):
            raise ConflictError(
                "DEPENDENCY_VIOLATES_STATE",
                f"The task is already '{task.status}', but the prerequisite is not finished.",
            )

        try:
            self.dependencies.add(TaskDependency(task_id=task.id, depends_on_id=prerequisite.id))
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            raise ConflictError("DEPENDENCY_EXISTS", "This dependency already exists.") from None
        return self.list_for_task(tctx)

    def remove(self, tctx: TaskContext, depends_on_id: int) -> None:
        ensure_project_writable(tctx.task.project)
        dependency = self.dependencies.get(tctx.task.id, depends_on_id)
        if dependency is None:
            raise NotFoundError("DEPENDENCY_NOT_FOUND", "This dependency does not exist.")
        self.dependencies.delete(dependency)
        self.db.commit()