from typing import Annotated

from fastapi import APIRouter, Query, status

from app.api.deps import (
    EditableTask,
    ManageableTask,
    ProjectContributor,
    TaskContextDep,
    TaskServiceDep,
    TenantViewer,
)
from app.schemas.common import ApiResponse, Page, PageParams
from app.schemas.task import (
    TaskAssign,
    TaskAssignmentRead,
    TaskCreate,
    TaskListQuery,
    TaskMove,
    TaskPriorityUpdate,
    TaskRead,
    TaskStatusUpdate,
    TaskUpdate,
)

router = APIRouter(tags=["Tasks"])


def _task(task) -> ApiResponse[TaskRead]:
    return ApiResponse[TaskRead](data=TaskRead.model_validate(task))


@router.post(
    "/projects/{project_id}/tasks",
    response_model=ApiResponse[TaskRead],
    status_code=status.HTTP_201_CREATED,
)
def create_task(
    payload: TaskCreate, pctx: ProjectContributor, service: TaskServiceDep
) -> ApiResponse[TaskRead]:
    return _task(service.create(pctx, payload))


@router.get("/tasks", response_model=ApiResponse[Page[TaskRead]])
def list_tasks(
    query: Annotated[TaskListQuery, Query()], ctx: TenantViewer, service: TaskServiceDep
) -> ApiResponse[Page[TaskRead]]:
    tasks, total = service.list_tasks(ctx, query)
    items = [TaskRead.model_validate(t) for t in tasks]
    return ApiResponse[Page[TaskRead]](data=Page.create(items, total, query))


@router.get("/tasks/{task_id}", response_model=ApiResponse[TaskRead])
def get_task(tctx: TaskContextDep) -> ApiResponse[TaskRead]:
    return _task(tctx.task)


@router.patch("/tasks/{task_id}", response_model=ApiResponse[TaskRead])
def update_task(
    payload: TaskUpdate, tctx: EditableTask, service: TaskServiceDep
) -> ApiResponse[TaskRead]:
    return _task(service.update(tctx, payload))


@router.patch("/tasks/{task_id}/status", response_model=ApiResponse[TaskRead])
def change_task_status(
    payload: TaskStatusUpdate, tctx: EditableTask, service: TaskServiceDep
) -> ApiResponse[TaskRead]:
    return _task(service.change_status(tctx, payload.status))


@router.patch("/tasks/{task_id}/priority", response_model=ApiResponse[TaskRead])
def change_task_priority(
    payload: TaskPriorityUpdate, tctx: EditableTask, service: TaskServiceDep
) -> ApiResponse[TaskRead]:
    return _task(service.change_priority(tctx, payload.priority))


@router.patch("/tasks/{task_id}/move", response_model=ApiResponse[TaskRead])
def move_task(
    payload: TaskMove, tctx: EditableTask, service: TaskServiceDep
) -> ApiResponse[TaskRead]:
    return _task(service.move(tctx, payload))


@router.patch("/tasks/{task_id}/assignee", response_model=ApiResponse[TaskRead])
def assign_task(
    payload: TaskAssign, tctx: ManageableTask, service: TaskServiceDep
) -> ApiResponse[TaskRead]:
    return _task(service.assign(tctx, payload.assignee_id))


@router.delete("/tasks/{task_id}", response_model=ApiResponse[None])
def delete_task(tctx: TaskContextDep, service: TaskServiceDep) -> ApiResponse[None]:
    service.delete(tctx)
    return ApiResponse[None](message="Task deleted.")


@router.get(
    "/tasks/{task_id}/assignment-history",
    response_model=ApiResponse[Page[TaskAssignmentRead]],
)
def assignment_history(
    params: Annotated[PageParams, Query()], tctx: TaskContextDep, service: TaskServiceDep
) -> ApiResponse[Page[TaskAssignmentRead]]:
    entries, total = service.assignment_history(tctx, params)
    items = [TaskAssignmentRead.model_validate(e) for e in entries]
    return ApiResponse[Page[TaskAssignmentRead]](data=Page.create(items, total, params))