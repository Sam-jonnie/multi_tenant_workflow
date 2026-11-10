from datetime import UTC, datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.audit_log import AuditLog
from app.repositories.query_utils import order_by_clauses, paginate
from app.schemas.audit import AuditListQuery


class AuditRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, entry: AuditLog) -> AuditLog:
        self.db.add(entry)  # no flush, no commit: the caller's transaction owns this row
        return entry

    # There is deliberately no update() and no delete() in this class.

    def list_for_org(self, org_id: int, query: AuditListQuery) -> tuple[list[AuditLog], int]:
        stmt = select(AuditLog).where(AuditLog.organization_id == org_id)  # tenant boundary

        if query.action is not None:
            stmt = stmt.where(AuditLog.action == query.action)
        if query.entity_type is not None:
            stmt = stmt.where(AuditLog.entity_type == query.entity_type)
        if query.entity_id is not None:
            stmt = stmt.where(AuditLog.entity_id == query.entity_id)
        if query.user_id is not None:
            stmt = stmt.where(AuditLog.user_id == query.user_id)
        if query.created_from:
            start = datetime.combine(query.created_from, time.min, tzinfo=UTC)
            stmt = stmt.where(AuditLog.created_at >= start)
        if query.created_to:
            end = datetime.combine(query.created_to + timedelta(days=1), time.min, tzinfo=UTC)
            stmt = stmt.where(AuditLog.created_at < end)

        return paginate(
            self.db,
            stmt,
            query,
            order_by=order_by_clauses(AuditLog.created_at, query.sort_order, AuditLog.id),
            options=[joinedload(AuditLog.user)],
        )