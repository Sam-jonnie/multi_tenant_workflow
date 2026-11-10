from fastapi import APIRouter, status

from app.api.deps import ManageableTask, TaskContextDep, TaskDependencyServiceDep
from app.models.task import Task
from app.schemas.common import ApiResponse
from app.schemas.task_dependency import DependencyAdd, TaskBrief, TaskDependenciesRead

router = APIRouter(prefix="/tasks/{task_id}/dependencies", tags=["Task Dependencies"])


def _build(prerequisites: list[Task], dependents: list[Task]) -> ApiResponse[TaskDependenciesRead]:
    return ApiResponse[TaskDependenciesRead](
        data=TaskDependenciesRead(
            depends_on=[TaskBrief.model_validate(t) for t in prerequisites],
            blocks=[TaskBrief.model_validate(t) for t in dependents],
        )
    )


@router.get("", response_model=ApiResponse[TaskDependenciesRead])
def list_dependencies(
    tctx: TaskContextDep, service: TaskDependencyServiceDep
) -> ApiResponse[TaskDependenciesRead]:
    return _build(*service.list_for_task(tctx))


@router.post(
    "", response_model=ApiResponse[TaskDependenciesRead], status_code=status.HTTP_201_CREATED
)
def add_dependency(
    payload: DependencyAdd, tctx: ManageableTask, service: TaskDependencyServiceDep
) -> ApiResponse[TaskDependenciesRead]:
    return _build(*service.add(tctx, payload.depends_on_id))


@router.delete("/{depends_on_id}", response_model=ApiResponse[None])
def remove_dependency(
    depends_on_id: int, tctx: ManageableTask, service: TaskDependencyServiceDep
) -> ApiResponse[None]:
    service.remove(tctx, depends_on_id)
    return ApiResponse[None](message="Dependency removed.")