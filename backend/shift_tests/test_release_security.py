"""Release acceptance checks for real attack boundaries and reported UI metrics."""
import csv
import io
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from shift_app.models import Approval, Shift, ShiftVersion
from .conftest import details, line, payload, send, submit


def test_legacy_entry_without_retired_review_remains_readable_and_exportable(system):
    from sqlalchemy import delete
    from shift_app.models import InvoiceReview
    app,_,admin,employee,_=system
    data=payload();data['entries']=[line('off_device',item_code='0001',quantity=1)]
    submit(employee,data)
    with app.state.factory() as db,db.begin():db.execute(delete(InvoiceReview))
    result=admin.get('/api/shifts/1')
    assert result.status_code==200
    assert result.json()['entries'][0]['review'] is None
    assert admin.get('/api/shifts/1/export.pdf').content.startswith(b'%PDF-')


def test_chunked_json_cannot_bypass_body_limit(system):
    _, _, _, employee, _ = system
    def chunks():
        yield b'{"username":"u2","password":"12345678","padding":"'
        for _ in range(10):
            yield b'x' * 65536
        yield b'"}'
    response = employee.post('/api/auth/login', content=chunks(), headers={'Content-Type':'application/json'})
    assert response.status_code == 413
    assert 'message' in response.json()
    assert response.headers['Cache-Control'] == 'no-store'


@pytest.mark.parametrize('length',['-1','not-a-number'])
def test_malformed_content_length_is_rejected(system,length):
    _, _, _, employee, _ = system
    response=employee.post('/api/auth/login',content=b'{}',headers={'Content-Type':'application/json','Content-Length':length})
    assert response.status_code==400
    assert response.headers.get('X-Content-Type-Options')=='nosniff'


def test_password_spaces_are_significant_and_never_returned(system):
    app, _, admin, _, _ = system
    password='  separate-password  '
    created=send(admin,'/api/users',{'username':'spaces','full_name':'موظف بكلمة مرور خاصة','password':password,'role':'employee'})
    assert created.status_code==200,created.text
    with TestClient(app) as client:
        assert client.post('/api/auth/login',json={'username':'spaces','password':password.strip()}).status_code==401
        assert client.post('/api/auth/login',json={'username':'spaces','password':password}).status_code==200
    assert password not in admin.get('/api/users').text
    assert password not in admin.get('/api/audit').text
    assert '$argon2' not in admin.get('/api/users').text


@pytest.mark.parametrize('field',['deposit_number','item_code','reference','name'])
def test_invisible_only_identifiers_and_names_are_rejected(system,field):
    _, _, _, employee, _=system
    data=payload()
    if field=='deposit_number':data[field]='\u200b\u200e'
    else:
        data['entries']=[line('off_device',item_code='001',quantity=1)] if field in ('item_code','name') else [line('bank',reference='R-1',purpose='current_shift')]
        data['entries'][0][field]='\u200b\u200e'
    assert send(employee,'/api/shifts',data).status_code==422


def test_two_concurrent_retries_create_one_shift(system):
    app, _, admin, employee, _=system
    data=payload();key=str(uuid4())
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda _:send(employee,'/api/shifts',data,key=key),range(2)))
    assert [r.status_code for r in results]==[200,200]
    assert results[0].json()==results[1].json()
    assert len(admin.get('/api/shifts').json())==1
    with app.state.factory() as db:assert len(list(db.scalars(select(Shift))))==1


@pytest.mark.parametrize('prefix',['\u00a0','\t','\u200e'])
def test_csv_formula_payload_is_escaped_after_leading_whitespace(system,prefix):
    _, _, admin, employee, _=system
    label=prefix+'=HYPERLINK("https://example.invalid","x")'
    changed=send(admin,'/api/users/2',{'full_name':label,'role':'employee'},method='PUT')
    assert changed.status_code==200
    # User editing revokes the old employee session.
    login=employee.post('/api/auth/login',json={'username':'u2','password':'12345678'})
    assert login.status_code==200
    submit(employee,payload())
    output=admin.get('/api/reports/export.csv?month=2026-09')
    assert output.status_code==200
    rows=list(csv.reader(io.StringIO(output.content.decode('utf-8-sig'))))
    assert rows[1][1].startswith("'")


@pytest.mark.parametrize('value',['اسم\x00غير صالح','اسم\ud800غير صالح'])
def test_invalid_database_text_is_validation_error_and_rolls_back(system,value):
    _,_,admin,employee,_=system
    from shift_app.security import CSRF_COOKIE
    def encoded_send(client,path,data,method='POST'):
        # Escape the surrogate on the actual JSON wire; HTTPX's json= encoder
        # otherwise rejects it before the application can validate the request.
        return client.request(method,path,content=json.dumps(data,ensure_ascii=True),headers={
            'Content-Type':'application/json','X-CSRF-Token':client.cookies.get(CSRF_COOKIE,''),
            'Idempotency-Key':str(uuid4())})
    result=encoded_send(admin,'/api/users/2',{'full_name':value,'role':'employee'},method='PUT')
    assert result.status_code==422
    data=payload();data['notes']=value
    assert encoded_send(employee,'/api/shifts',data).status_code==422
    assert admin.get('/api/shifts').json()==[]


def legacy_approval(db,employee_id,day,difference,number):
    shift=Shift(employee_id=employee_id,business_date=day,current_version=1,approved_version=1)
    db.add(shift);db.flush()
    version=ShiftVersion(shift_id=shift.id,number=1,business_date=day,deposit_date=date(2026,10,1),
        deposit_number='HIST-'+str(number),deposit_amount=Decimal('100'),device_sales=Decimal('100'),
        opening_cash=Decimal('0'),pos_sales=Decimal('0'),retained_cash=Decimal('0'),
        notes='',reason='سجل نقدي قديم',created_by=employee_id)
    db.add(version);db.flush()
    db.add(Approval(shift_id=shift.id,version_id=version.id,approved_by=1,note='لقطة أصلية',
        totals_json=json.dumps({'device_sales':'100.00','outside_sales':'0.00','total_sales':'100.00',
            'purchases':'0.00','shift_bank':'0.00','total_bank':'0.00','deposit_amount':'100.00',
            'difference':difference,'status':'shortage' if Decimal(difference)<0 else 'surplus'})))


def test_historical_variance_analytics_comes_from_backend_snapshots(system):
    app, _, admin, employee, other=system
    with app.state.factory() as db,db.begin():
        legacy_approval(db,2,date(2026,9,28),'-50.10',1)
        legacy_approval(db,2,date(2026,9,29),'30.05',2)
        legacy_approval(db,3,date(2026,9,29),'-900.00',3)
    result=admin.get('/api/reports/analytics?month=2026-09&employee_id=2')
    assert result.status_code==200,result.text
    current=result.json()['months'][-1]
    assert current['shortage']=='50.10' and current['surplus']=='30.05'
    assert current['net_difference']=='-20.05' and current['cash_count_sessions']==2
    assert current['total_sales']=='200.00'
    empty=admin.get('/api/reports/analytics?month=2026-08').json()['months'][-1]
    assert empty['shortage'] is None and empty['net_difference'] is None
    assert employee.get('/api/reports/analytics?month=2026-09').status_code==403
    assert other.get('/api/reports/analytics?month=2026-09').status_code==403


@pytest.mark.parametrize('month',['','2026-13','x','0000-01','9999-12'])
def test_bad_months_have_arabic_validation_errors(system,month):
    _,_,admin,_,_=system
    response=admin.get('/api/reports/analytics',params={'month':month})
    assert response.status_code==422
    assert 'message' in response.json()


def test_api_boundary_blocks_employee_exports_settings_and_service_token_reuse(system):
    app,config,_,employee,_=system
    paths=['/api/shifts','/api/reports','/api/reports/analytics?month=2026-09',
        '/api/reports/export.pdf','/api/reports/export.csv','/api/users','/api/settings','/api/audit','/api/notifications']
    for path in paths:assert employee.get(path).status_code==403,(path,employee.get(path).text)
    with TestClient(app) as service:
        for path in paths:
            assert service.get(path,headers={'Authorization':'Bearer '+config.n8n_api_token}).status_code==401
        assert service.post('/api/integrations/outbox/claim',headers={'Authorization':'Bearer wrong','Idempotency-Key':str(uuid4())}).status_code==401


def test_untrusted_origin_also_gets_security_headers(system):
    _,_,_,employee,_=system
    response=employee.get('/api/auth/me',headers={'Origin':'https://evil.example'})
    assert response.status_code==403
    assert response.headers.get('Cache-Control')=='no-store'
    assert response.headers.get('X-Frame-Options')=='DENY'


def test_fake_pdf_and_active_pdf_are_rejected(system):
    _,_,_,employee,_=system
    from shift_app.security import CSRF_COOKIE
    headers={'X-CSRF-Token':employee.cookies.get(CSRF_COOKIE,''),'Idempotency-Key':str(uuid4()),
             'Content-Type':'application/pdf','X-Filename':'invoice.pdf'}
    response=employee.post('/api/attachments',content=b'%PDF-1.7\nthis is not a PDF file\n%%EOF',headers=headers)
    assert response.status_code==422
    from pypdf import PdfWriter
    writer=PdfWriter();writer.add_blank_page(width=100,height=100);writer.add_js('app.alert("test")')
    stream=io.BytesIO();writer.write(stream)
    headers['Idempotency-Key']=str(uuid4())
    assert employee.post('/api/attachments',content=stream.getvalue(),headers=headers).status_code==422


def test_real_pdf_upload_and_disguised_extension_boundary(system):
    _,_,admin,employee,_=system
    from shift_app.security import CSRF_COOKIE
    pdf=admin.get('/api/reports/export.pdf?month=2026-09')
    assert pdf.status_code==200 and pdf.content.startswith(b'%PDF-')
    headers={'X-CSRF-Token':employee.cookies.get(CSRF_COOKIE,''),'Content-Type':'application/pdf',
             'Idempotency-Key':str(uuid4()),'X-Filename':'invoice.html'}
    assert employee.post('/api/attachments',content=pdf.content,headers=headers).status_code==422
    headers.update({'X-Filename':'invoice.pdf','Idempotency-Key':str(uuid4())})
    saved=employee.post('/api/attachments',content=pdf.content,headers=headers)
    assert saved.status_code==200,saved.text
    assert admin.get('/api/attachments/'+saved.json()['id']).content==pdf.content
    assert employee.get('/api/attachments/'+saved.json()['id']).status_code==403


def test_production_cookie_and_response_hardening(system):
    _,config,_,_,_=system
    from shift_app.main import create_app
    production=create_app(config.model_copy(update={'app_env':'production','cookie_secure':True,
                                                   'allowed_origins':'https://testserver'}))
    with TestClient(production,base_url='https://testserver') as client:
        response=client.post('/api/auth/login',json={'username':'u2','password':'12345678'})
        assert response.status_code==200
        session=next(c for c in response.headers.get_list('set-cookie') if c.startswith('bin_doul_session='))
        assert 'HttpOnly' in session and 'Secure' in session and 'SameSite=strict' in session
        assert response.headers['Strict-Transport-Security']=='max-age=31536000'
        assert 'frame-ancestors' in response.headers['Content-Security-Policy']
        assert client.get('/api/docs').status_code==404
        assert client.get('/api/openapi.json').status_code==404
    production.state.engine.dispose()
