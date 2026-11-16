from collections.abc import Awaitable, Callable

from fastapi import Depends, FastAPI, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.router import api_router
from app.core.config import settings
from app.core.database import get_db
from app.core.exceptions import register_exception_handlers

MULTIPART_OVERHEAD_BYTES = 1024 * 1024  # form boundaries and headers around the file

app = FastAPI(title=settings.app_name, version="1.0.0")

register_exception_handlers(app)


@app.middleware("http")
async def reject_oversized_uploads(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Refuse an obviously oversized upload from its Content-Length header, before the
    body is read. The streaming check in FileStorage.stage is the real guarantee,
    because a client can lie in this header."""
    if request.method == "POST" and request.url.path.endswith("/attachments"):
        declared = request.headers.get("content-length", "")
        limit = settings.max_upload_size_bytes + MULTIPART_OVERHEAD_BYTES
        if declared.isdigit() and int(declared) > limit:
            return JSONResponse(
                status_code=413,
                content={
                    "success": False,
                    "error": {
                        "code": "FILE_TOO_LARGE",
                        "message": f"The file exceeds the {settings.max_upload_size_mb} MB limit.",
                    },
                },
            )
    return await call_next(request)


# Same routes under both prefixes: /api/auth/... (as the assignment says)
# and /api/v1/auth/... (the API-versioning bonus, shown in Swagger).
app.include_router(api_router, prefix="/api/v1")
app.include_router(api_router, prefix="/api", include_in_schema=False)


@app.get("/health", tags=["Health"])
def health(db: Session = Depends(get_db)) -> dict[str, str]:
    db.execute(text("SELECT 1"))
    return {"status": "ok"}