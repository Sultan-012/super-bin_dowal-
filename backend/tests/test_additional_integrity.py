import pytest
import subprocess
import sys
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from .conftest import API, PASSWORD


def test_cash_collection_affects_collection_day_not_original_debt_day(api):
    api.open()
    api.sales('100', '0')
    d = api.debt('100','credit',sid=1)
    api.close('500')
    api.open(None, '2026-10-02')
    api.write('/payments',dict(debt_id=d['id'],session_id=2,payment_date='2026-10-02',amount='60',payment_method='cash'))
    assert api.detail(1)['totals']['expected_cash'] == '500.00'
    assert api.detail(2)['totals']['expected_cash'] == '560.00'
    assert api.detail(2)['totals']['total_sales'] == '0.00'


def test_shortages_surpluses_separated_without_summing_balances(api):
    api.open()
    api.close('450','عجز اليوم الأول')
    api.open(None,'2026-10-02')
    api.write('/sessions/2/close',dict(actual_cash='480',expected_version=1,note='فائض اليوم الثاني'))
    r=api.get('/reports?start=2026-10-01&end=2026-10-02')
    assert r['totals']['total_shortages']=='50.00'
    assert r['totals']['total_surpluses']=='30.00'
    assert r['totals']['net_difference']=='-20.00'
    assert r['balance_at_end']['opening_cash']=='450.00'
    assert 'opening_cash' not in r['totals']


def test_closing_snapshot_is_immutable(env,api):
    api.open()
    api.close('500')
    with pytest.raises(IntegrityError):
        with env.state.factory() as db,db.begin():
            db.execute(text("UPDATE closing_snapshots SET note='changed'"))


def test_closed_session_requires_nonnull_count_version_in_database(env,api):
    api.open()
    with pytest.raises(IntegrityError):
        with env.state.factory() as db, db.begin():
            db.execute(text("UPDATE cash_sessions SET status='closed', actual_cash=500, closed_at=CURRENT_TIMESTAMP, closed_by=1, count_version=NULL WHERE id=1"))


def test_disabled_user_and_changed_role_revoke_access(env,api):
    employee=API(env,'employee')
    user=next(u for u in api.get('/users') if u['username']=='employee')
    api.write(f"/users/{user['id']}",dict(full_name=user['full_name'],role='employee',is_active=False),method='put')
    assert employee.client.get('/api/sessions').status_code==401
    api.write('/users/1',dict(full_name='مدير',role='employee',is_active=True),method='put',status=422)


def test_bank_repayment_and_purchase_method_validation(api):
    api.open()
    d=api.debt('200')
    api.payment(d['id'],'200','bank')
    assert api.detail()['totals']['expected_cash']=='500.00'
    assert api.detail()['totals']['bank_collections']=='200.00'
    api.purchase('30','card',True,status=422)


def test_currency_cannot_change_after_opening_debt(api):
    api.debt('100')
    api.write('/settings',dict(store_name='متجر',currency='USD',timezone='Asia/Aden'),method='put',status=422)


def test_no_cancel_generated_effect_without_source(api):
    api.open()
    api.purchase('20')
    mid=api.detail()['movements'][0]['id']
    api.write(f'/records/movements/{mid}/cancel',dict(reason='تعديل منفرد غير مسموح'),status=422)
    assert api.detail()['totals']['expected_cash']=='480.00'


def test_request_requires_idempotency_key(api):
    assert api.client.post('/api/customers',json={'name':'عميل'}).status_code==422


def test_user_password_whitespace_is_preserved(env,api):
    password='  a long password  '
    api.write('/users',dict(username='spaceuser',full_name='حساب',role='employee',password=password))
    result=api.client.post('/api/auth/login',json=dict(username='spaceuser',password=password))
    assert result.status_code==200


def test_persistence_in_a_separate_python_process(env,api):
    api.open()
    api.move('17.35')
    code = """
from fastapi.testclient import TestClient
from app.main import create_app
from app.config import Config
from app.security import CSRF_COOKIE
from tests.conftest import PASSWORD
app=create_app(Config(cookie_secure=False))
with TestClient(app) as client:
    result=client.post('/api/auth/login',json={'username':'admin','password':PASSWORD})
    assert result.status_code==200
    result=client.get('/api/sessions/1')
    assert result.status_code==200
    print(result.json()['totals']['expected_cash'])
"""
    result=subprocess.run([sys.executable,'-c',code],check=True,capture_output=True,text=True,timeout=30)
    assert result.stdout.strip()=='482.65'
