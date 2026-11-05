from typing import Annotated

from fastapi import Depends, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.context import OrgContext, ProjectContext
from app.core.database import get_db
from app.core.enums import OrgRole, TokenType
from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.permissions import has_min_role
from app.core.security import decode_token
from app.models.user import User
from app.repositories.membership_repository import MembershipRepository
from app.repositories.organization_repository import OrganizationRepository
from app.repositories.project_repository import ProjectMemberRepository, ProjectRepository
from app.repositories.user_repository import UserRepository
from app.services.auth_service import AuthService
from app.services.organization_service import OrganizationService
from app.services.project_service import ProjectService

bearer_scheme = HTTPBearer(auto_error=False)

DbSession = Annotated[Session, Depends(get_db)]


# ---------- authentication ----------
def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: DbSession,
) -> User:
    if credentials is None:
        raise UnauthorizedError("NOT_AUTHENTICATED", "Authentication required.")

    payload = decode_token(credentials.credentials, TokenType.ACCESS)
    user = UserRepository(db).get_by_id(int(payload["sub"]))
    if user is None:
        raise UnauthorizedError("USER_NOT_FOUND", "User no longer exists.")
    if not user.is_active:
        raise ForbiddenError("USER_INACTIVE", "Your account is deactivated.")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


# ---------- organization context ----------
def build_org_context(
    org_id: int, user: User, db: Session, denied: ForbiddenError
) -> OrgContext:
    org = OrganizationRepository(db).get_by_id(org_id)
    if org is None:
        raise denied  # same answer as "not a member", so IDs can't be probed

    if user.is_super_admin:
        return OrgContext(org, user, None, OrgRole.ORG_ADMIN)

    membership = MembershipRepository(db).get(org_id, user.id)
    if membership is None or not membership.is_active or not org.is_active:
        raise denied
    return OrgContext(org, user, membership, membership.role)


def _org_denied() -> ForbiddenError:
    return ForbiddenError(
        "ORGANIZATION_ACCESS_DENIED", "You do not have access to this organization."
    )


def get_org_context(org_id: int, current_user: CurrentUser, db: DbSession) -> OrgContext:
    """Org taken from the URL path: /organizations/{org_id}/..."""
    return build_org_context(org_id, current_user, db, _org_denied())


def get_tenant_context(
    x_organization_id: Annotated[int, Header()], current_user: CurrentUser, db: DbSession
) -> OrgContext:
    """Org taken from the X-Organization-ID header: used by collection endpoints."""
    return build_org_context(x_organization_id, current_user, db, _org_denied())


OrgContextDep = Annotated[OrgContext, Depends(get_org_context)]
TenantContextDep = Annotated[OrgContext, Depends(get_tenant_context)]


def _enforce_role(ctx: OrgContext, minimum: OrgRole) -> OrgContext:
    if not has_min_role(ctx.role, minimum):
        raise ForbiddenError(
            "INSUFFICIENT_ROLE", f"This action requires the {minimum.value} role or higher."
        )
    return ctx


def require_org_role(minimum: OrgRole):
    def checker(ctx: OrgContextDep) -> OrgContext:
        return _enforce_role(ctx, minimum)

    return checker


def require_tenant_role(minimum: OrgRole):
    def checker(ctx: TenantContextDep) -> OrgContext:
        return _enforce_role(ctx, minimum)

    return checker


# org from path
OrgViewer = Annotated[OrgContext, Depends(require_org_role(OrgRole.VIEWER))]
OrgMember = Annotated[OrgContext, Depends(require_org_role(OrgRole.TEAM_MEMBER))]
OrgManager = Annotated[OrgContext, Depends(require_org_role(OrgRole.PROJECT_MANAGER))]
OrgAdmin = Annotated[OrgContext, Depends(require_org_role(OrgRole.ORG_ADMIN))]

# org from header
TenantViewer = Annotated[OrgContext, Depends(require_tenant_role(OrgRole.VIEWER))]
TenantMember = Annotated[OrgContext, Depends(require_tenant_role(OrgRole.TEAM_MEMBER))]
TenantManager = Annotated[OrgContext, Depends(require_tenant_role(OrgRole.PROJECT_MANAGER))]
TenantAdmin = Annotated[OrgContext, Depends(require_tenant_role(OrgRole.ORG_ADMIN))]


# ---------- project context (resource-based authorization) ----------
def get_project_context(
    project_id: int, current_user: CurrentUser, db: DbSession
) -> ProjectContext:
    denied = ForbiddenError("PROJECT_ACCESS_DENIED", "You do not have access to this project.")

    project = ProjectRepository(db).get_by_id(project_id)
    if project is None:
        raise denied

    # The project tells us which org it belongs to, then we check the user against THAT org.
    org_ctx = build_org_context(project.organization_id, current_user, db, denied)

    is_member = ProjectMemberRepository(db).get(project.id, current_user.id) is not None
    if not org_ctx.is_admin and not is_member:
        raise denied
    return ProjectContext(project=project, org=org_ctx, is_member=is_member)


ProjectContextDep = Annotated[ProjectContext, Depends(get_project_context)]


def get_manageable_project(pctx: ProjectContextDep) -> ProjectContext:
    if not pctx.can_manage:
        raise ForbiddenError(
            "PROJECT_MANAGE_DENIED",
            "Only the project owner or an organization admin can do this.",
        )
    return pctx


ManageableProject = Annotated[ProjectContext, Depends(get_manageable_project)]


# ---------- services ----------
def get_auth_service(db: DbSession) -> AuthService:
    return AuthService(db)


def get_organization_service(db: DbSession) -> OrganizationService:
    return OrganizationService(db)


def get_project_service(db: DbSession) -> ProjectService:
    return ProjectService(db)


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]
OrganizationServiceDep = Annotated[OrganizationService, Depends(get_organization_service)]
ProjectServiceDep = Annotated[ProjectService, Depends(get_project_service)]