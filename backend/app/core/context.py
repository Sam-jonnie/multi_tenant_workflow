from dataclasses import dataclass

from app.core.enums import OrgRole
from app.core.permissions import has_min_role
from app.models.organization import Organization, OrganizationMember
from app.models.project import Project
from app.models.user import User
from app.models.task import Task


@dataclass
class OrgContext:
    organization: Organization
    user: User
    membership: OrganizationMember | None  # None for a super admin who isn't a member
    role: OrgRole  # the effective role

    @property
    def is_admin(self) -> bool:
        return self.role == OrgRole.ORG_ADMIN


@dataclass
class ProjectContext:
    project: Project
    org: OrgContext
    is_member: bool

    @property
    def is_owner(self) -> bool:
        return self.project.owner_id == self.org.user.id

    @property
    def can_manage(self) -> bool:
        return self.org.is_admin or (
            self.is_owner and has_min_role(self.org.role, OrgRole.PROJECT_MANAGER)
        )

@dataclass
class TaskContext:
    task: Task
    project: ProjectContext

    @property
    def user(self) -> User:
        return self.project.org.user

    @property
    def role(self) -> OrgRole:
        return self.project.org.role

    @property
    def is_manager(self) -> bool:
        # The project context already proved membership (or admin), so role is enough.
        return has_min_role(self.role, OrgRole.PROJECT_MANAGER)

    @property
    def is_participant(self) -> bool:
        return self.user.id in (self.task.reporter_id, self.task.assignee_id)

    @property
    def can_edit(self) -> bool:
        return has_min_role(self.role, OrgRole.TEAM_MEMBER) and (
            self.is_manager or self.is_participant
        )

    @property
    def can_delete(self) -> bool:
        return has_min_role(self.role, OrgRole.TEAM_MEMBER) and (
            self.is_manager or self.task.reporter_id == self.user.id
        )