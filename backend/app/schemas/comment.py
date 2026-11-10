from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.core.enums import SortOrder
from app.schemas.common import PageParams
from app.schemas.user import UserBrief


class CommentCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    body: str = Field(min_length=1, max_length=5000)


class CommentUpdate(CommentCreate):
    pass


class CommentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    task_id: int | None
    author: UserBrief
    body: str
    mentions: list[UserBrief]
    edited_at: datetime | None
    created_at: datetime
    updated_at: datetime

    @computed_field
    @property
    def is_edited(self) -> bool:
        return self.edited_at is not None


class CommentListQuery(PageParams):
    sort_order: SortOrder = SortOrder.ASC  # conversations read oldest to newest