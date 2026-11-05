from datetime import date, datetime
from typing import Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    field_validator,
    model_validator,
)

from app.core.enums import ProjectSortBy, ProjectStatus, SortOrder
from app.core.workflow import PROJECT_TRANSITIONS
from app.schemas.common import PageParams
from app.schemas.user import UserBrief


class ProjectCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=2, max_length=150)
    description: str | None = Field(None, max_length=5000)
    start_date: date | None = None
    due_date: date | None = None

    @model_validator(mode="after")
    def check_dates(self) -> Self:
        if self.start_date and self.due_date and self.due_date < self.start_date:
            raise ValueError("due_date must be on or after start_date")
        return self


class ProjectUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str | None = Field(None, min_length=2, max_length=150)
    description: str | None = Field(None, max_length=5000)
    start_date: date | None = None
    due_date: date | None = None
    owner_id: int | None = None

    @field_validator("name", "owner_id")
    @classmethod
    def not_null(cls, value: object) -> object:
        if value is None:
            raise ValueError("This field cannot be null.")
        return value


class ProjectStatusUpdate(BaseModel):
    status: ProjectStatus


class ProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    name: str
    description: str | None
    owner_id: int
    owner: UserBrief
    status: ProjectStatus
    start_date: date | None
    due_date: date | None
    created_at: datetime
    updated_at: datetime

    @computed_field
    @property
    def allowed_status_transitions(self) -> list[ProjectStatus]:
        return list(PROJECT_TRANSITIONS[self.status])


class ProjectListQuery(PageParams):
    model_config = ConfigDict(str_strip_whitespace=True)

    search: str | None = Field(None, max_length=100)
    status: ProjectStatus | None = None
    owner_id: int | None = None
    include_archived: bool = False
    due_from: date | None = None
    due_to: date | None = None
    sort_by: ProjectSortBy = ProjectSortBy.CREATED_AT
    sort_order: SortOrder = SortOrder.DESC

    @model_validator(mode="after")
    def check_range(self) -> Self:
        if self.due_from and self.due_to and self.due_to < self.due_from:
            raise ValueError("due_to must be on or after due_from")
        return self


class ProjectMemberAdd(BaseModel):
    user_id: int


class ProjectMemberRead(BaseModel):
    user_id: int
    email: str
    username: str
    full_name: str
    is_owner: bool
    joined_at: datetime