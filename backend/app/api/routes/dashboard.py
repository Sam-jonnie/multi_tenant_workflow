from fastapi import APIRouter

from app.api.deps import DashboardServiceDep, TenantAdmin, TenantManager, TenantViewer
from app.schemas.common import ApiResponse
from app.schemas.dashboard import AdminDashboard, ManagerDashboard, MemberDashboard

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/admin", response_model=ApiResponse[AdminDashboard])
def admin_dashboard(
    ctx: TenantAdmin, service: DashboardServiceDep
) -> ApiResponse[AdminDashboard]:
    return ApiResponse[AdminDashboard](data=service.admin(ctx))


@router.get("/manager", response_model=ApiResponse[ManagerDashboard])
def manager_dashboard(
    ctx: TenantManager, service: DashboardServiceDep
) -> ApiResponse[ManagerDashboard]:
    return ApiResponse[ManagerDashboard](data=service.manager(ctx))


@router.get("/member", response_model=ApiResponse[MemberDashboard])
def member_dashboard(
    ctx: TenantViewer, service: DashboardServiceDep
) -> ApiResponse[MemberDashboard]:
    return ApiResponse[MemberDashboard](data=service.member(ctx))