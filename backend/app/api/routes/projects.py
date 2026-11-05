from typing import Annotated

from fastapi import APIRouter, Query, status

from app.api.deps import (
    ManageableProject,
    ProjectContextDep,
    ProjectServiceDep,
    TenantManager,
    TenantViewer,
)
from app.models.project import ProjectMember
from app.schemas.common import ApiResponse, Page, PageParams
from app.schemas.project import (
    ProjectCreate,
    ProjectListQuery,
    ProjectMemberAdd,
    ProjectMemberRead,
    ProjectRead,
    ProjectStatusUpdate,
    ProjectUpdate,
)

router = APIRouter(prefix="/projects", tags=["Projects"])


def _member_read(member: ProjectMember, owner_id: int) -> ProjectMemberRead:
    return ProjectMemberRead(
        user_id=member.user_id,
        email=member.user.email,
        username=member.user.username,
        full_name=member.user.full_name,
        is_owner=member.user_id == owner_id,
        joined_at=member.created_at,
    )


# ---------- collection endpoints: org comes from the X-Organization-ID header ----------
@router.post("", response_model=ApiResponse[ProjectRead], status_code=status.HTTP_201_CREATED)
def create_project(
    payload: ProjectCreate, ctx: TenantManager, service: ProjectServiceDep
) -> ApiResponse[ProjectRead]:
    project = service.create(ctx, payload)
    return ApiResponse[ProjectRead](
        data=ProjectRead.model_validate(project), message="Project created."
    )


@router.get("", response_model=ApiResponse[Page[ProjectRead]])
def list_projects(
    query: Annotated[ProjectListQuery, Query()], ctx: TenantViewer, service: ProjectServiceDep
) -> ApiResponse[Page[ProjectRead]]:
    projects, total = service.list_projects(ctx, query)
    items = [ProjectRead.model_validate(p) for p in projects]
    return ApiResponse[Page[ProjectRead]](data=Page.create(items, total, query))


# ---------- resource endpoints: the project itself decides the organization ----------
@router.get("/{project_id}", response_model=ApiResponse[ProjectRead])
def get_project(pctx: ProjectContextDep) -> ApiResponse[ProjectRead]:
    return ApiResponse[ProjectRead](data=ProjectRead.model_validate(pctx.project))


@router.patch("/{project_id}", response_model=ApiResponse[ProjectRead])
def update_project(
    payload: ProjectUpdate, pctx: ManageableProject, service: ProjectServiceDep
) -> ApiResponse[ProjectRead]:
    project = service.update(pctx, payload)
    return ApiResponse[ProjectRead](data=ProjectRead.model_validate(project))


@router.patch("/{project_id}/status", response_model=ApiResponse[ProjectRead])
def change_project_status(
    payload: ProjectStatusUpdate, pctx: ManageableProject, service: ProjectServiceDep
) -> ApiResponse[ProjectRead]:
    project = service.change_status(pctx, payload.status)
    return ApiResponse[ProjectRead](data=ProjectRead.model_validate(project))


@router.post("/{project_id}/archive", response_model=ApiResponse[ProjectRead])
def archive_project(
    pctx: ManageableProject, service: ProjectServiceDep
) -> ApiResponse[ProjectRead]:
    from app.core.enums import ProjectStatus

    project = service.change_status(pctx, ProjectStatus.ARCHIVED)
    return ApiResponse[ProjectRead](data=ProjectRead.model_validate(project), message="Archived.")


@router.delete("/{project_id}", response_model=ApiResponse[None])
def delete_project(pctx: ProjectContextDep, service: ProjectServiceDep) -> ApiResponse[None]:
    service.delete(pctx)
    return ApiResponse[None](message="Project deleted.")


# ---------- members ----------
@router.get("/{project_id}/members", response_model=ApiResponse[Page[ProjectMemberRead]])
def list_project_members(
    params: Annotated[PageParams, Query()], pctx: ProjectContextDep, service: ProjectServiceDep
) -> ApiResponse[Page[ProjectMemberRead]]:
    members, total = service.list_members(pctx, params)
    items = [_member_read(m, pctx.project.owner_id) for m in members]
    return ApiResponse[Page[ProjectMemberRead]](data=Page.create(items, total, params))


@router.post(
    "/{project_id}/members",
    response_model=ApiResponse[ProjectMemberRead],
    status_code=status.HTTP_201_CREATED,
)
def add_project_member(
    payload: ProjectMemberAdd, pctx: ManageableProject, service: ProjectServiceDep
) -> ApiResponse[ProjectMemberRead]:
    member = service.add_member(pctx, payload.user_id)
    return ApiResponse[ProjectMemberRead](
        data=_member_read(member, pctx.project.owner_id), message="Member added."
    )


@router.delete("/{project_id}/members/{user_id}", response_model=ApiResponse[None])
def remove_project_member(
    user_id: int, pctx: ManageableProject, service: ProjectServiceDep
) -> ApiResponse[None]:
    service.remove_member(pctx, user_id)
    return ApiResponse[None](message="Member removed.")