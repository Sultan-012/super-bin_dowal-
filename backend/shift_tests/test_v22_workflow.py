"""v2.2 end-to-end acceptance tests: manager confirmation without a cash count."""
import json
from datetime import date
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from shift_app.models import (Approval, AuditLog, CustomerDebt, DebtPayment,
                              Entry, NotificationEvent, Shift, ShiftVersion)
from .conftest import attachment, details, line, payload, send, submit


def confirm(admin, identifier=1, version=1, note='تمت المراجعة', key=None):
    return send(admin, f'/api/shifts/{identifier}/confirm',
                dict(expected_version=version, confirmed=True, note=note), key=key)


def test_admin_confirmation_is_explicit_and_never_computes_cash_balance(system):
    app, _, admin, employee, _ = system
    submit(employee, payload())
    result = confirm(admin, note='اطلعت على الفواتير')
    assert result.status_code == 200, result.text
    assert result.json()['confirmation_mode'] == 'administrative'
    detail = details(admin)
    assert detail['approved'] is True and detail['shift']['approved_version'] == 1
    assert detail['version']['number'] == 1  # no fabricated counted-cash version
    assert 'pos_sales' not in detail['version']
    assert 'retained_cash' not in detail['version']
    for forbidden in ('difference', 'shortage', 'surplus', 'expected_cash', 'new_debts', 'account_bank'):
        assert forbidden not in detail['totals']
    assert 'totals_json' not in detail['approval']
    assert detail['totals']['status'] == 'confirmed'
    assert detail['totals']['financial_variance_calculated'] is False
    with app.state.factory() as db:
        approval = db.scalar(select(Approval))
        assert approval is not None
        stored = json.loads(approval.totals_json)
        assert stored['confirmation_mode'] == 'administrative'
        assert stored['difference'] is None and stored['shortage'] is None
        assert db.scalar(select(AuditLog).where(AuditLog.action == 'shift.confirmed')) is not None
        assert db.scalar(select(CustomerDebt.id)) is None


def test_confirm_requires_version_acknowledgement_and_admin(system):
    _, _, admin, employee, other = system
    submit(employee, payload())
    for body in (dict(expected_version=1, confirmed=False),
                 dict(expected_version=1),
                 dict(expected_version=0, confirmed=True)):
        assert send(admin, '/api/shifts/1/confirm', body).status_code == 422
    assert send(employee, '/api/shifts/1/confirm', {'expected_version': 1, 'confirmed': True}).status_code == 403
    assert send(other, '/api/shifts/1/confirm', {'expected_version': 1, 'confirmed': True}).status_code == 403
    assert confirm(admin, version=5).status_code == 409
    assert confirm(admin).status_code == 200
    assert confirm(admin).status_code == 409
    assert admin.get('/api/shifts?status=confirmed').json()[0]['approved'] is True
    assert admin.get('/api/shifts?status=pending').json() == []


def test_confirm_idempotency_and_immutable_approval(system):
    app, _, admin, employee, _ = system
    submit(employee, payload())
    key = str(uuid4())
    a = confirm(admin, key=key)
    b = confirm(admin, key=key)
    assert a.status_code == b.status_code == 200 and a.json() == b.json()
    assert confirm(admin, note='different', key=key).status_code == 409
    with app.state.factory() as db:
        assert len(list(db.scalars(select(Approval)))) == 1
        with pytest.raises(IntegrityError):
            db.execute(text('DELETE FROM shift_approvals'))
        db.rollback()


def test_legacy_invoice_and_debt_paths_are_unavailable(system):
    _, _, admin, employee, _ = system
    submit(employee, payload())
    for path in ('/api/invoices', '/api/customers', '/api/customers/1', '/api/reports/months'):
        assert admin.get(path).status_code in (404, 405)
    for path in ('/api/shifts/1/reconcile', '/api/shifts/1/preview',
                 '/api/invoices/1/match', '/api/customers/opening-debts'):
        assert send(admin, path, {}).status_code in (404, 405)


def test_new_debt_and_old_account_bank_are_rejected_at_api(system):
    app, _, _, employee, _ = system
    for entry in (line('debt', description='رصيد غير مسدد', invoice_total='100'),
                  line('bank', reference='OLD-ACCOUNT', purpose='customer_account')):
        data = payload()
        data['entries'] = [entry]
        assert send(employee, '/api/shifts', data).status_code == 422
    with app.state.factory() as db:
        assert db.scalar(select(Shift.id)) is None


def test_purchase_and_bank_optional_invoice_and_attachment(system):
    app, _, admin, employee, _ = system
    purchase_file, bank_file = attachment(employee), attachment(employee)
    data = payload()
    data['entries'] = [
        line('purchase', name='المورد الأول', description='رز وزيت', attachment_id=purchase_file),
        line('purchase', name='المورد الثاني', description='سكر'),
        line('bank', name='المودع', reference='BN-2026-0001', purpose='current_shift', attachment_id=bank_file),
    ]
    submit(employee, data)
    entries = details(admin)['entries']
    assert len(entries) == 3 and all(e['invoice_number'] == '' for e in entries)
    assert {e['attachment_id'] for e in entries if e['attachment_id']} == {purchase_file, bank_file}
    assert all(admin.get('/api/attachments/' + file_id).status_code == 200 for file_id in [purchase_file, bank_file])
    assert confirm(admin).status_code == 200
    with app.state.factory() as db:
        assert not list(db.scalars(select(CustomerDebt)))
        assert not list(db.scalars(select(DebtPayment)))


def test_multiple_shifts_one_day_confirm_in_any_order_without_cash_chain(system):
    _, _, admin, employee, _ = system
    submit(employee, payload())
    submit(employee, payload())
    assert len(admin.get('/api/shifts?month=2026-09').json()) == 2
    assert confirm(admin, identifier=2).status_code == 200
    assert confirm(admin, identifier=1).status_code == 200
    assert details(admin, 1)['shift']['previous_shift_id'] is None
    assert details(admin, 2)['shift']['previous_shift_id'] is None
    assert admin.get('/api/reports?month=2026-09').json()['totals']['approved'] == 2


def test_corrected_shift_needs_new_confirm_without_rewriting_prior_snapshot(system):
    app, _, admin, employee, _ = system
    data = payload()
    submit(employee, data)
    assert confirm(admin).status_code == 200
    revision = {**data, 'expected_version': 1, 'reason': 'تصحيح مبلغ الإيداع', 'deposit_amount': '950.00'}
    response = send(admin, '/api/shifts/1', revision, method='PUT')
    assert response.status_code == 200, response.text
    assert details(admin)['approved'] is False
    assert confirm(admin, version=1).status_code == 409
    assert confirm(admin, version=2).status_code == 200
    with app.state.factory() as db:
        approvals = list(db.scalars(select(Approval)))
        assert len(approvals) == 2
        assert [a.version_id for a in approvals] == [1, 2]


def test_legacy_debt_records_cannot_be_confirmed_or_edited_in_new_workflow(system):
    app, _, admin, employee, _ = system
    submit(employee, payload())
    with app.state.factory() as db, db.begin():
        ver = db.scalar(select(ShiftVersion))
        db.add(Entry(version_id=ver.id, line_key=str(uuid4()), kind='debt',
                     name='مدين سابق', amount=Decimal('100'),
                     description='سجل تاريخي', invoice_total=Decimal('100'), invoice_number='L-1'))
    assert confirm(admin).status_code == 409
    original = payload()
    original.update(expected_version=1, reason='تصحيح جرد', entries=[])
    assert send(admin, '/api/shifts/1', original, method='PUT').status_code == 409
    with app.state.factory() as db:
        assert db.scalar(select(Entry.id).where(Entry.kind == 'debt')) is not None


def test_archived_cash_snapshot_preserved_but_not_displayed_as_current_cash(system):
    app, _, admin, _, _ = system
    with app.state.factory() as db, db.begin():
        row = Shift(employee_id=2, business_date=date(2026,9,28), current_version=1, approved_version=1)
        db.add(row); db.flush()
        version = ShiftVersion(shift_id=row.id, number=1, business_date=date(2026,9,28),
                               deposit_date=date(2026,9,28), deposit_number='OLD-CASH',
                               deposit_amount=Decimal('100'), device_sales=Decimal('100'),
                               opening_cash=Decimal('0'), pos_sales=Decimal('0'), retained_cash=Decimal('0'),
                               notes='', reason='طريقة قديمة', created_by=2)
        db.add(version); db.flush()
        db.add(Approval(shift_id=row.id, version_id=version.id, approved_by=1, note='من النسخة القديمة',
                        totals_json=json.dumps({'device_sales':'100','outside_sales':'0','total_sales':'100',
                           'purchases':'0','shift_bank':'0','total_bank':'0','deposit_amount':'100',
                           'difference':'0','status':'balanced','message':'الصندوق مطابق'})))
    res = details(admin)
    assert res['approved'] is True and res['has_legacy_cash'] is True
    assert 'retained_cash' not in res['version'] and 'difference' not in res['totals']
    data = payload(); data.update(expected_version=1,reason='محاولة تعديل',deposit_number='OLD-CASH')
    assert send(admin,'/api/shifts/1',data,method='PUT').status_code == 409
    with app.state.factory() as db:
        assert db.scalar(select(Approval.id)) is not None


def test_exports_have_no_debt_or_cash_variance_columns(system):
    _, _, admin, employee, _ = system
    submit(employee, payload())
    confirm(admin)
    report = admin.get('/api/reports?month=2026-09')
    assert report.status_code == 200
    assert 'outstanding_debts' not in report.json()
    for label in ('new_debts','shortage','surplus','net_difference'):
        assert label not in report.json()['totals']
    csv = admin.get('/api/reports/export.csv?month=2026-09')
    assert csv.status_code == 200 and csv.content.startswith(b'\xef\xbb\xbf')
    for column in ('العجز','الفائض','الديون','صافي الفرق'):
        assert column not in csv.text
    for path in ('/api/reports/export.pdf?month=2026-09', '/api/shifts/1/export.pdf'):
        pdf = admin.get(path)
        assert pdf.status_code == 200 and pdf.content.startswith(b'%PDF')


def test_notifications_off_device_no_cash_shortage_events(system):
    app, _, admin, employee, _ = system
    data = payload()
    data['entries'] = [line('off_device', amount='50', name='منتج خارج الجهاز', item_code='X1',quantity=1)]
    submit(employee, data)
    assert confirm(admin).status_code == 200
    with app.state.factory() as db:
        events = list(db.scalars(select(NotificationEvent)))
        assert {e.kind for e in events} == {'off_device_sales'}


def test_two_simultaneous_confirms_single_approval(system):
    app, _, admin, employee, _ = system
    submit(employee, payload())
    cookie = dict(admin.cookies)
    def worker(_):
        with TestClient(app) as client:
            client.cookies.update(cookie)
            return confirm(client).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = sorted(pool.map(worker, [1,2]))
    assert statuses == [200,409]
    with app.state.factory() as db:
        assert len(list(db.scalars(select(Approval)))) == 1
