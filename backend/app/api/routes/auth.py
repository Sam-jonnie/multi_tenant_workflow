from fastapi import APIRouter, status

from app.api.deps import AuthServiceDep, CurrentUser
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenPair,
)
from app.schemas.common import ApiResponse
from app.schemas.user import UserRead

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/register", response_model=ApiResponse[UserRead], status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, service: AuthServiceDep) -> ApiResponse[UserRead]:
    user = service.register(payload)
    return ApiResponse[UserRead](data=UserRead.model_validate(user), message="Registered.")


@router.post("/login", response_model=ApiResponse[TokenPair])
def login(payload: LoginRequest, service: AuthServiceDep) -> ApiResponse[TokenPair]:
    return ApiResponse[TokenPair](data=service.login(payload))


@router.post("/refresh", response_model=ApiResponse[TokenPair])
def refresh(payload: RefreshRequest, service: AuthServiceDep) -> ApiResponse[TokenPair]:
    return ApiResponse[TokenPair](data=service.refresh(payload.refresh_token))


@router.post("/logout", response_model=ApiResponse[None])
def logout(payload: RefreshRequest, service: AuthServiceDep) -> ApiResponse[None]:
    service.logout(payload.refresh_token)
    return ApiResponse[None](message="Logged out.")


@router.get("/me", response_model=ApiResponse[UserRead])
def me(current_user: CurrentUser) -> ApiResponse[UserRead]:
    return ApiResponse[UserRead](data=UserRead.model_validate(current_user))


@router.post("/change-password", response_model=ApiResponse[None])
def change_password(
    payload: ChangePasswordRequest, current_user: CurrentUser, service: AuthServiceDep
) -> ApiResponse[None]:
    service.change_password(current_user, payload)
    return ApiResponse[None](message="Password changed. Please log in again.")