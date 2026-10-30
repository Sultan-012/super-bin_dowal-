"""Allow several daily shifts and optional invoice references/documents.

Revision ID: 20261030_03
Revises: 20261029_02

Financial versions are append-only. We only relax validation constraints and the
one-shift-per-employee-date uniqueness; existing records are never rewritten.
"""
from alembic import op

revision = '20261030_03'
down_revision = '20261029_02'
branch_labels = None
depends_on = None


def upgrade():
    dialect = op.get_bind().dialect.name
    if dialect not in ('postgresql', 'sqlite'):
        raise RuntimeError('Only PostgreSQL and test SQLite are supported.')
    mode = 'always' if dialect == 'sqlite' else 'auto'
    with op.batch_alter_table('shifts', recreate=mode) as batch:
        batch.drop_constraint('uq_employee_shift_date', type_='unique')

    with op.batch_alter_table('shift_entries', recreate=mode) as batch:
        batch.drop_constraint('ck_purchase_invoice_required', type_='check')
        batch.create_check_constraint('ck_purchase_invoice_required',
            "kind <> 'purchase' OR length(trim(description)) > 0")
        batch.drop_constraint('ck_debt_invoice_required', type_='check')
        batch.create_check_constraint('ck_debt_invoice_required',
            "kind <> 'debt' OR (length(trim(description)) > 0 AND invoice_total >= amount AND invoice_total IS NOT NULL)")
        batch.drop_constraint('ck_bank_current_invoice', type_='check')

    if dialect == 'sqlite':
        # SQLite batch recreation drops old triggers along with the old table.
        # Restore the append-only protection created in 20261029_02.
        for action in ('UPDATE', 'DELETE'):
            op.execute(
                'CREATE TRIGGER protect_shift_entries_' + action.lower() +
                ' BEFORE ' + action + ' ON shift_entries BEGIN '
                "SELECT RAISE(ABORT,'Financial records are append-only'); END"
            )


def downgrade():
    # New production data may intentionally have blank invoice numbers or several
    # shifts on one day. Reinstating the old checks would lose or reject records.
    raise RuntimeError('This financial schema migration is forward-only. Restore an earlier backup in a NEW database.')
