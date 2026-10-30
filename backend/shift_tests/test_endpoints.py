import json
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select,text
from sqlalchemy.exc import IntegrityError
from shift_app.main import create_app
from shift_app.models import (CustomerDebt,DebtPayment,Entry,NotificationDelivery,NotificationEvent,Store,Shift)
from shift_app.security import CSRF_COOKIE
from .conftest import attachment,details,line,match_all,payload,reconcile,send,submit








def test_references_upload_owner_and_invalid_amounts_are_atomic(system):
    app,_,admin,employee,other=system
    file_id=attachment(other)
    data=payload();data['entries']=[line('purchase',name='مورد',description='شراء',invoice_number='P1',attachment_id=file_id)]
    assert send(employee,'/api/shifts',data).status_code==403
    with app.state.factory() as db:assert db.scalar(select(Shift.id)) is None
    data['entries'][0]['attachment_id']=attachment(employee)
    submit(employee,data)
    assert other.get('/api/attachments/'+file_id).status_code==403
    data2=payload('2026-09-29');data2['deposit_number']=data['deposit_number']
    assert send(other,'/api/shifts',data2).status_code==409
    data2['deposit_number']='Different'
    data2['entries']=[line('off_device','-2',item_code='001',quantity=1)]
    assert send(other,'/api/shifts',data2).status_code==422
    with app.state.factory() as db:assert len(list(db.scalars(select(Shift))))==1






def test_user_password_security_csrf_and_deletion_keeps_financial_records(system):
    app,_,admin,employee,_=system
    assert send(admin,'/api/users',dict(username='newuser',full_name='جديد',password='1234567',role='employee')).status_code==422
    created=send(admin,'/api/users',dict(username='newuser',full_name='جديد',password='12345678',role='employee'))
    assert created.status_code==200 and 'password' not in created.text
    assert employee.post('/api/shifts',json=payload()).status_code==403
    assert send(employee,'/api/users',dict(username='hack',full_name='غير مصرح',password='12345678',role='admin')).status_code==403
    submit(employee,payload())
    assert send(admin,'/api/users/2',method='DELETE').status_code==200
    assert employee.get('/api/auth/me').status_code==401
    assert details(admin)['employee']=='أحمد'
    assert send(admin,'/api/users/1',method='DELETE').status_code==422




