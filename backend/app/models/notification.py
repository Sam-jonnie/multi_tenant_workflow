from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, Index, String, false, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.db_types import str_enum
from app.core.enums import NotificationEntity, NotificationType

if TYPE_CHECKING:
    from app.models.user import User


class Notification(Base):
    """One row per recipient. Written in the same transaction as the action behind it."""

    __tablename__ = "notifications"
    __table_args__ = (
        # "my notifications in this org, newest first" and "how many unread?"
        Index(
            "ix_notifications_recipient_org_read",
            "recipient_id",
            "organization_id",
            "is_read",
            "created_at",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    recipient_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    type: Mapped[NotificationType] = mapped_column(str_enum(NotificationType))
    title: Mapped[str] = mapped_column(String(200))
    message: Mapped[str] = mapped_column(String(500))
    entity_type: Mapped[NotificationEntity] = mapped_column(str_enum(NotificationEntity))
    entity_id: Mapped[int | None] = mapped_column()  # no FK: the task may be deleted later
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'::jsonb")
    )
    is_read: Mapped[bool] = mapped_column(default=False, server_default=false())
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    actor: Mapped["User | None"] = relationship(foreign_keys=[actor_id])