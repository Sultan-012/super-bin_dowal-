"""Keep append-only guards and classify their rejection as an integrity error."""
from alembic import op

revision = '20261030_04'
down_revision = '20261030_03'
branch_labels = None
depends_on = None


def upgrade():
    if op.get_bind().dialect.name == 'postgresql':
        op.execute("""CREATE OR REPLACE FUNCTION shift_forbid_financial_change() RETURNS trigger
        LANGUAGE plpgsql AS $$ BEGIN
        RAISE EXCEPTION 'Financial records are append-only; create a new version'
        USING ERRCODE = '23000'; END; $$""")


def downgrade():
    raise RuntimeError('Financial migrations are forward-only. Restore into a new database.')
