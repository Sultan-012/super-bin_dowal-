from decimal import Decimal as D
import pytest
from app.finance import RuleError, calculate, money


@pytest.mark.parametrize('actual,difference,state', [('1650','-50.00','shortage'), ('1750','50.00','surplus'), ('1700','0.00','balanced'), (None,None,'pending')])
def test_required_financial_example(actual, difference, state):
    r = calculate(opening=D('500'), total=D('3000'), pos=D('1200'), credit=D('300'),
                  collections=D('200'), purchases=D('400'), expenses=D('100'), actual=D(actual) if actual else None)
    assert r['cash_sales'] == D('1500')
    assert r['expected_cash'] == D('1700')
    assert r['difference'] == (D(difference) if difference is not None else None)
    assert r['reconciliation_status'] == state
    if actual is None: assert r['reconciliation_message'] == 'بانتظار الجرد'


def test_negative_cash_sales_rejected():
    with pytest.raises(RuleError):
        calculate(opening=D('0'), total=D('100'), pos=D('70'), credit=D('40'))


def test_decimal_and_half_up_policy():
    assert money(D('0.10') + D('0.20')) == D('0.30')
    assert money(D('1.005')) == D('1.01')


def test_zero_count_is_not_empty():
    result = calculate(opening=D('0'), total=D('0'), pos=D('0'), actual=D('0'))
    assert result['reconciliation_status'] == 'balanced'


def test_aggregate_overflow_rejected():
    with pytest.raises(RuleError):
        calculate(opening=D('9999999999999999.99'), total=D('1'), pos=D('0'))
