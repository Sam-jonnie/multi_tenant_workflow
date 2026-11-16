from typing import Annotated

from fastapi import APIRouter, File, Query, UploadFile, status
from fastapi.responses import FileResponse

from app.api.deps import (
    AttachmentContextDep,
    AttachmentServiceDep,
    ContributorTask,
    DeletableAttachment,
    ProjectContextDep,
    ProjectContributor,
    TaskContextDep,
)
from app.models.attachment import Attachment
from app.schemas.attachment import AttachmentListQuery, AttachmentRead
from app.schemas.common import ApiResponse, Page

router = APIRouter(tags=["Attachments"])


def _one(attachment: Attachment, message: str | None = None) -> ApiResponse[AttachmentRead]:
    return ApiResponse[AttachmentRead](
        data=AttachmentRead.model_validate(attachment), message=message
    )


def _page(
    items: list[Attachment], total: int, query: AttachmentListQuery
) -> ApiResponse[Page[AttachmentRead]]:
    read = [AttachmentRead.model_validate(a) for a in items]
    return ApiResponse[Page[AttachmentRead]](data=Page.create(read, total, query))


# ---------- project files ----------
@router.post(
    "/projects/{project_id}/attachments",
    response_model=ApiResponse[AttachmentRead],
    status_code=status.HTTP_201_CREATED,
)
def upload_project_file(
    file: Annotated[UploadFile, File()],
    pctx: ProjectContributor,
    service: AttachmentServiceDep,
) -> ApiResponse[AttachmentRead]:
    attachment = service.upload(pctx, None, file.filename, file.file)
    return _one(attachment, "File uploaded.")


@router.get(
    "/projects/{project_id}/attachments", response_model=ApiResponse[Page[AttachmentRead]]
)
def list_project_files(
    query: Annotated[AttachmentListQuery, Query()],
    pctx: ProjectContextDep,
    service: AttachmentServiceDep,
) -> ApiResponse[Page[AttachmentRead]]:
    items, total = service.list_for_project(pctx, query)
    return _page(items, total, query)


# ---------- task files ----------
@router.post(
    "/tasks/{task_id}/attachments",
    response_model=ApiResponse[AttachmentRead],
    status_code=status.HTTP_201_CREATED,
)
def upload_task_file(
    file: Annotated[UploadFile, File()],
    tctx: ContributorTask,
    service: AttachmentServiceDep,
) -> ApiResponse[AttachmentRead]:
    attachment = service.upload(tctx.project, tctx.task.id, file.filename, file.file)
    return _one(attachment, "File uploaded.")


@router.get("/tasks/{task_id}/attachments", response_model=ApiResponse[Page[AttachmentRead]])
def list_task_files(
    query: Annotated[AttachmentListQuery, Query()],
    tctx: TaskContextDep,
    service: AttachmentServiceDep,
) -> ApiResponse[Page[AttachmentRead]]:
    items, total = service.list_for_task(tctx.task.id, query)
    return _page(items, total, query)


# ---------- single file ----------
@router.get("/attachments/{attachment_id}", response_model=ApiResponse[AttachmentRead])
def get_file_info(actx: AttachmentContextDep) -> ApiResponse[AttachmentRead]:
    return _one(actx.attachment)


@router.get("/attachments/{attachment_id}/download", response_model=None)
def download_file(actx: AttachmentContextDep, service: AttachmentServiceDep) -> FileResponse:
    path = service.file_path(actx)
    return FileResponse(
        path,
        media_type=actx.attachment.mime_type,
        filename=actx.attachment.filename,
        content_disposition_type="attachment",  # the browser saves it, never renders it
        headers={"X-Content-Type-Options": "nosniff"},
    )


@router.delete("/attachments/{attachment_id}", response_model=ApiResponse[None])
def delete_file(
    actx: DeletableAttachment, service: AttachmentServiceDep
) -> ApiResponse[None]:
    service.delete(actx)
    return ApiResponse[None](message="File deleted.")