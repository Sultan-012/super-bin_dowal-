from pathlib import Path
from uuid import uuid4
import pytest
from alembic import command
from alembic.config import Config as AlembicConfig
from fastapi.testclient import TestClient
from app.config import Config
from app.db import make_engine
from app.main import create_app
from app.models import User
from app.security import CSRF_COOKIE, hasher

PASSWORD = 'Test-password-only-2026!'


@pytest.fixture
def env(tmp_path, monkeypatch):
    url = 'sqlite:///' + str(tmp_path / 'persistent-test.db')
    monkeypatch.setenv('APP_ENV', 'test')
    monkeypatch.setenv('DATABASE_URL', url)
    cfg = AlembicConfig(str(Path(__file__).resolve().parents[1] / 'alembic.ini'))
    command.upgrade(cfg, 'head')
    app = create_app(Config(app_env='test', database_url=url, cookie_secure=False))
    with app.state.factory() as db, db.begin():
        db.add_all([User(username='admin', full_name='مدير الاختبار', role='admin', password_hash=hasher.hash(PASSWORD)),
                    User(username='employee', full_name='موظف الاختبار', role='employee', password_hash=hasher.hash(PASSWORD))])
    yield app
    app.state.engine.dispose()


class API:
    def __init__(self, app, username='admin'):
        self.app = app
        self.client = TestClient(app)
        result = self.client.post('/api/auth/login', json={'username': username, 'password': PASSWORD})
        assert result.status_code == 200, result.text
        self.client.headers['X-CSRF-Token'] = self.client.cookies[CSRF_COOKIE]

    def get(self, path):
        r = self.client.get('/api' + path)
        assert r.status_code == 200, r.text
        return r.json()

    def write(self, path, data, *, method='post', key=None, status=200):
        r = self.client.request(method, '/api' + path, json=data, headers={'Idempotency-Key': key or uuid4().hex})
        assert r.status_code == status, r.text
        return r.json()

    def open(self, opening='500.00', day='2026-10-01'):
        return self.write('/sessions', dict(business_date=day, opening_cash=opening))

    def detail(self, sid=1):
        return self.get(f'/sessions/{sid}')

    def sales(self, total='3000.00', pos='1200.00', sid=1, **kwargs):
        v = self.detail(sid)['version']
        return self.write(f'/sessions/{sid}/sales', dict(total_sales=total, pos_sales=pos, expected_version=v), method='put', **kwargs)

    def customer(self):
        return self.write('/customers', {'name': 'عميل عربي', 'phone': '777123456'})['id']

    def debt(self, amount='500', kind='opening', cid=None, sid=None):
        return self.write('/debts', dict(customer_id=cid or self.customer(), debt_date='2026-10-01', amount=amount, kind=kind, session_id=sid))

    def payment(self, did, amount='200', method='cash', **kwargs):
        return self.write('/payments', dict(debt_id=did, session_id=1, payment_date='2026-10-01', amount=amount, payment_method=method), **kwargs)

    def purchase(self, amount='400', method='cash', drawer=True, **kwargs):
        return self.write('/purchases', dict(session_id=1, purchase_date='2026-10-01', description='مشتريات', amount=amount, payment_method=method, from_drawer=drawer), **kwargs)

    def move(self, amount='100', kind='expense', **kwargs):
        return self.write('/movements', dict(session_id=1, movement_date='2026-10-01', description='حركة صندوق', amount=amount, kind=kind), **kwargs)

    def close(self, actual=None, note='', **kwargs):
        return self.write('/sessions/1/close', dict(actual_cash=actual, expected_version=self.detail()['version'], note=note), **kwargs)


@pytest.fixture
def api(env):
    return API(env)


@pytest.fixture
def example(api):
    api.open()
    api.sales()
    api.debt('300', 'credit', sid=1)
    d = api.debt('500')
    api.payment(d['id'])
    api.purchase()
    api.move()
    return api, d
