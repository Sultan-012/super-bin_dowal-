from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from app import services
from app.config import Config
from app.main import create_app
from app.models import AuditLog, CashMovement, ClosingSnapshot, DebtPayment, Purchase
from .conftest import API, PASSWORD


@pytest.mark.parametrize('actual,state,difference', [('1650','shortage','-50.00'),('1750','surplus','50.00'),('1700','balanced','0.00')])
def test_backend_required_example_and_snapshot(example, actual, state, difference):
    api, debt = example
    totals = api.detail()['totals']
    assert totals['cash_sales'] == '1500.00'
    assert totals['expected_cash'] == '1700.00'
    result = api.close(actual, 'سبب فرق الجرد' if state != 'balanced' else '')
    assert result['totals']['reconciliation_status'] == state
    assert result['totals']['difference'] == difference
    assert len(result['snapshots']) == 1
    assert result['snapshots'][0]['totals']['expected_cash'] == '1700.00'
    report = api.get('/reports?start=2026-10-01&end=2026-10-01')
    assert report['totals']['net_difference'] == difference


def test_empty_count_cannot_close(example):
    api, _ = example
    assert api.detail()['totals']['reconciliation_message'] == 'بانتظار الجرد'
    api.close(None, status=422)
    assert api.detail()['status'] == 'open'


def test_difference_requires_note(example):
    api, _ = example
    api.close('1650', status=422)
    assert api.detail()['snapshots'] == []


def test_card_collection_no_cash_or_new_sales(example):
    api, debt = example
    p = api.detail()['payments'][0]
    api.write(f"/records/payments/{p['id']}/cancel", {'reason': 'تصحيح طريقة الدفع'})
    api.payment(debt['id'], method='card')
    r = api.detail()['totals']
    assert r['expected_cash'] == '1500.00'
    assert r['total_sales'] == '3000.00'
    assert r['pos_sales'] == '1200.00'
    assert r['card_collections'] == '200.00'
    assert api.get(f"/customers/{debt['customer_id']}/statement")['outstanding'] == '300.00'


def test_opening_debt_does_not_increase_sales(api):
    api.open()
    api.debt('900')
    r = api.detail()['totals']
    assert r['new_credit_sales'] == r['total_sales'] == '0.00'
    assert r['expected_cash'] == '500.00'


def test_credit_causing_negative_cash_rejected_atomically(api):
    api.open()
    api.sales('100', '80')
    cid = api.customer()
    api.write('/debts', dict(customer_id=cid, debt_date='2026-10-01', amount='30', kind='credit', session_id=1), status=422)
    assert api.detail()['debts'] == []
    assert api.detail()['totals']['cash_sales'] == '20.00'
    api.sales('50', '80', status=422)
    assert api.detail()['total_sales'] == '100.00'


def test_total_less_than_existing_credit_plus_pos_rejected(api):
    api.open()
    api.sales('100', '50')
    api.debt('30', 'credit', sid=1)
    api.sales('70', '50', status=422)
    assert api.detail()['total_sales'] == '100.00'


@pytest.mark.parametrize('method,drawer', [('card',False), ('bank',False), ('cash',False)])
def test_nondrawer_purchase_does_not_reduce_cash(api, method, drawer):
    api.open()
    api.purchase('100', method, drawer)
    assert api.detail()['totals']['expected_cash'] == '500.00'
    assert api.detail()['totals']['cash_purchases'] == '0.00'


def test_cash_refund_exactly_once_and_idempotency(api):
    api.open()
    key = uuid4().hex
    first = api.move('50', 'refund', key=key)
    second = api.move('50', 'refund', key=key)
    assert first == second
    assert api.detail()['totals']['expected_cash'] == '450.00'
    assert len(api.detail()['movements']) == 1
    api.move('60', 'refund', key=key, status=409)


def test_repayment_retry_and_overpayment(api):
    api.open()
    d = api.debt('200')
    key = uuid4().hex
    assert api.payment(d['id'], '150', key=key) == api.payment(d['id'], '150', key=key)
    api.payment(d['id'], '51', status=422)
    assert len(api.detail()['payments']) == 1
    assert len(api.detail()['movements']) == 1
    assert api.detail()['totals']['total_sales'] == '0.00'
    st = api.get(f"/customers/{d['customer_id']}/statement")
    assert st['outstanding'] == '50.00'
    assert st['debts'][0]['debt_status'] == 'partial'
    api.payment(d['id'], '50')
    assert api.get(f"/customers/{d['customer_id']}/statement")['debts'][0]['debt_status'] == 'paid'


def test_source_and_movement_rollback_together(api, monkeypatch):
    api.open()
    d = api.debt('200')
    def broken(*args, **kwargs):
        raise services.RuleError('اختبار فشل كتابة الحركة', 503)
    monkeypatch.setattr(services, 'generated_movement', broken)
    api.payment(d['id'], status=503)
    assert api.detail()['payments'] == []
    assert api.detail()['movements'] == []
    assert api.get(f"/customers/{d['customer_id']}/statement")['outstanding'] == '200.00'


def test_no_transactions_after_close_and_retry_original_works(api):
    api.open()
    key = uuid4().hex
    original = api.move('10', key=key)
    api.close('490')
    assert api.move('10', key=key) == original
    api.move('10', status=409)
    api.purchase(status=409)
    api.sales('100', '0', status=409)


@pytest.mark.parametrize('amount', ['-1', '0', 'NaN', 'Infinity', '0.001', '10000000000000000', 0.1, True, 'invalid'])
def test_invalid_monetary_amounts(api, amount):
    api.open()
    api.move(amount, status=422)
    assert api.detail()['movements'] == []


def test_authorization_csrf_and_origin(env, api):
    anon = TestClient(env)
    assert anon.get('/api/sessions').status_code == 401
    assert anon.post('/api/movements', json={}).status_code == 401
    employee = API(env, 'employee')
    assert employee.client.get('/api/users').status_code == 403
    assert employee.client.get('/api/reports?start=2026-10-01&end=2026-10-01').status_code == 403
    employee.write('/users', dict(username='newuser', full_name='اسم', role='admin', password=PASSWORD), status=403)
    employee.write('/settings', dict(store_name='اسم', currency='SAR', timezone='UTC'), method='put', status=403)
    assert anon.post('/api/auth/login', json={'username':'admin','password':PASSWORD}, headers={'Origin':'https://evil.example'}).status_code == 403
    csrf = api.client.headers.pop('X-CSRF-Token')
    api.write('/customers', {'name':'عميل'}, status=403)
    api.client.headers['X-CSRF-Token'] = csrf


def test_employee_can_record_but_not_cancel_or_reopen(env, api):
    api.open()
    employee = API(env, 'employee')
    m = employee.move('10')
    employee.write(f"/records/movements/{m['id']}/cancel", {'reason':'تصحيح'}, status=403)
    employee.write('/debts', dict(customer_id=api.customer(), kind='opening', debt_date='2026-10-01', amount='10'), status=403)
    api.close('490')
    employee.write('/sessions/1/reopen', {'reason':'تصحيح'}, status=403)


def test_persistence_after_dispose_and_restart(env, api):
    api.open()
    api.move('17.35')
    env.state.engine.dispose()
    new_app = create_app(env.state.config)
    new_api = API(new_app)
    assert new_api.detail()['totals']['expected_cash'] == '482.65'
    assert new_api.detail()['movements'][0]['amount'] == '17.35'
    new_app.state.engine.dispose()


def test_carry_actual_not_expected_and_reopen_dependency(api):
    api.open()
    api.close('450', 'عجز موثق')
    api.write('/sessions/1/reopen', {'reason':'مراجعة قبل اليوم التالي'})
    assert api.detail()['totals']['count_stale']
    api.close('450', 'عجز موثق بعد المراجعة')
    result = api.open(None, '2026-10-02')
    assert result['opening_cash'] == '450.00'
    api.write('/sessions/1/reopen', {'reason':'لا يسمح بعد الترحيل'}, status=409)
    api.write('/sessions', {'business_date':'2026-10-03'}, status=409)


def test_count_stale_and_optimistic_close(api):
    api.open()
    api.write('/sessions/1/count', {'actual_cash':'500','expected_version':1}, method='put')
    api.move('10')
    result = api.detail()['totals']
    assert result['count_stale'] and result['actual_cash'] == '500.00'
    assert result['reconciliation_message'] == 'بانتظار الجرد'
    api.write('/sessions/1/close', {'actual_cash':'500','expected_version':1}, status=409)


def test_concurrent_repayments_prevent_overcollection(env, api):
    api.open()
    d = api.debt('200')
    def collect(_):
        client = TestClient(env)
        client.cookies.update(dict(api.client.cookies))
        return client.post('/api/payments', json=dict(debt_id=d['id'], session_id=1, payment_date='2026-10-01', amount='150', payment_method='cash'),
                           headers={'Idempotency-Key':uuid4().hex,'X-CSRF-Token':api.client.headers['X-CSRF-Token']}).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(collect, range(2)))
    assert sorted(statuses) == [200, 422]
    assert len(api.detail()['payments']) == 1


def test_concurrent_same_request_creates_one_expense(env, api):
    api.open()
    key = uuid4().hex
    def save(_):
        client = TestClient(env)
        client.cookies.update(dict(api.client.cookies))
        return client.post('/api/movements', json=dict(session_id=1, movement_date='2026-10-01', amount='10', kind='expense', description='نفس العملية'),
                           headers={'Idempotency-Key':key,'X-CSRF-Token':api.client.headers['X-CSRF-Token']}).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert list(pool.map(save, range(2))) == [200, 200]
    assert len(api.detail()['movements']) == 1


def test_concurrent_close_and_add_are_serialized(env, api):
    api.open()
    def perform(which):
        client = TestClient(env)
        client.cookies.update(dict(api.client.cookies))
        path, data = ('/api/sessions/1/close',dict(actual_cash='500',expected_version=1)) if which == 'close' else ('/api/movements',dict(session_id=1,movement_date='2026-10-01',amount='10',kind='expense',description='مصروف'))
        return which, client.post(path, json=data, headers={'Idempotency-Key':uuid4().hex,'X-CSRF-Token':api.client.headers['X-CSRF-Token']}).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        result = dict(pool.map(perform, ['close','move']))
    assert sorted(result.values()) == [200, 409]
    detail = api.detail()
    assert (detail['status'] == 'closed' and not detail['movements']) or (detail['status'] == 'open' and len(detail['movements']) == 1)


def test_unique_generated_movement_constraint(api, env):
    api.open()
    p = api.purchase('10')
    with pytest.raises(IntegrityError):
        with env.state.factory() as db, db.begin():
            m = db.scalar(select(CashMovement).where(CashMovement.purchase_id == p['id']))
            db.add(CashMovement(session_id=1,movement_date=m.movement_date,kind='purchase',amount=m.amount,description='مكرر',responsible_user_id=1,created_by=1,purchase_id=p['id']))
            db.flush()


def test_cancel_preserves_source_and_audit(api, env):
    api.open()
    p = api.purchase('10')
    api.write(f"/records/purchases/{p['id']}/cancel", {'reason':'فاتورة مكررة'})
    assert api.detail()['totals']['expected_cash'] == '500.00'
    assert api.detail()['purchases'][0]['cancelled_at']
    assert api.detail()['movements'][0]['cancelled_at']
    logs = api.get('/audit')
    assert any(a['action'] == 'cancel_purchases' and a['reason'] == 'فاتورة مكررة' for a in logs)
    with pytest.raises(IntegrityError):
        with env.state.factory() as db, db.begin():
            db.execute(text('DELETE FROM audit_logs'))


def test_csv_arabic_bom_and_nonduplicated_reports(example):
    api, _ = example
    report = api.get('/reports?start=2026-10-01&end=2026-10-01')
    assert report['totals']['cash_purchases'] == '400.00'
    assert len(report['recent_transactions']) == 5
    csv = api.client.get('/api/reports/export.csv?start=2026-10-01&end=2026-10-01')
    assert csv.content.startswith(b'\xef\xbb\xbf')
    assert 'إجمالي المبيعات' in csv.content.decode('utf-8-sig')
    assert 'opening_cash' not in report['totals']


def test_session_duplicate_and_invalid_dates(api):
    api.open()
    api.write('/sessions', {'business_date':'2026-10-01','opening_cash':'0'}, status=409)
    api.write('/movements', dict(session_id=1,movement_date='2026-10-02',amount='10',kind='expense',description='خطأ'), status=422)


def test_password_not_in_users_audit_or_idempotency_response(api):
    user = api.write('/users', dict(username='staff2',full_name='موظف',role='employee',password=PASSWORD))
    assert 'password' not in str(user)
    assert PASSWORD not in str(api.get('/audit'))


def test_login_throttle_and_logout(env, api):
    client = TestClient(env)
    for _ in range(5):
        assert client.post('/api/auth/login', json={'username':'nobody','password':'wrong'}).status_code == 401
    assert client.post('/api/auth/login', json={'username':'nobody','password':'wrong'}).status_code == 429
    assert api.client.post('/api/auth/logout').status_code == 200
    assert api.client.get('/api/auth/me').status_code == 401
