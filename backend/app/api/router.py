from fastapi import APIRouter

from app.api.routes import auth, members, organizations

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(organizations.router)
api_router.include_router(members.router)