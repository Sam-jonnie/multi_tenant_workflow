"""audit log append only"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'e7b198fc7e5e'
down_revision: Union[str, Sequence[str], None] = '1132ca5e4d62'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FUNCTION_SQL = """
CREATE OR REPLACE FUNCTION prevent_audit_log_changes() RETURNS trigger AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'audit_logs is append-only (DELETE is not allowed)';
    END IF;

    -- UPDATE: the only change allowed is the foreign key ON DELETE SET NULL
    IF NEW.id IS DISTINCT FROM OLD.id
       OR NEW.action IS DISTINCT FROM OLD.action
       OR NEW.entity_type IS DISTINCT FROM OLD.entity_type
       OR NEW.entity_id IS DISTINCT FROM OLD.entity_id
       OR NEW.ip_address IS DISTINCT FROM OLD.ip_address
       OR NEW.user_agent IS DISTINCT FROM OLD.user_agent
       OR NEW.metadata IS DISTINCT FROM OLD.metadata
       OR NEW.created_at IS DISTINCT FROM OLD.created_at
       OR (NEW.user_id IS NOT NULL AND NEW.user_id IS DISTINCT FROM OLD.user_id)
       OR (NEW.organization_id IS NOT NULL
           AND NEW.organization_id IS DISTINCT FROM OLD.organization_id)
    THEN
        RAISE EXCEPTION 'audit_logs is append-only (UPDATE is not allowed)';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""


def upgrade() -> None:
    op.execute(FUNCTION_SQL)
    op.execute(
        "CREATE TRIGGER audit_logs_append_only "
        "BEFORE UPDATE OR DELETE ON audit_logs "
        "FOR EACH ROW EXECUTE FUNCTION prevent_audit_log_changes()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS audit_logs_append_only ON audit_logs")
    op.execute("DROP FUNCTION IF EXISTS prevent_audit_log_changes()")
