from fastapi import APIRouter

from app.api.routes import (
    auth,
    dashboard,
    members,
    organizations,
    projects,
    task_dependencies,
    tasks,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(organizations.router)
api_router.include_router(members.router)
api_router.include_router(projects.router)
api_router.include_router(tasks.router)
api_router.include_router(task_dependencies.router)
api_router.include_router(dashboard.router)