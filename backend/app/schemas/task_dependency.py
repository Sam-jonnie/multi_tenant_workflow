from pydantic import BaseModel, ConfigDict, computed_field

from app.core.enums import TaskPriority, TaskStatus
from app.core.workflow import DEPENDENCY_SATISFIED_STATUSES
from app.schemas.user import UserBrief


class DependencyAdd(BaseModel):
    depends_on_id: int


class TaskBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    status: TaskStatus
    priority: TaskPriority
    assignee: UserBrief | None


class TaskDependenciesRead(BaseModel):
    depends_on: list[TaskBrief]  # prerequisites of this task
    blocks: list[TaskBrief]  # tasks waiting on this task

    @computed_field
    @property
    def is_blocked(self) -> bool:
        return any(t.status not in DEPENDENCY_SATISFIED_STATUSES for t in self.depends_on)