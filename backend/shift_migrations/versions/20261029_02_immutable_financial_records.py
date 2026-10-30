"""Append-only financial versions, approvals and audit; initialize the store."""
from alembic import op
import sqlalchemy as sa
from decimal import Decimal

revision='20261029_02'
down_revision='20261029_01'
branch_labels=None
depends_on=None

IMMUTABLE=('shift_versions','shift_entries','shift_approvals','shift_audit_logs','shift_notification_events')


def upgrade():
    settings=sa.table('shift_settings',sa.column('id',sa.Integer),sa.column('revision',sa.Integer),
                     sa.column('store_name',sa.String),sa.column('currency',sa.String),
                     sa.column('timezone',sa.String),sa.column('initial_opening_cash',sa.Numeric(18,2)))
    op.bulk_insert(settings,[{'id':1,'revision':0,'store_name':'سوبر ماركت بن دول',
                             'currency':'YER','timezone':'Asia/Aden','initial_opening_cash':Decimal('0.00')}])
    dialect=op.get_bind().dialect.name
    if dialect=='postgresql':
        op.execute("""CREATE FUNCTION shift_forbid_financial_change() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN RAISE EXCEPTION 'Financial records are append-only; create a new version'; END; $$""")
        for table in IMMUTABLE:
            op.execute(f'CREATE TRIGGER protect_{table} BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION shift_forbid_financial_change()')
    elif dialect=='sqlite':
        for table in IMMUTABLE:
            for action in ('UPDATE','DELETE'):
                op.execute(f"CREATE TRIGGER protect_{table}_{action.lower()} BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT,'Financial records are append-only'); END")
    else:
        raise RuntimeError('This migration supports PostgreSQL and test SQLite only.')


def downgrade():
    raise RuntimeError('Financial migrations are forward-only. Restore a backup into a new database.')
