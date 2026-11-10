from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Column, DateTime, ForeignKey, Index, Table, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.project import Project
    from app.models.user import User

# Plain association table: a mention has no data of its own beyond "who".
comment_mentions = Table(
    "comment_mentions",
    Base.metadata,
    Column("comment_id", ForeignKey("comments.id", ondelete="CASCADE"), primary_key=True),
    Column("user_id", ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True),
)


class Comment(Base, TimestampMixin):
    __tablename__ = "comments"
    __table_args__ = (
        Index("ix_comments_project_created", "project_id", "created_at"),
        Index("ix_comments_task_created", "task_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # project_id is ALWAYS set (it is the tenant anchor); task_id only for task comments.
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    task_id: Mapped[int | None] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"))
    author_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    body: Mapped[str] = mapped_column(Text)
    edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    author: Mapped["User"] = relationship(foreign_keys=[author_id])
    project: Mapped["Project"] = relationship()
    mentions: Mapped[list["User"]] = relationship(secondary=comment_mentions)