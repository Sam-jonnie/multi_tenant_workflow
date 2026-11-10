from app.core.enums import ProjectStatus
from app.core.exceptions import ConflictError
from app.models.project import Project


def ensure_project_writable(project: Project) -> None:
    if project.status == ProjectStatus.ARCHIVED:
        raise ConflictError("PROJECT_ARCHIVED", "Archived projects are read-only.")