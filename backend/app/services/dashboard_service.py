from collections.abc import Mapping
from enum import StrEnum

from sqlalchemy.orm import Session

from app.core.context import OrgContext
from app.core.enums import ProjectStatus, TaskPriority, TaskStatus
from app.core.workflow import TERMINAL_TASK_STATUSES
from app.models.task import Task
from app.repositories.dashboard_repository import DashboardRepository, _today
from app.schemas.dashboard import (
    AdminDashboard,
    CountItem,
    DashboardProject,
    DashboardTask,
    ManagerDashboard,
    MemberDashboard,
)

LIST_LIMIT = 10


def _breakdown[E: StrEnum](members: type[E], counts: Mapping[E, int]) -> list[CountItem]:
    """One entry per enum member, zero-filled, so charts always show every category."""
    return [CountItem(label=m.value, count=counts.get(m, 0)) for m in members]


def _open_total(by_status: Mapping[TaskStatus, int]) -> int:
    return sum(c for status, c in by_status.items() if status not in TERMINAL_TASK_STATUSES)


def _dashboard_task(task: Task) -> DashboardTask:
    return DashboardTask(
        id=task.id,
        title=task.title,
        status=task.status,
        priority=task.priority,
        due_date=task.due_date,
        project_id=task.project_id,
        project_name=task.project.name,
        completed_at=task.completed_at,
    )


class DashboardService:
    def __init__(self, db: Session) -> None:
        self.repo = DashboardRepository(db)

    def admin(self, ctx: OrgContext) -> AdminDashboard:
        org_id = ctx.organization.id
        projects = self.repo.project_counts(org_id)
        tasks = self.repo.task_counts_by_status(org_id)
        total_users, active_users = self.repo.user_counts(org_id)
        return AdminDashboard(
            total_projects=sum(projects.values()),
            active_projects=projects.get(ProjectStatus.ACTIVE, 0),
            completed_projects=projects.get(ProjectStatus.COMPLETED, 0),
            total_users=total_users,
            active_users=active_users,
            total_tasks=sum(tasks.values()),
            overdue_tasks=self.repo.count_tasks(org_id=org_id, overdue=True),
            projects_by_status=_breakdown(ProjectStatus, projects),
            tasks_by_status=_breakdown(TaskStatus, tasks),
        )

    def manager(self, ctx: OrgContext) -> ManagerDashboard:
        org_id, user_id = ctx.organization.id, ctx.user.id
        owned, owned_total = self.repo.owned_projects(org_id, user_id, LIST_LIMIT)
        by_status = self.repo.task_counts_by_status(org_id, owner_id=user_id)
        by_priority = self.repo.open_task_counts_by_priority(org_id, owner_id=user_id)
        by_member = self.repo.open_task_counts_by_assignee(org_id, owner_id=user_id)
        return ManagerDashboard(
            my_projects_count=owned_total,
            my_projects=[
                DashboardProject(id=p.id, name=p.name, status=p.status, due_date=p.due_date)
                for p in owned
            ],
            open_tasks=_open_total(by_status),
            completed_tasks=by_status.get(TaskStatus.DONE, 0),
            overdue_tasks=self.repo.count_tasks(org_id=org_id, owner_id=user_id, overdue=True),
            tasks_by_member=[
                CountItem(label=name or "Unassigned", count=count) for name, count in by_member
            ],
            tasks_by_priority=_breakdown(TaskPriority, by_priority),
        )

    def member(self, ctx: OrgContext) -> MemberDashboard:
        org_id, user_id = ctx.organization.id, ctx.user.id
        by_status = self.repo.task_counts_by_status(org_id, assignee_id=user_id)
        return MemberDashboard(
            my_tasks_count=_open_total(by_status),
            overdue_tasks=self.repo.count_tasks(org_id=org_id, assignee_id=user_id, overdue=True),
            tasks_due_today=self.repo.count_tasks(
                org_id=org_id, assignee_id=user_id, open_only=True, due_on=_today()
            ),
            my_tasks=[_dashboard_task(t) for t in self.repo.my_open_tasks(org_id, user_id, LIST_LIMIT)],
            recently_completed=[
                _dashboard_task(t) for t in self.repo.recently_completed(org_id, user_id, 5)
            ],
            my_tasks_by_status=_breakdown(TaskStatus, by_status),
        )