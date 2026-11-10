from typing import Any

from sqlalchemy.orm import Session

from app.core.context import OrgContext, RequestInfo
from app.core.enums import AuditAction, AuditEntity
from app.models.audit_log import AuditLog
from app.repositories.audit_repository import AuditRepository
from app.schemas.audit import AuditListQuery


class AuditService:
    def __init__(self, db: Session, request_info: RequestInfo) -> None:
        self.repo = AuditRepository(db)
        self.request_info = request_info

    def log(
        self,
        action: AuditAction,
        *,
        entity_type: AuditEntity,
        entity_id: int | None = None,
        user_id: int | None = None,
        organization_id: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AuditLog:
        """Queue an audit row. It does NOT commit: it is saved (or discarded)
        together with the business change that caused it."""
        entry = AuditLog(
            user_id=user_id,
            organization_id=organization_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            ip_address=self.request_info.ip_address,
            user_agent=self.request_info.user_agent,
            meta=metadata or {},
        )
        return self.repo.add(entry)

    def list_logs(self, ctx: OrgContext, query: AuditListQuery) -> tuple[list[AuditLog], int]:
        return self.repo.list_for_org(ctx.organization.id, query)