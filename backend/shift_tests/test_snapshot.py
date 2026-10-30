from .conftest import payload,submit,reconcile


def test_approved_snapshot_remains_the_historical_source_of_truth(system,monkeypatch):
    _,_,admin,employee,_=system
    submit(employee,payload())
    assert reconcile(admin).status_code==200
    from shift_app import services
    def unavailable_new_formula(*_,**__):
        raise AssertionError('Approved history must use its immutable snapshot')
    monkeypatch.setattr(services,'calculate',unavailable_new_formula)
    report=admin.get('/api/reports?month=2026-09')
    assert report.status_code==200
    assert report.json()['shifts'][0]['totals']['difference']=='0.00'
