from .conftest import send


def test_opening_debt_duplicates_are_normalized_and_reversal_preserves_original(system):
    _,_,admin,employee,_=system
    data=dict(name='عميل قديم',invoice_number='0001',description='رصيد افتتاحي خاطئ',debt_date='2025-01-01',amount='100')
    created=send(admin,'/api/customers/opening-debts',data)
    assert created.status_code==200
    assert send(admin,'/api/customers/opening-debts',{**data,'invoice_number':'٠٠٠١'}).status_code==409
    identifier=created.json()['id']
    path=f'/api/customers/debts/{identifier}/cancel-opening'
    assert send(employee,path,{'reason':'غير مصرح'}).status_code==403
    assert send(admin,path,{'reason':'تم تصحيح الرصيد الافتتاحي'}).status_code==200
    statement=admin.get('/api/customers').json()[0]
    assert statement['remaining']=='0.00'
    assert len(statement['debts'])==1 and not statement['debts'][0]['active']
