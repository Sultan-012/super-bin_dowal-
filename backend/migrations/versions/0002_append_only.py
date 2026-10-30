"""Protect audit logs and approved closing snapshots from UPDATE and DELETE."""
from alembic import op

revision = '0002'
down_revision = '0001'
branch_labels = depends_on = None


def upgrade():
    dialect = op.get_context().dialect.name
    for table in ['audit_logs', 'closing_snapshots']:
        if dialect == 'mssql':
            op.execute(f"CREATE TRIGGER tr_{table}_immutable ON {table} INSTEAD OF UPDATE, DELETE AS BEGIN SET NOCOUNT ON; THROW 51000, 'Approved records are append-only', 1; END")
        elif dialect == 'sqlite':
            for action in ['UPDATE', 'DELETE']:
                op.execute(f"CREATE TRIGGER tr_{table}_{action.lower()} BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT, 'Approved records are append-only'); END")


def downgrade():
    dialect = op.get_context().dialect.name
    for table in ['audit_logs', 'closing_snapshots']:
        if dialect == 'mssql':
            op.execute(f'DROP TRIGGER tr_{table}_immutable')
        elif dialect == 'sqlite':
            for action in ['update', 'delete']:
                op.execute(f'DROP TRIGGER tr_{table}_{action}')
