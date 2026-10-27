from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.router import api_router
from app.core.config import settings
from app.core.database import get_db
from app.core.exceptions import register_exception_handlers

app = FastAPI(title=settings.app_name, version="1.0.0")

register_exception_handlers(app)

# Same routes under both prefixes: /api/auth/... (as the assignment says)
# and /api/v1/auth/... (the API-versioning bonus, shown in Swagger).
app.include_router(api_router, prefix="/api/v1")
app.include_router(api_router, prefix="/api", include_in_schema=False)


@app.get("/health", tags=["Health"])
def health(db: Session = Depends(get_db)) -> dict[str, str]:
    db.execute(text("SELECT 1"))
    return {"status": "ok"}