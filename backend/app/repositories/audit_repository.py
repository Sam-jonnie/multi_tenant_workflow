from datetime import UTC, datetime, time, timedelta

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session, joinedload

from app.core.enums import AuditEntity
from app.models.audit_log import AuditLog
from app.models.organization import OrganizationMember
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
        active_member_ids = select(OrganizationMember.user_id).where(
            OrganizationMember.organization_id == org_id,
            OrganizationMember.is_active.is_(True),
        )
        stmt = select(AuditLog).where(
            or_(
                AuditLog.organization_id == org_id,  # tenant boundary
                and_(  # the one exception: account events of this org's members
                    AuditLog.organization_id.is_(None),
                    AuditLog.entity_type == AuditEntity.USER,
                    AuditLog.user_id.in_(active_member_ids),
                ),
            )
        )

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