from dataclasses import dataclass

from app.core.enums import OrgRole
from app.core.permissions import has_min_role
from app.models.organization import Organization, OrganizationMember
from app.models.project import Project
from app.models.user import User


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