from .conftest import details,payload,reconcile,send,submit


def revision_from(detail,day):
    data={k:detail['version'][k] for k in ['business_date','deposit_date','deposit_number','deposit_amount','device_sales','notes']}
    return {**data,'business_date':day,'entries':[],'expected_version':detail['version']['number'],'reason':'تصحيح تاريخ الصندوق'}


def test_pending_date_correction_does_not_reorder_active_cash_chain(system):
    _,_,admin,employee,other=system
    submit(employee,payload('2026-09-28'))
    assert reconcile(admin).status_code==200
    assert send(admin,'/api/shifts/1',revision_from(details(admin),'2026-09-30'),method='PUT').status_code==200
    submit(other,payload('2026-09-29'))
    result=reconcile(admin,2)
    assert result.status_code==200,result.text
    assert result.json()['totals']['opening_cash']=='500.00'
    assert result.json()['totals']['previous_shift_id']==1
    # A second same-day submission is permitted, but cannot be approved out
    # of order after a newer date has already been approved.
    submit(employee,payload('2026-09-28'))
    assert reconcile(admin,3).status_code==409
    # Approval of the now-invalid correction cannot reorder the dependent shift.
    assert reconcile(admin,1).status_code==409


def test_last_shift_cannot_be_moved_before_its_predecessor_or_into_future(system):
    _,_,admin,employee,other=system
    submit(employee,payload('2026-09-28'));assert reconcile(admin).status_code==200
    submit(other,payload('2026-09-29'));assert reconcile(admin,2).status_code==200
    assert send(admin,'/api/shifts/2',revision_from(details(admin,2),'2099-01-01'),method='PUT').status_code==422
    assert send(admin,'/api/shifts/2',revision_from(details(admin,2),'2026-09-27'),method='PUT').status_code==200
    assert reconcile(admin,2).status_code==409


def test_blind_employee_context_respects_active_approved_date_during_correction(system):
    from datetime import date,timedelta
    _,_,admin,employee,_=system
    today=employee.get('/api/auth/me').json()['today']
    submit(employee,payload(today));assert reconcile(admin).status_code==200
    yesterday=(date.fromisoformat(today)-timedelta(days=1)).isoformat()
    assert send(admin,'/api/shifts/1',revision_from(details(admin),yesterday),method='PUT').status_code==200
    assert employee.get('/api/auth/me').json()['submitted_today'] is True
