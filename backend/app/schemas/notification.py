from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.core.enums import NotificationEntity, NotificationType
from app.schemas.common import PageParams
from app.schemas.user import UserBrief


class NotificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    project_id: int | None
    type: NotificationType
    title: str
    message: str
    entity_type: NotificationEntity
    entity_id: int | None
    actor: UserBrief | None
    payload: dict[str, Any]
    is_read: bool
    read_at: datetime | None
    created_at: datetime


class NotificationListQuery(PageParams):
    is_read: bool | None = None
    type: NotificationType | None = None


class UnreadCount(BaseModel):
    unread: int


class MarkAllReadResult(BaseModel):
    updated: int