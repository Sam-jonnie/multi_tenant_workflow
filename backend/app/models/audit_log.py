from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.enums import AuditAction, AuditEntity

if TYPE_CHECKING:
    from app.models.user import User


def _values(enum_class: type[StrEnum]) -> list[str]:
    return [member.value for member in enum_class]


class AuditLog(Base):
    """Append-only. No updated_at on purpose, and no code path ever edits a row."""

    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_org_created", "organization_id", "created_at"),
        Index("ix_audit_entity", "entity_type", "entity_id"),
        Index("ix_audit_user_created", "user_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    organization_id: Mapped[int | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="SET NULL")
    )
    action: Mapped[AuditAction] = mapped_column(
        Enum(AuditAction, native_enum=False, length=50, values_callable=_values)
    )
    entity_type: Mapped[AuditEntity] = mapped_column(
        Enum(AuditEntity, native_enum=False, length=50, values_callable=_values)
    )
    entity_id: Mapped[int | None] = mapped_column()
    ip_address: Mapped[str | None] = mapped_column(String(45))  # 45 = longest IPv6 text
    user_agent: Mapped[str | None] = mapped_column(String(255))
    # "metadata" is reserved on declarative classes (Base.metadata), so the Python
    # attribute is `meta` while the DB column keeps the name "metadata".
    meta: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, default=dict, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped["User | None"] = relationship(foreign_keys=[user_id])