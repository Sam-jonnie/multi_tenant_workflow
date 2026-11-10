from collections.abc import Mapping
from enum import StrEnum

from app.core.enums import ProjectStatus, TaskStatus
from app.core.exceptions import ConflictError

PROJECT_TRANSITIONS: dict[ProjectStatus, tuple[ProjectStatus, ...]] = {
    ProjectStatus.PLANNING: (ProjectStatus.ACTIVE, ProjectStatus.ARCHIVED),
    ProjectStatus.ACTIVE: (ProjectStatus.ON_HOLD, ProjectStatus.COMPLETED),
    ProjectStatus.ON_HOLD: (ProjectStatus.ACTIVE, ProjectStatus.ARCHIVED),
    ProjectStatus.COMPLETED: (ProjectStatus.ACTIVE, ProjectStatus.ARCHIVED),
    ProjectStatus.ARCHIVED: (),
}

TASK_TRANSITIONS: dict[TaskStatus, tuple[TaskStatus, ...]] = {
    TaskStatus.BACKLOG: (TaskStatus.TODO, TaskStatus.CANCELLED),
    TaskStatus.TODO: (TaskStatus.IN_PROGRESS, TaskStatus.BACKLOG, TaskStatus.CANCELLED),
    TaskStatus.IN_PROGRESS: (
        TaskStatus.REVIEW,
        TaskStatus.BLOCKED,
        TaskStatus.TODO,
        TaskStatus.CANCELLED,
    ),
    TaskStatus.BLOCKED: (TaskStatus.IN_PROGRESS, TaskStatus.CANCELLED),
    TaskStatus.REVIEW: (TaskStatus.DONE, TaskStatus.IN_PROGRESS, TaskStatus.CANCELLED),
    TaskStatus.DONE: (TaskStatus.IN_PROGRESS,),
    TaskStatus.CANCELLED: (TaskStatus.BACKLOG,),
}

TERMINAL_TASK_STATUSES: tuple[TaskStatus, ...] = (TaskStatus.DONE, TaskStatus.CANCELLED)

STATUSES_REQUIRING_ASSIGNEE: frozenset[TaskStatus] = frozenset(
    {TaskStatus.IN_PROGRESS, TaskStatus.REVIEW, TaskStatus.DONE}
)

# A task cannot ENTER these statuses while a prerequisite is unresolved.
STATUSES_BLOCKED_BY_DEPENDENCIES: frozenset[TaskStatus] = frozenset(
    {TaskStatus.IN_PROGRESS, TaskStatus.REVIEW, TaskStatus.DONE}
)

# A prerequisite in one of these statuses no longer blocks anything.
DEPENDENCY_SATISFIED_STATUSES: tuple[TaskStatus, ...] = (TaskStatus.DONE, TaskStatus.CANCELLED)


def ensure_transition[S: StrEnum](
    transitions: Mapping[S, tuple[S, ...]],
    current: S,
    target: S,
    *,
    code: str,
    entity: str,
) -> None:
    allowed = transitions[current]
    if target not in allowed:
        options = ", ".join(allowed) or "none"
        raise ConflictError(
            code,
            f"Cannot change {entity} status from '{current}' to '{target}'. "
            f"Allowed: {options}.",
        )