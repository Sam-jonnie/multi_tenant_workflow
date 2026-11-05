from collections.abc import Mapping
from enum import StrEnum

from app.core.enums import ProjectStatus
from app.core.exceptions import ConflictError

PROJECT_TRANSITIONS: dict[ProjectStatus, tuple[ProjectStatus, ...]] = {
    ProjectStatus.PLANNING: (ProjectStatus.ACTIVE, ProjectStatus.ARCHIVED),
    ProjectStatus.ACTIVE: (ProjectStatus.ON_HOLD, ProjectStatus.COMPLETED),
    ProjectStatus.ON_HOLD: (ProjectStatus.ACTIVE, ProjectStatus.ARCHIVED),
    ProjectStatus.COMPLETED: (ProjectStatus.ACTIVE, ProjectStatus.ARCHIVED),
    ProjectStatus.ARCHIVED: (),
}


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