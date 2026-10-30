from decimal import Decimal as D
import pytest
from pydantic import ValidationError
from shift_app.finance import calculate,money
from shift_app.schemas import ShiftInput,EntryInput,ConfirmShiftInput,UserInput
from .conftest import line,payload

@pytest.mark.parametrize('value',[-1,-1.5,True,None,'-10','NaN','Infinity','1,23','1.001','1e4'])
def test_money_rejects_invalid(value):
    with pytest.raises(ValueError):money(value)

def test_exact_arabic_money():
    assert money('١٠٬٠٠٠٫٥٠')==D('10000.50')
    assert money('0.10')+money('0.20')==D('0.30')

def test_simple_shift_overview_never_implies_cash_reconciliation():
    result=calculate({'device_sales':D('1000'),'deposit_amount':D('950')},
                     [{'kind':'purchase','amount':D('200')},{'kind':'bank','purpose':'current_shift','amount':D('100')}])
    assert result['total_sales']==D('1000')
    assert result['purchases']==D('200')
    assert result['shift_bank']==D('100')
    assert result['difference'] is None and result['shortage'] is None and result['surplus'] is None
    assert result['status']=='pending'

@pytest.mark.parametrize('entry',[
    line('purchase',invoice_number='',description=''),
    line('off_device',item_code='',quantity=1),
    line('off_device',item_code='01',quantity=0),
    line('off_device',item_code='01',quantity=1,name='   '),
    line('debt',invoice_number='D1',description='details',invoice_total='100'),
    line('bank',reference='T1'),
    line('bank',purpose='customer_account',reference='T2'),
])
def test_entry_validation_rejects_debt_and_missing_fields(entry):
    with pytest.raises(ValidationError):EntryInput.model_validate(entry)

def test_optional_invoice_numbers():
    for entry in [line('purchase',invoice_number='',description='توريد'),
                  line('bank',purpose='current_shift',invoice_number='',reference='REF')]:
        EntryInput.model_validate(entry)
    data=payload();data['entries']=[line('purchase',name='مورد',description='صنف أول'),
                                    line('purchase',name='مورد',description='صنف ثاني')]
    ShiftInput.model_validate(data)

def test_security_validations():
    with pytest.raises(ValidationError):ShiftInput.model_validate({**payload(),'deposit_number':' '})
    with pytest.raises(ValidationError):ConfirmShiftInput(expected_version=1,confirmed=False)
    with pytest.raises(ValidationError):ConfirmShiftInput(expected_version=0,confirmed=True)
    assert UserInput(username='user',full_name='موظف',password='12345678',role='employee').password=='12345678'
    with pytest.raises(ValidationError):UserInput(username='user',full_name='موظف',password='1234567',role='employee')
