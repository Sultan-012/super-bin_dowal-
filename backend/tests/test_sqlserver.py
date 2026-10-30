"""Opt-in real SQL Server acceptance test. Requires a NEW, EMPTY *_acceptance_test DB.

No database is created or dropped by this test. Re-run in a new empty test DB.
"""
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4
import pytest
from alembic import command
from alembic.config import Config as AlembicConfig
from fastapi.testclient import TestClient
from sqlalchemy import inspect, select
from sqlalchemy.engine import make_url
from app.config import Config
from app.db import make_engine
from app.main import create_app
from app.models import User
from app.security import hasher
from .conftest import API, PASSWORD


@pytest.mark.sqlserver
@pytest.mark.skipif(not os.environ.get('TEST_SQLSERVER_URL'), reason='No TEST_SQLSERVER_URL / SQL Server connection available')
def test_real_sqlserver_migrations_persistence_concurrency(monkeypatch):
    url = os.environ['TEST_SQLSERVER_URL']
    parsed = make_url(url)
    assert parsed.drivername == 'mssql+pyodbc'
    assert parsed.database and parsed.database.lower().endswith('_acceptance_test'), 'Use a disposable *_acceptance_test database'
    engine = make_engine(url)
    assert not inspect(engine).get_table_names(), 'The opt-in test requires an EMPTY test database'
    monkeypatch.setenv('DATABASE_URL', url)
    monkeypatch.setenv('APP_ENV', 'test')
    command.upgrade(AlembicConfig(str(Path(__file__).resolve().parents[1] / 'alembic.ini')), 'head')
    app = create_app(Config(app_env='test', database_url=url, cookie_secure=False), engine)
    with app.state.factory() as db, db.begin():
        db.add(User(username='admin',full_name='اختبار SQL Server',role='admin',password_hash=hasher.hash(PASSWORD)))
    api = API(app)
    api.open()
    api.sales()
    api.debt('300', 'credit', sid=1)
    debt = api.debt('200')
    key = uuid4().hex
    def collect(_):
        client = TestClient(app)
        client.cookies.update(dict(api.client.cookies))
        return client.post('/api/payments', json=dict(debt_id=debt['id'],session_id=1,payment_date='2026-10-01',amount='200',payment_method='cash'),
                           headers={'Idempotency-Key':key,'X-CSRF-Token':api.client.headers['X-CSRF-Token']}).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert list(pool.map(collect,range(2))) == [200,200]
    assert len(api.detail()['payments']) == 1
    api.payment(debt['id'], '0.01', status=422)
    api.purchase()
    api.move()
    assert api.detail()['totals']['expected_cash'] == '1700.00'
    api.close('1650','عجز اختبار موثق')
    engine.dispose()
    restarted = create_app(Config(app_env='test',database_url=url,cookie_secure=False))
    again = API(restarted)
    assert again.detail()['snapshots'][0]['totals']['difference'] == '-50.00'
    next_day = again.open(None,'2026-10-02')
    assert next_day['opening_cash'] == '1650.00'
    again.write('/sessions/1/reopen',{'reason':'اختبار منع الترحيل'},status=409)
    assert again.get('/customers')[0]['name'] == 'عميل عربي'
    restarted.state.engine.dispose()
