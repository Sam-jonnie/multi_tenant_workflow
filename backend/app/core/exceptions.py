import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


class AppException(Exception):
    """Base class for every error we raise on purpose."""

    status_code: int = 500

    def __init__(
        self, code: str, message: str, details: list[dict[str, Any]] | None = None
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details


class BadRequestError(AppException):
    status_code = 400


class UnauthorizedError(AppException):
    status_code = 401


class ForbiddenError(AppException):
    status_code = 403


class NotFoundError(AppException):
    status_code = 404


class ConflictError(AppException):
    status_code = 409


def _error_response(
    status_code: int,
    code: str,
    message: str,
    details: list[dict[str, Any]] | None = None,
) -> JSONResponse:
    error: dict[str, Any] = {"code": code, "message": message}
    if details:
        error["details"] = details
    return JSONResponse(
        status_code=status_code, content={"success": False, "error": error}
    )


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    return _error_response(exc.status_code, exc.code, exc.message, exc.details)


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    details = [
        {"field": ".".join(str(p) for p in err["loc"][1:]), "message": err["msg"]}
        for err in exc.errors()
    ]
    return _error_response(422, "VALIDATION_ERROR", "Request validation failed.", details)


async def http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    return _error_response(exc.status_code, f"HTTP_{exc.status_code}", str(exc.detail))


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return _error_response(500, "INTERNAL_SERVER_ERROR", "Something went wrong.")


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)