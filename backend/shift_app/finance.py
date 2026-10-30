import re
import unicodedata
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

ZERO = Decimal('0.00')
CENT = Decimal('0.01')
LIMIT = Decimal('9999999999999999.99')


class RuleError(Exception):
    def __init__(self, message, status=422):
        self.message, self.status = message, status


def normalize(value):
    text = unicodedata.normalize('NFKC', str(value)).strip().casefold()
    return ''.join(str(unicodedata.decimal(c)) if c.isdecimal() else c for c in text)


def reference_key(value):
    return re.sub(r'\s+', '', normalize(value))


def money(value):
    if isinstance(value, (float, bool)) or value is None:
        raise ValueError('أدخل المبلغ كنص عشري صحيح، وليس رقمًا تقريبيًا.')
    text = normalize(value).replace('٫', '.').replace('٬', ',')
    if not re.fullmatch(r'(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d{1,2})?', text):
        raise ValueError('أدخل مبلغًا غير سالب، مثل 10,000.50، وبمنزلتين عشريتين كحد أقصى.')
    try:
        result = Decimal(text.replace(',', '')).quantize(CENT, rounding=ROUND_HALF_UP)
    except InvalidOperation:
        raise ValueError('قيمة المبلغ غير صحيحة.') from None
    if not result.is_finite() or result > LIMIT:
        raise ValueError('المبلغ يتجاوز الحد المسموح.')
    return result


def calculate(data, entries, opening=None, pos=None, retained=None):
    def total(kind, purpose=None):
        return sum((e['amount'] for e in entries if e['kind'] == kind and
                    (purpose is None or e.get('purpose') == purpose)), ZERO)
    device = data['device_sales']
    outside, purchases, debts = total('off_device'), total('purchase'), total('debt')
    shift_bank, account_bank = total('bank', 'current_shift'), total('bank', 'customer_account')
    if device < debts + shift_bank:
        if debts:
            raise RuleError('الديون المسجلة قديمًا والتحويلات تتجاوز مبيعات الجهاز؛ راجع السجل المحاسبي القديم.')
        raise RuleError('قيمة التحويلات البنكية من مبيعات الوردية تتجاوز إجمالي مبيعات الجهاز.')
    result = dict(device_sales=device, outside_sales=outside, total_sales=device + outside,
                  purchases=purchases, new_debts=debts, shift_bank=shift_bank,
                  account_bank=account_bank, total_bank=shift_bank + account_bank,
                  deposit_amount=data['deposit_amount'], opening_cash=opening, pos_sales=pos,
                  retained_cash=retained, cash_sales=None, expected_cash=None,
                  actual_cash=None, difference=None, shortage=None, surplus=None,
                  status='pending', message='بانتظار اعتماد المدير')
    if any(value is None for value in (opening, pos, retained)):
        return result
    device_cash = device - pos - debts - shift_bank
    if device_cash < ZERO:
        raise RuleError('إجمالي الجهاز أقل من الشبكة والديون وتحويلات فواتير الوردية. راجع وسائل السداد ولا تسجل مبلغًا مرتين.')
    cash_sales = device_cash + outside
    # Off-device sales are cash. Only current-shift bank invoices reduce expected cash.
    expected = opening + cash_sales - purchases
    actual = data['deposit_amount'] + retained
    diff = (actual - expected).quantize(CENT, rounding=ROUND_HALF_UP)
    result.update(cash_sales=cash_sales, expected_cash=expected, actual_cash=actual,
                  difference=diff, shortage=max(-diff, ZERO), surplus=max(diff, ZERO),
                  status='balanced' if diff == ZERO else 'shortage' if diff < ZERO else 'surplus',
                  message='الصندوق مطابق' if diff == ZERO else
                  f'يوجد عجز بمبلغ {abs(diff):,.2f}' if diff < ZERO else f'يوجد فائض بمبلغ {diff:,.2f}')
    return result
