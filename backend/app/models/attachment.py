from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.project import Project
    from app.models.user import User


class Attachment(Base, TimestampMixin):
    __tablename__ = "attachments"
    __table_args__ = (
        CheckConstraint("size_bytes > 0", name="ck_attachment_size_positive"),
        Index("ix_attachments_project_created", "project_id", "created_at"),
        Index("ix_attachments_task_created", "task_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # project_id is ALWAYS set (the tenant anchor); task_id only for task files.
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    task_id: Mapped[int | None] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"))
    uploaded_by_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    filename: Mapped[str] = mapped_column(String(255))  # sanitized name, for display only
    mime_type: Mapped[str] = mapped_column(String(100))  # derived from the bytes
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    storage_path: Mapped[str] = mapped_column(String(500), unique=True)  # relative to upload dir
    checksum_sha256: Mapped[str] = mapped_column(String(64))

    uploaded_by: Mapped["User"] = relationship(foreign_keys=[uploaded_by_id])
    project: Mapped["Project"] = relationship()