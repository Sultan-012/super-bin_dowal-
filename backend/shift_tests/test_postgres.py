"""Opt-in real PostgreSQL verification in an isolated disposable schema."""
import os
import secrets
from uuid import uuid4
import pytest
from alembic import command
from alembic.config import Config as AlembicConfig
from sqlalchemy import create_engine,text
from sqlalchemy.engine import make_url
from shift_app.config import ROOT


@pytest.mark.postgres
def test_postgresql_migrations_decimal_and_immutable_triggers(monkeypatch):
    url=os.environ.get('TEST_POSTGRES_URL')
    if not url:
        pytest.skip('TEST_POSTGRES_URL is absent; no real PostgreSQL server was supplied.')
    parsed=make_url(url)
    if not parsed.drivername.startswith('postgresql+psycopg') or not (parsed.database or '').startswith('bin_doul_test'):
        pytest.fail('Use a disposable database whose name starts with bin_doul_test.')
    schema='test_'+secrets.token_hex(8)
    engine=create_engine(url,hide_parameters=True)
    with engine.begin() as connection:connection.execute(text('CREATE SCHEMA '+schema))
    scoped=parsed.update_query_dict({'options':'-csearch_path='+schema}).render_as_string(hide_password=False)
    monkeypatch.setenv('DATABASE_URL',scoped);monkeypatch.setenv('APP_ENV','development')
    monkeypatch.setenv('COOKIE_SECURE','false');monkeypatch.setenv('IDEMPOTENCY_SECRET','postgres-test-secret-over-thirty-two-characters')
    scoped_engine=create_engine(scoped,hide_parameters=True)
    try:
        command.upgrade(AlembicConfig(str(ROOT/'backend'/'shift_alembic.ini')),'head')
        with scoped_engine.begin() as connection:
            value=connection.scalar(text('SELECT initial_opening_cash FROM shift_settings WHERE id=1'))
            from decimal import Decimal
            assert value==Decimal('0.00')
            assert connection.scalar(text("SELECT data_type FROM information_schema.columns WHERE table_schema=:s AND table_name='shift_attachments' AND column_name='content'"),{'s':schema})=='bytea'
            connection.execute(text("INSERT INTO shift_audit_logs(action,entity_type,detail_json,created_at) VALUES('test','test','{}',CURRENT_TIMESTAMP)"))
        with pytest.raises(Exception):
            with scoped_engine.begin() as connection:connection.execute(text('DELETE FROM shift_audit_logs'))
    finally:
        scoped_engine.dispose()
        with engine.begin() as connection:connection.execute(text('DROP SCHEMA '+schema+' CASCADE'))
        engine.dispose()
