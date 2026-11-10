from typing import Annotated

from fastapi import APIRouter, Query, status

from app.api.deps import (
    CommentServiceDep,
    ContributorTask,
    DeletableComment,
    EditableComment,
    ProjectContextDep,
    ProjectContributor,
    TaskContextDep,
)
from app.models.comment import Comment
from app.schemas.comment import CommentCreate, CommentListQuery, CommentRead, CommentUpdate
from app.schemas.common import ApiResponse, Page

router = APIRouter(tags=["Comments"])


def _one(comment: Comment) -> ApiResponse[CommentRead]:
    return ApiResponse[CommentRead](data=CommentRead.model_validate(comment))


def _page(
    comments: list[Comment], total: int, query: CommentListQuery
) -> ApiResponse[Page[CommentRead]]:
    items = [CommentRead.model_validate(c) for c in comments]
    return ApiResponse[Page[CommentRead]](data=Page.create(items, total, query))


# ---------- project comments ----------
@router.post(
    "/projects/{project_id}/comments",
    response_model=ApiResponse[CommentRead],
    status_code=status.HTTP_201_CREATED,
)
def add_project_comment(
    payload: CommentCreate, pctx: ProjectContributor, service: CommentServiceDep
) -> ApiResponse[CommentRead]:
    return _one(service.add_to_project(pctx, payload))


@router.get("/projects/{project_id}/comments", response_model=ApiResponse[Page[CommentRead]])
def list_project_comments(
    query: Annotated[CommentListQuery, Query()],
    pctx: ProjectContextDep,
    service: CommentServiceDep,
) -> ApiResponse[Page[CommentRead]]:
    comments, total = service.list_for_project(pctx, query)
    return _page(comments, total, query)


# ---------- task comments ----------
@router.post(
    "/tasks/{task_id}/comments",
    response_model=ApiResponse[CommentRead],
    status_code=status.HTTP_201_CREATED,
)
def add_task_comment(
    payload: CommentCreate, tctx: ContributorTask, service: CommentServiceDep
) -> ApiResponse[CommentRead]:
    return _one(service.add_to_task(tctx, payload))


@router.get("/tasks/{task_id}/comments", response_model=ApiResponse[Page[CommentRead]])
def list_task_comments(
    query: Annotated[CommentListQuery, Query()],
    tctx: TaskContextDep,
    service: CommentServiceDep,
) -> ApiResponse[Page[CommentRead]]:
    comments, total = service.list_for_task(tctx, query)
    return _page(comments, total, query)


# ---------- single comment ----------
@router.patch("/comments/{comment_id}", response_model=ApiResponse[CommentRead])
def update_comment(
    payload: CommentUpdate, cctx: EditableComment, service: CommentServiceDep
) -> ApiResponse[CommentRead]:
    return _one(service.update(cctx, payload))


@router.delete("/comments/{comment_id}", response_model=ApiResponse[None])
def delete_comment(cctx: DeletableComment, service: CommentServiceDep) -> ApiResponse[None]:
    service.delete(cctx)
    return ApiResponse[None](message="Comment deleted.")