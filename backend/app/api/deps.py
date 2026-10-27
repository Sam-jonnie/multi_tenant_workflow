from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from dataclasses import dataclass

from app.core.enums import OrgRole
from app.core.permissions import has_min_role
from app.models.organization import Organization, OrganizationMember
from app.repositories.membership_repository import MembershipRepository
from app.repositories.organization_repository import OrganizationRepository
from app.services.organization_service import OrganizationService

from app.core.database import get_db
from app.core.enums import TokenType
from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.security import decode_token
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.services.auth_service import AuthService

bearer_scheme = HTTPBearer(auto_error=False)

DbSession = Annotated[Session, Depends(get_db)]


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


def get_auth_service(db: DbSession) -> AuthService:
    return AuthService(db)


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]

@dataclass
class OrgContext:
    """Who is calling, which org they are acting in, and what they can do there."""

    organization: Organization
    user: User
    membership: OrganizationMember | None  # None for a super admin who isn't a member
    role: OrgRole  # the effective role


def get_org_context(org_id: int, current_user: CurrentUser, db: DbSession) -> OrgContext:
    denied = ForbiddenError(
        "ORGANIZATION_ACCESS_DENIED", "You do not have access to this organization."
    )
    org = OrganizationRepository(db).get_by_id(org_id)
    if org is None:
        raise denied  # same answer as "not a member", so IDs can't be probed

    if current_user.is_super_admin:
        return OrgContext(org, current_user, None, OrgRole.ORG_ADMIN)

    membership = MembershipRepository(db).get(org_id, current_user.id)
    if membership is None or not membership.is_active or not org.is_active:
        raise denied
    return OrgContext(org, current_user, membership, membership.role)


OrgContextDep = Annotated[OrgContext, Depends(get_org_context)]


def require_org_role(minimum: OrgRole):
    def checker(ctx: OrgContextDep) -> OrgContext:
        if not has_min_role(ctx.role, minimum):
            raise ForbiddenError(
                "INSUFFICIENT_ROLE", f"This action requires the {minimum.value} role or higher."
            )
        return ctx

    return checker


OrgViewer = Annotated[OrgContext, Depends(require_org_role(OrgRole.VIEWER))]
OrgMember = Annotated[OrgContext, Depends(require_org_role(OrgRole.TEAM_MEMBER))]
OrgManager = Annotated[OrgContext, Depends(require_org_role(OrgRole.PROJECT_MANAGER))]
OrgAdmin = Annotated[OrgContext, Depends(require_org_role(OrgRole.ORG_ADMIN))]


def get_organization_service(db: DbSession) -> OrganizationService:
    return OrganizationService(db)


OrganizationServiceDep = Annotated[OrganizationService, Depends(get_organization_service)]