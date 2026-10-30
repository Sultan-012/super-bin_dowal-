from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from uuid import uuid4
from fastapi.testclient import TestClient
from sqlalchemy import select
from .conftest import details,line,match_all,payload,reconcile,send,submit
from shift_app.models import CustomerDebt,DebtPayment,NotificationDelivery,Shift,Store,utcnow








def test_unknown_notification_delivery_never_automatically_retries(system):
    app,config,admin,employee,_=system
    data=payload();data['entries']=[line('off_device','20',name='صنف',item_code='00001',quantity=1)]
    submit(employee,data)
    client=TestClient(app)
    headers={'Authorization':'Bearer '+config.n8n_api_token,'Idempotency-Key':str(uuid4())}
    result=client.post('/api/integrations/outbox/claim',headers=headers).json()['delivery']
    with app.state.factory() as db,db.begin():db.get(NotificationDelivery,result['id']).lease_until=utcnow()-timedelta(seconds=1)
    assert client.post('/api/integrations/outbox/claim',headers=headers).json()['delivery'] is None
    with app.state.factory() as db:assert db.get(NotificationDelivery,result['id']).status=='uncertain'
    response=send(admin,f"/api/notifications/{result['id']}/retry",{'reason':'تم التحقق من المزود ولم ترسل الرسالة'})
    assert response.status_code==200
    with app.state.factory() as db:assert db.get(NotificationDelivery,result['id']).status=='pending'




def test_login_throttle_persists(system):
    app,config,_,_,_=system
    client=TestClient(app)
    for _ in range(5):assert client.post('/api/auth/login',json={'username':'u2','password':'incorrect'}).status_code==401
    assert client.post('/api/auth/login',json={'username':'u2','password':'12345678'}).status_code==429
    from shift_app.main import create_app
    restarted=create_app(config)
    with TestClient(restarted) as new:
        assert new.post('/api/auth/login',json={'username':'u2','password':'12345678'}).status_code==429
    restarted.state.engine.dispose()
