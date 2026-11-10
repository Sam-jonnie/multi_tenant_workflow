from typing import Annotated

from fastapi import Depends, Header, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.context import (
    CommentContext,
    OrgContext,
    ProjectContext,
    RequestInfo,
    TaskContext,
)
from app.core.database import get_db
from app.core.enums import OrgRole, TokenType
from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.permissions import has_min_role
from app.core.security import decode_token
from app.models.project import Project
from app.models.user import User
from app.repositories.comment_repository import CommentRepository
from app.repositories.membership_repository import MembershipRepository
from app.repositories.organization_repository import OrganizationRepository
from app.repositories.project_repository import ProjectMemberRepository, ProjectRepository
from app.repositories.task_repository import TaskRepository
from app.repositories.user_repository import UserRepository
from app.services.audit_service import AuditService
from app.services.auth_service import AuthService
from app.services.comment_service import CommentService
from app.services.dashboard_service import DashboardService
from app.services.organization_service import OrganizationService
from app.services.project_service import ProjectService
from app.services.task_dependency_service import TaskDependencyService
from app.services.task_service import TaskService

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
def build_project_context(
    project: Project | None, user: User, db: Session, denied: ForbiddenError
) -> ProjectContext:
    if project is None:
        raise denied
    # The project tells us which org it belongs to, then we check the user against THAT org.
    org_ctx = build_org_context(project.organization_id, user, db, denied)

    is_member = ProjectMemberRepository(db).get(project.id, user.id) is not None
    if not org_ctx.is_admin and not is_member:
        raise denied
    return ProjectContext(project=project, org=org_ctx, is_member=is_member)


def get_project_context(
    project_id: int, current_user: CurrentUser, db: DbSession
) -> ProjectContext:
    denied = ForbiddenError("PROJECT_ACCESS_DENIED", "You do not have access to this project.")
    project = ProjectRepository(db).get_by_id(project_id)
    return build_project_context(project, current_user, db, denied)


ProjectContextDep = Annotated[ProjectContext, Depends(get_project_context)]


def get_manageable_project(pctx: ProjectContextDep) -> ProjectContext:
    if not pctx.can_manage:
        raise ForbiddenError(
            "PROJECT_MANAGE_DENIED",
            "Only the project owner or an organization admin can do this.",
        )
    return pctx


def get_project_contributor(pctx: ProjectContextDep) -> ProjectContext:
    if not has_min_role(pctx.org.role, OrgRole.TEAM_MEMBER):
        raise ForbiddenError(
            "INSUFFICIENT_ROLE",
            f"This action requires the {OrgRole.TEAM_MEMBER.value} role or higher.",
        )
    return pctx


ManageableProject = Annotated[ProjectContext, Depends(get_manageable_project)]
ProjectContributor = Annotated[ProjectContext, Depends(get_project_contributor)]


# ---------- task context ----------
def get_task_context(task_id: int, current_user: CurrentUser, db: DbSession) -> TaskContext:
    denied = ForbiddenError(
        "TASK_ORGANIZATION_ACCESS_DENIED", "You do not have access to this task."
    )
    task = TaskRepository(db).get_by_id(task_id)
    pctx = build_project_context(task.project if task else None, current_user, db, denied)
    return TaskContext(task=task, project=pctx)  # type: ignore[arg-type]


TaskContextDep = Annotated[TaskContext, Depends(get_task_context)]


def get_editable_task(tctx: TaskContextDep) -> TaskContext:
    if not tctx.can_edit:
        raise ForbiddenError(
            "TASK_EDIT_DENIED", "Only project managers, the reporter or the assignee can do this."
        )
    return tctx


def get_manageable_task(tctx: TaskContextDep) -> TaskContext:
    if not tctx.is_manager:
        raise ForbiddenError("TASK_MANAGE_DENIED", "Only project managers can do this.")
    return tctx


def get_task_contributor(tctx: TaskContextDep) -> TaskContext:
    if not has_min_role(tctx.role, OrgRole.TEAM_MEMBER):
        raise ForbiddenError(
            "INSUFFICIENT_ROLE",
            f"This action requires the {OrgRole.TEAM_MEMBER.value} role or higher.",
        )
    return tctx


EditableTask = Annotated[TaskContext, Depends(get_editable_task)]
ManageableTask = Annotated[TaskContext, Depends(get_manageable_task)]
ContributorTask = Annotated[TaskContext, Depends(get_task_contributor)]


# ---------- comment context ----------
def get_comment_context(
    comment_id: int, current_user: CurrentUser, db: DbSession
) -> CommentContext:
    denied = ForbiddenError(
        "COMMENT_ORGANIZATION_ACCESS_DENIED", "You do not have access to this comment."
    )
    comment = CommentRepository(db).get_by_id(comment_id)
    pctx = build_project_context(comment.project if comment else None, current_user, db, denied)
    return CommentContext(comment=comment, project=pctx)  # type: ignore[arg-type]


CommentContextDep = Annotated[CommentContext, Depends(get_comment_context)]


def get_editable_comment(cctx: CommentContextDep) -> CommentContext:
    if not cctx.can_edit:
        raise ForbiddenError("COMMENT_EDIT_DENIED", "You can only edit your own comments.")
    return cctx


def get_deletable_comment(cctx: CommentContextDep) -> CommentContext:
    if not cctx.can_delete:
        raise ForbiddenError("COMMENT_DELETE_DENIED", "You can only delete your own comments.")
    return cctx


EditableComment = Annotated[CommentContext, Depends(get_editable_comment)]
DeletableComment = Annotated[CommentContext, Depends(get_deletable_comment)]


# ---------- request info + audit ----------
def get_request_info(request: Request) -> RequestInfo:
    user_agent = request.headers.get("user-agent")
    return RequestInfo(
        ip_address=request.client.host if request.client else None,
        user_agent=user_agent[:255] if user_agent else None,
    )


RequestInfoDep = Annotated[RequestInfo, Depends(get_request_info)]


def get_audit_service(db: DbSession, request_info: RequestInfoDep) -> AuditService:
    return AuditService(db, request_info)


AuditServiceDep = Annotated[AuditService, Depends(get_audit_service)]


# ---------- services ----------
def get_auth_service(db: DbSession) -> AuthService:
    return AuthService(db)


def get_organization_service(db: DbSession) -> OrganizationService:
    return OrganizationService(db)


def get_project_service(db: DbSession) -> ProjectService:
    return ProjectService(db)


def get_task_service(db: DbSession) -> TaskService:
    return TaskService(db)


def get_task_dependency_service(db: DbSession) -> TaskDependencyService:
    return TaskDependencyService(db)


def get_dashboard_service(db: DbSession) -> DashboardService:
    return DashboardService(db)


def get_comment_service(db: DbSession, audit: AuditServiceDep) -> CommentService:
    return CommentService(db, audit)


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]
OrganizationServiceDep = Annotated[OrganizationService, Depends(get_organization_service)]
ProjectServiceDep = Annotated[ProjectService, Depends(get_project_service)]
TaskServiceDep = Annotated[TaskService, Depends(get_task_service)]
TaskDependencyServiceDep = Annotated[TaskDependencyService, Depends(get_task_dependency_service)]
DashboardServiceDep = Annotated[DashboardService, Depends(get_dashboard_service)]
CommentServiceDep = Annotated[CommentService, Depends(get_comment_service)]