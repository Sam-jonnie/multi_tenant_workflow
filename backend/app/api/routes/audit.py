from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import AuditServiceDep, TenantAdmin
from app.schemas.audit import AuditListQuery, AuditLogRead
from app.schemas.common import ApiResponse, Page

router = APIRouter(prefix="/audit-logs", tags=["Audit Logs"])


# Read-only on purpose: no POST, PUT, PATCH or DELETE routes exist for audit logs.
@router.get("", response_model=ApiResponse[Page[AuditLogRead]])
def list_audit_logs(
    query: Annotated[AuditListQuery, Query()], ctx: TenantAdmin, service: AuditServiceDep
) -> ApiResponse[Page[AuditLogRead]]:
    entries, total = service.list_logs(ctx, query)
    items = [AuditLogRead.from_entry(e) for e in entries]
    return ApiResponse[Page[AuditLogRead]](data=Page.create(items, total, query))