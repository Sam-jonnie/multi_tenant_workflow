from typing import Annotated

from fastapi import APIRouter, Query, status

from app.api.deps import OrganizationServiceDep, OrgAdmin, OrgViewer
from app.core.enums import OrgRole
from app.models.organization import OrganizationMember
from app.schemas.common import ApiResponse, Page, PageParams
from app.schemas.organization import MemberAdd, MemberRead, MemberRoleUpdate, MemberStatusUpdate

router = APIRouter(prefix="/organizations/{org_id}/members", tags=["Members"])


def _to_read(m: OrganizationMember) -> MemberRead:
    return MemberRead(
        user_id=m.user_id,
        email=m.user.email,
        username=m.user.username,
        full_name=m.user.full_name,
        role=m.role,
        is_active=m.is_active,
        joined_at=m.created_at,
    )


@router.get("", response_model=ApiResponse[Page[MemberRead]])
def list_members(
    org_id: int,
    ctx: OrgViewer,
    service: OrganizationServiceDep,
    params: Annotated[PageParams, Query()],
    search: str | None = None,
    role: OrgRole | None = None,
    is_active: bool | None = None,
) -> ApiResponse[Page[MemberRead]]:
    members, total = service.list_members(ctx.organization, params, search, role, is_active)
    return ApiResponse[Page[MemberRead]](
        data=Page.create([_to_read(m) for m in members], total, params)
    )


@router.post("", response_model=ApiResponse[MemberRead], status_code=status.HTTP_201_CREATED)
def add_member(
    org_id: int, payload: MemberAdd, ctx: OrgAdmin, service: OrganizationServiceDep
) -> ApiResponse[MemberRead]:
    member = service.add_member(ctx.organization, payload)
    return ApiResponse[MemberRead](data=_to_read(member), message="Member added.")


@router.patch("/{user_id}/role", response_model=ApiResponse[MemberRead])
def change_member_role(
    org_id: int,
    user_id: int,
    payload: MemberRoleUpdate,
    ctx: OrgAdmin,
    service: OrganizationServiceDep,
) -> ApiResponse[MemberRead]:
    member = service.change_role(ctx.organization, user_id, payload.role)
    return ApiResponse[MemberRead](data=_to_read(member))


@router.patch("/{user_id}/status", response_model=ApiResponse[MemberRead])
def set_member_status(
    org_id: int,
    user_id: int,
    payload: MemberStatusUpdate,
    ctx: OrgAdmin,
    service: OrganizationServiceDep,
) -> ApiResponse[MemberRead]:
    member = service.set_member_active(ctx.organization, user_id, payload.is_active)
    return ApiResponse[MemberRead](data=_to_read(member))


@router.delete("/{user_id}", response_model=ApiResponse[None])
def remove_member(
    org_id: int, user_id: int, ctx: OrgAdmin, service: OrganizationServiceDep
) -> ApiResponse[None]:
    service.remove_member(ctx.organization, user_id)
    return ApiResponse[None](message="Member removed.")