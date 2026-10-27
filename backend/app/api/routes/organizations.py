from typing import Annotated

from fastapi import APIRouter, Query, status

from app.api.deps import CurrentUser, OrganizationServiceDep, OrgAdmin, OrgViewer
from app.schemas.common import ApiResponse, Page, PageParams
from app.schemas.organization import OrganizationCreate, OrganizationRead, OrganizationUpdate

router = APIRouter(prefix="/organizations", tags=["Organizations"])


@router.post(
    "", response_model=ApiResponse[OrganizationRead], status_code=status.HTTP_201_CREATED
)
def create_organization(
    payload: OrganizationCreate, current_user: CurrentUser, service: OrganizationServiceDep
) -> ApiResponse[OrganizationRead]:
    org = service.create(current_user, payload)
    return ApiResponse[OrganizationRead](
        data=OrganizationRead.model_validate(org), message="Organization created."
    )


@router.get("", response_model=ApiResponse[Page[OrganizationRead]])
def list_my_organizations(
    params: Annotated[PageParams, Query()],
    current_user: CurrentUser,
    service: OrganizationServiceDep,
) -> ApiResponse[Page[OrganizationRead]]:
    orgs, total = service.list_for_user(current_user, params)
    items = [OrganizationRead.model_validate(o) for o in orgs]
    return ApiResponse[Page[OrganizationRead]](data=Page.create(items, total, params))


@router.get("/{org_id}", response_model=ApiResponse[OrganizationRead])
def get_organization(org_id: int, ctx: OrgViewer) -> ApiResponse[OrganizationRead]:
    return ApiResponse[OrganizationRead](data=OrganizationRead.model_validate(ctx.organization))


@router.patch("/{org_id}", response_model=ApiResponse[OrganizationRead])
def update_organization(
    org_id: int, payload: OrganizationUpdate, ctx: OrgAdmin, service: OrganizationServiceDep
) -> ApiResponse[OrganizationRead]:
    org = service.update(ctx.organization, payload)
    return ApiResponse[OrganizationRead](data=OrganizationRead.model_validate(org))