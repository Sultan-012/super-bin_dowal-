import io
import os
from uuid import uuid4
import pytest
from alembic import command
from alembic.config import Config as AlembicConfig
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from shift_app.config import Config, ROOT
from shift_app.main import create_app
from shift_app.models import User, Store
from shift_app.security import CSRF_COOKIE, hasher

# Retained for the requested deletion review. These modules target retired v2.0
# debt/reconciliation routes; current behavior is covered by test_v22_workflow.
collect_ignore = ['test_active_chain.py', 'test_opening_reversal.py', 'test_snapshot.py']


@pytest.fixture
def system(tmp_path,monkeypatch):
    owner_engine = None
    schema = None
    if os.environ.get('BIN_DOUL_TEST_BACKEND') == 'postgres':
        parsed = make_url(os.environ['TEST_POSTGRES_URL'])
        if not parsed.drivername.startswith('postgresql+psycopg') or not (parsed.database or '').startswith('bin_doul_test'):
            pytest.fail('Use a disposable PostgreSQL database starting with bin_doul_test.')
        owner_engine = create_engine(parsed, hide_parameters=True)
        schema = 'case_' + uuid4().hex
        with owner_engine.begin() as connection:
            connection.execute(text('CREATE SCHEMA ' + schema))
        url = parsed.update_query_dict({'options': '-csearch_path=' + schema}).render_as_string(hide_password=False)
    else:
        url='sqlite:///'+str(tmp_path/'persistent-shifts.db')
    monkeypatch.setenv('APP_ENV','test')
    monkeypatch.setenv('DATABASE_URL',url)
    monkeypatch.setenv('IDEMPOTENCY_SECRET','test-secret-with-more-than-thirty-two-characters')
    migration=AlembicConfig(str(ROOT/'backend'/'shift_alembic.ini'))
    command.upgrade(migration,'head')
    config=Config(app_env='test',database_url=url,cookie_secure=False,
                  idempotency_secret='test-secret-with-more-than-thirty-two-characters',
                  n8n_api_token='test-n8n-token-more-than-thirty-two-characters',
                  notification_channels='email,whatsapp',allowed_origins='http://testserver')
    app=create_app(config)
    with app.state.factory() as db,db.begin():
        db.get(Store,1).initial_opening_cash='500.00'
        for id,name,role in [(1,'مدير الاختبار','admin'),(2,'أحمد','employee'),(3,'خالد','employee')]:
            db.add(User(id=id,username='u'+str(id),full_name=name,role=role,
                        password_hash=hasher.hash('12345678'),active=True))
        db.flush()
        if owner_engine is not None:
            db.execute(text("SELECT setval(pg_get_serial_sequence('shift_users','id'), 3, true)"))
    clients=[]
    for username in ['u1','u2','u3']:
        client=TestClient(app)
        result=client.post('/api/auth/login',json={'username':username,'password':'12345678'})
        assert result.status_code==200,result.text
        clients.append(client)
    yield app,config,*clients
    for client in clients:
        client.close()
    app.state.engine.dispose()
    if owner_engine is not None:
        with owner_engine.begin() as connection:
            connection.execute(text('DROP SCHEMA ' + schema + ' CASCADE'))
        owner_engine.dispose()


def send(client,path,data=None,method='POST',key=None):
    return client.request(method,path,json=data,headers={
        'X-CSRF-Token':client.cookies.get(CSRF_COOKIE,''),'Idempotency-Key':key or str(uuid4())})


def attachment(client):
    image=Image.new('RGB',(40,30),'white')
    stream=io.BytesIO();image.save(stream,format='PNG')
    response=client.post('/api/attachments',content=stream.getvalue(),headers={
        'X-CSRF-Token':client.cookies.get(CSRF_COOKIE,''),'Idempotency-Key':str(uuid4()),
        'Content-Type':'image/png','X-Filename':'invoice.png'})
    assert response.status_code==200,response.text
    return response.json()['id']


def line(kind,amount='100.00',**extra):
    defaults=dict(line_key=str(uuid4()),kind=kind,name='عميل',amount=amount)
    return {**defaults,**extra}


def payload(day='2026-09-28',**extra):
    return dict(business_date=day,deposit_date='2026-10-01',deposit_number='DEP-'+str(uuid4()),
                deposit_amount='1000.00',device_sales='1000.00',notes='ملاحظة\nالوردية',entries=[],**extra)


def submit(employee,data):
    response=send(employee,'/api/shifts',data)
    assert response.status_code==200,response.text
    assert set(response.json())=={'submitted','message'}


def details(admin,identifier=1):
    response=admin.get(f'/api/shifts/{identifier}')
    assert response.status_code==200,response.text
    return response.json()


def match_all(admin,identifier=1,debt_id=None):
    detail=details(admin,identifier)
    for entry in detail['entries']:
        body=dict(expected_version=detail['version']['number'],status='matched',note='تمت المراجعة')
        if entry['kind']=='bank' and entry['purpose']=='customer_account':body['debt_id']=debt_id
        response=send(admin,f"/api/invoices/{entry['id']}/match",body)
        assert response.status_code==200,response.text


def reconcile(admin,identifier=1,pos='0',retained='500',note='مطابقة موثقة',key=None):
    version=details(admin,identifier)['version']['number']
    return send(admin,f'/api/shifts/{identifier}/reconcile',dict(expected_version=version,
                pos_sales=pos,retained_cash=retained,note=note),key=key)
