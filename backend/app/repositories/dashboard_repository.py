from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session, joinedload

from app.core.enums import ProjectStatus, TaskPriority, TaskStatus
from app.core.workflow import TERMINAL_TASK_STATUSES
from app.models.organization import OrganizationMember
from app.models.project import Project
from app.models.task import Task
from app.models.user import User


def _today() -> date:
    return datetime.now(UTC).date()


class DashboardRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _scope(
        stmt: Select[Any], org_id: int, owner_id: int | None, assignee_id: int | None
    ) -> Select[Any]:
        """Every task query starts here, so the tenant filter can't be forgotten."""
        stmt = (
            stmt.select_from(Task)
            .join(Project, Project.id == Task.project_id)
            .where(Project.organization_id == org_id)
        )
        if owner_id is not None:
            stmt = stmt.where(Project.owner_id == owner_id)
        if assignee_id is not None:
            stmt = stmt.where(Task.assignee_id == assignee_id)
        return stmt

    # ---------- organization-wide ----------
    def project_counts(self, org_id: int) -> dict[ProjectStatus, int]:
        rows = self.db.execute(
            select(Project.status, func.count())
            .where(Project.organization_id == org_id)
            .group_by(Project.status)
        ).all()
        return {status: count for status, count in rows}

    def user_counts(self, org_id: int) -> tuple[int, int]:
        """Returns (total members, active members) in one query using FILTER."""
        row = self.db.execute(
            select(
                func.count(),
                func.count().filter(
                    OrganizationMember.is_active.is_(True), User.is_active.is_(True)
                ),
            )
            .select_from(OrganizationMember)
            .join(User, User.id == OrganizationMember.user_id)
            .where(OrganizationMember.organization_id == org_id)
        ).one()
        return row[0], row[1]

    # ---------- tasks ----------
    def task_counts_by_status(
        self, org_id: int, *, owner_id: int | None = None, assignee_id: int | None = None
    ) -> dict[TaskStatus, int]:
        stmt = self._scope(select(Task.status, func.count()), org_id, owner_id, assignee_id)
        rows = self.db.execute(stmt.group_by(Task.status)).all()
        return {status: count for status, count in rows}

    def open_task_counts_by_priority(
        self, org_id: int, *, owner_id: int
    ) -> dict[TaskPriority, int]:
        stmt = self._scope(select(Task.priority, func.count()), org_id, owner_id, None).where(
            Task.status.not_in(TERMINAL_TASK_STATUSES)
        )
        rows = self.db.execute(stmt.group_by(Task.priority)).all()
        return {priority: count for priority, count in rows}

    def open_task_counts_by_assignee(
        self, org_id: int, *, owner_id: int
    ) -> list[tuple[str | None, int]]:
        stmt = (
            select(User.full_name, func.count())
            .select_from(Task)
            .join(Project, Project.id == Task.project_id)
            .outerjoin(User, User.id == Task.assignee_id)  # keeps unassigned tasks
            .where(
                Project.organization_id == org_id,
                Project.owner_id == owner_id,
                Task.status.not_in(TERMINAL_TASK_STATUSES),
            )
            .group_by(User.id, User.full_name)
            .order_by(func.count().desc())
        )
        return [(name, count) for name, count in self.db.execute(stmt).all()]

    def count_tasks(
        self,
        *,
        org_id: int,
        owner_id: int | None = None,
        assignee_id: int | None = None,
        open_only: bool = False,
        overdue: bool = False,
        due_on: date | None = None,
    ) -> int:
        stmt = self._scope(select(func.count()), org_id, owner_id, assignee_id)
        if open_only or overdue:
            stmt = stmt.where(Task.status.not_in(TERMINAL_TASK_STATUSES))
        if overdue:
            stmt = stmt.where(Task.due_date < _today())
        if due_on is not None:
            stmt = stmt.where(Task.due_date == due_on)
        return self.db.scalar(stmt) or 0

    # ---------- lists ----------
    def owned_projects(
        self, org_id: int, owner_id: int, limit: int
    ) -> tuple[list[Project], int]:
        base = select(Project).where(
            Project.organization_id == org_id,
            Project.owner_id == owner_id,
            Project.status != ProjectStatus.ARCHIVED,
        )
        total = self.db.scalar(select(func.count()).select_from(base.subquery())) or 0
        items = self.db.scalars(
            base.order_by(Project.due_date.asc().nulls_last(), Project.id.asc()).limit(limit)
        ).all()
        return list(items), total

    def my_open_tasks(self, org_id: int, user_id: int, limit: int) -> list[Task]:
        stmt = (
            select(Task)
            .join(Project, Project.id == Task.project_id)
            .where(
                Project.organization_id == org_id,
                Task.assignee_id == user_id,
                Task.status.not_in(TERMINAL_TASK_STATUSES),
            )
            .options(joinedload(Task.project))
            .order_by(Task.due_date.asc().nulls_last(), Task.id.asc())
            .limit(limit)
        )
        return list(self.db.scalars(stmt).unique().all())

    def recently_completed(self, org_id: int, user_id: int, limit: int) -> list[Task]:
        stmt = (
            select(Task)
            .join(Project, Project.id == Task.project_id)
            .where(
                Project.organization_id == org_id,
                Task.assignee_id == user_id,
                Task.status == TaskStatus.DONE,
            )
            .options(joinedload(Task.project))
            .order_by(Task.completed_at.desc().nulls_last(), Task.id.desc())
            .limit(limit)
        )
        return list(self.db.scalars(stmt).unique().all())