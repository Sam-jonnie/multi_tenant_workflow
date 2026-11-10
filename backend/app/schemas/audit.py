from datetime import date, datetime
from typing import TYPE_CHECKING, Any, Self

from pydantic import BaseModel, model_validator

from app.core.enums import AuditAction, AuditEntity, SortOrder
from app.schemas.common import PageParams
from app.schemas.user import UserBrief

if TYPE_CHECKING:
    from app.models.audit_log import AuditLog


class AuditLogRead(BaseModel):
    id: int
    user: UserBrief | None
    organization_id: int | None
    action: AuditAction
    entity_type: AuditEntity
    entity_id: int | None
    ip_address: str | None
    user_agent: str | None
    metadata: dict[str, Any]
    created_at: datetime

    @classmethod
    def from_entry(cls, entry: "AuditLog") -> Self:
        # Mapped by hand: the ORM attribute is `meta`, the API field is `metadata`.
        return cls(
            id=entry.id,
            user=UserBrief.model_validate(entry.user) if entry.user else None,
            organization_id=entry.organization_id,
            action=entry.action,
            entity_type=entry.entity_type,
            entity_id=entry.entity_id,
            ip_address=entry.ip_address,
            user_agent=entry.user_agent,
            metadata=entry.meta,
            created_at=entry.created_at,
        )


class AuditListQuery(PageParams):
    action: AuditAction | None = None
    entity_type: AuditEntity | None = None
    entity_id: int | None = None
    user_id: int | None = None
    created_from: date | None = None
    created_to: date | None = None
    sort_order: SortOrder = SortOrder.DESC

    @model_validator(mode="after")
    def check_range(self) -> Self:
        if self.created_from and self.created_to and self.created_to < self.created_from:
            raise ValueError("created_to must be on or after created_from")
        return self