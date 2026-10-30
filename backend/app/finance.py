from decimal import Decimal, ROUND_HALF_UP
from .schemas import MAX_MONEY

ZERO = Decimal('0.00')
CENT = Decimal('0.01')


class RuleError(Exception):
    def __init__(self, message: str, status: int = 422):
        self.message, self.status = message, status


def money(value):
    value = Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)
    if not value.is_finite() or abs(value) > MAX_MONEY:
        raise RuleError('المبلغ أو إجمالي العملية يتجاوز الحد المسموح')
    return value


def calculate(*, opening, total, pos, credit=ZERO, collections=ZERO, deposits=ZERO,
              purchases=ZERO, expenses=ZERO, withdrawals=ZERO, refunds=ZERO, actual=None):
    """Pure Decimal calculation. Sources supply only valid, non-cancelled records."""
    values = [opening, total, pos, credit, collections, deposits, purchases, expenses, withdrawals, refunds]
    if any(money(x) < ZERO for x in values) or (actual is not None and money(actual) < ZERO):
        raise RuleError('المبالغ المدخلة يجب أن تكون غير سالبة')
    cash = money(total - pos - credit)
    if cash < ZERO:
        raise RuleError('إجمالي المبيعات أقل من مجموع مبيعات الشبكة والمبيعات الآجلة. عدّل إجمالي المبيعات أو تفاصيل البيع الآجل.')
    expected = money(opening + cash + collections + deposits - purchases - expenses - withdrawals - refunds)
    difference = None if actual is None else money(actual - expected)
    if difference is None:
        state, message = 'pending', 'بانتظار الجرد'
    elif difference == ZERO:
        state, message = 'balanced', 'الصندوق مطابق'
    elif difference < ZERO:
        state, message = 'shortage', f'يوجد عجز بمبلغ {abs(difference):.2f}'
    else:
        state, message = 'surplus', f'يوجد فائض بمبلغ {difference:.2f}'
    return {'cash_sales': cash, 'expected_cash': expected, 'difference': difference,
            'reconciliation_status': state, 'reconciliation_message': message}
