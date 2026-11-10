from datetime import UTC, date, datetime

from pydantic import BaseModel, computed_field

from app.core.enums import ProjectStatus, TaskPriority, TaskStatus
from app.core.workflow import TERMINAL_TASK_STATUSES


class CountItem(BaseModel):
    label: str
    count: int


class DashboardProject(BaseModel):
    id: int
    name: str
    status: ProjectStatus
    due_date: date | None


class DashboardTask(BaseModel):
    id: int
    title: str
    status: TaskStatus
    priority: TaskPriority
    due_date: date | None
    project_id: int
    project_name: str
    completed_at: datetime | None

    @computed_field
    @property
    def is_overdue(self) -> bool:
        return (
            self.due_date is not None
            and self.due_date < datetime.now(UTC).date()
            and self.status not in TERMINAL_TASK_STATUSES
        )


class AdminDashboard(BaseModel):
    total_projects: int
    active_projects: int
    completed_projects: int
    total_users: int
    active_users: int
    total_tasks: int
    overdue_tasks: int
    projects_by_status: list[CountItem]
    tasks_by_status: list[CountItem]


class ManagerDashboard(BaseModel):
    my_projects_count: int
    my_projects: list[DashboardProject]
    open_tasks: int
    completed_tasks: int
    overdue_tasks: int
    tasks_by_member: list[CountItem]
    tasks_by_priority: list[CountItem]


class MemberDashboard(BaseModel):
    my_tasks_count: int
    overdue_tasks: int
    tasks_due_today: int
    my_tasks: list[DashboardTask]
    recently_completed: list[DashboardTask]
    my_tasks_by_status: list[CountItem]