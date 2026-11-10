from datetime import UTC, date, datetime
from typing import Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    field_validator,
    model_validator,
)

from app.core.enums import TaskPriority, TaskSortBy, TaskStatus, SortOrder
from app.core.workflow import TASK_TRANSITIONS, TERMINAL_TASK_STATUSES
from app.schemas.common import PageParams
from app.schemas.user import UserBrief


class TaskCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(min_length=2, max_length=200)
    description: str | None = Field(None, max_length=10000)
    priority: TaskPriority = TaskPriority.MEDIUM
    status: TaskStatus = TaskStatus.BACKLOG
    due_date: date | None = None
    estimated_hours: float | None = Field(None, ge=0, le=10000)
    assignee_id: int | None = None

    @field_validator("status")
    @classmethod
    def initial_status(cls, value: TaskStatus) -> TaskStatus:
        if value not in (TaskStatus.BACKLOG, TaskStatus.TODO):
            raise ValueError("A new task must start in 'backlog' or 'todo'.")
        return value


class TaskUpdate(BaseModel):
    """Plain fields only. Status and assignee have their own endpoints on purpose."""

    model_config = ConfigDict(str_strip_whitespace=True)

    title: str | None = Field(None, min_length=2, max_length=200)
    description: str | None = Field(None, max_length=10000)
    priority: TaskPriority | None = None
    due_date: date | None = None
    estimated_hours: float | None = Field(None, ge=0, le=10000)
    actual_hours: float | None = Field(None, ge=0, le=10000)

    @field_validator("title", "priority", "actual_hours")
    @classmethod
    def not_null(cls, value: object) -> object:
        if value is None:
            raise ValueError("This field cannot be null.")
        return value


class TaskStatusUpdate(BaseModel):
    status: TaskStatus


class TaskPriorityUpdate(BaseModel):
    priority: TaskPriority


class TaskAssign(BaseModel):
    assignee_id: int | None  # null = unassign


class TaskMove(BaseModel):
    status: TaskStatus
    position: int | None = Field(None, ge=0)  # null = end of the column


class TaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    title: str
    description: str | None
    status: TaskStatus
    priority: TaskPriority
    position: int
    assignee: UserBrief | None
    reporter: UserBrief
    due_date: date | None
    estimated_hours: float | None
    actual_hours: float
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    @computed_field
    @property
    def is_overdue(self) -> bool:
        return (
            self.due_date is not None
            and self.due_date < datetime.now(UTC).date()
            and self.status not in TERMINAL_TASK_STATUSES
        )

    @computed_field
    @property
    def allowed_status_transitions(self) -> list[TaskStatus]:
        return list(TASK_TRANSITIONS[self.status])


class TaskAssignmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    from_user: UserBrief | None
    to_user: UserBrief | None
    changed_by: UserBrief | None
    created_at: datetime


class TaskListQuery(PageParams):
    model_config = ConfigDict(str_strip_whitespace=True)

    project_id: int | None = None
    status: TaskStatus | None = None
    priority: TaskPriority | None = None
    assignee_id: int | None = None
    mine: bool = False
    overdue: bool = False
    search: str | None = Field(None, max_length=100)
    due_from: date | None = None
    due_to: date | None = None
    created_from: date | None = None
    created_to: date | None = None
    sort_by: TaskSortBy = TaskSortBy.CREATED_AT
    sort_order: SortOrder = SortOrder.DESC

    @model_validator(mode="after")
    def check_ranges(self) -> Self:
        if self.due_from and self.due_to and self.due_to < self.due_from:
            raise ValueError("due_to must be on or after due_from")
        if self.created_from and self.created_to and self.created_to < self.created_from:
            raise ValueError("created_to must be on or after created_from")
        return self