from datetime import date
from decimal import Decimal
from typing import Annotated, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, field_validator, model_validator
from pydantic import StringConstraints

MAX_MONEY = Decimal('9999999999999999.99')


def exact_money(v):
    if isinstance(v, (float, bool)):
        raise ValueError('أرسل المبلغ كنص عشري دقيق، بحد أقصى منزلتين عشريتين')
    return v


Money = Annotated[Decimal, BeforeValidator(exact_money), Field(ge=0, le=MAX_MONEY, max_digits=18, decimal_places=2, allow_inf_nan=False)]
PositiveMoney = Annotated[Money, Field(gt=0)]
Text = Annotated[str, Field(min_length=1, max_length=250)]
Notes = Annotated[str, Field(max_length=2000)]
Method = Literal['cash', 'card', 'bank']
Password = Annotated[str, StringConstraints(strip_whitespace=False)]


class Input(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class LoginInput(Input):
    username: str = Field(min_length=1, max_length=64)
    password: Password = Field(min_length=1, max_length=256)


class UserInput(Input):
    username: str = Field(pattern=r'^[a-zA-Z0-9_.-]{3,64}$')
    full_name: str = Field(min_length=1, max_length=150)
    password: Password = Field(min_length=12, max_length=128)
    role: Literal['admin', 'employee']


class UserEdit(Input):
    full_name: str = Field(min_length=1, max_length=150)
    role: Literal['admin', 'employee']
    is_active: bool
    password: Password | None = Field(default=None, min_length=12, max_length=128)


class PasswordInput(Input):
    current_password: Password = Field(min_length=1, max_length=256)
    new_password: Password = Field(min_length=12, max_length=128)


class OpenInput(Input):
    business_date: date
    opening_cash: Money | None = None
    notes: Notes = ''


class SalesInput(Input):
    total_sales: Money
    pos_sales: Money
    notes: Notes = ''
    expected_version: int = Field(ge=1)


class CountInput(Input):
    actual_cash: Money | None = None
    expected_version: int = Field(ge=1)


class CloseInput(CountInput):
    note: Notes = ''


class ReasonInput(Input):
    reason: str = Field(min_length=3, max_length=1000)


class CustomerInput(Input):
    name: str = Field(min_length=1, max_length=150)
    phone: str | None = Field(default=None, max_length=40)
    notes: Notes = ''


class DebtInput(Input):
    customer_id: int = Field(gt=0)
    debt_date: date
    amount: PositiveMoney
    due_date: date | None = None
    kind: Literal['opening', 'credit']
    session_id: int | None = Field(default=None, gt=0)
    notes: Notes = ''

    @model_validator(mode='after')
    def source(self):
        if (self.kind == 'opening') != (self.session_id is None):
            raise ValueError('الرصيد الافتتاحي لا يرتبط بجلسة؛ البيع الآجل يتطلب جلسة يومية')
        if self.due_date and self.due_date < self.debt_date:
            raise ValueError('تاريخ الاستحقاق يجب ألا يسبق تاريخ الدين')
        return self


class PaymentInput(Input):
    debt_id: int = Field(gt=0)
    session_id: int = Field(gt=0)
    payment_date: date
    amount: PositiveMoney
    payment_method: Method
    notes: Notes = ''


class PurchaseInput(Input):
    session_id: int = Field(gt=0)
    purchase_date: date
    description: Text
    supplier: str | None = Field(default=None, max_length=150)
    amount: PositiveMoney
    payment_method: Method
    from_drawer: bool
    invoice_number: str | None = Field(default=None, max_length=80)
    notes: Notes = ''

    @model_validator(mode='after')
    def source(self):
        if self.from_drawer and self.payment_method != 'cash':
            raise ValueError('الدفع من الصندوق يتطلب طريقة الدفع نقدًا')
        return self


class MovementInput(Input):
    session_id: int = Field(gt=0)
    movement_date: date
    kind: Literal['expense', 'withdrawal', 'deposit', 'refund']
    amount: PositiveMoney
    description: Text


class SettingsInput(Input):
    store_name: str = Field(min_length=1, max_length=150)
    currency: str = Field(pattern=r'^[A-Z]{3}$')
    timezone: str = Field(min_length=1, max_length=64)

    @field_validator('currency')
    @classmethod
    def currency_code(cls, value):
        # One currency, exactly two decimal places in this version.
        if value not in {'SAR', 'YER', 'AED', 'USD', 'EUR', 'GBP', 'EGP', 'QAR'}:
            raise ValueError('رمز العملة غير مدعوم')
        return value

    @field_validator('timezone')
    @classmethod
    def timezone_exists(cls, value):
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError:
            raise ValueError('المنطقة الزمنية غير صالحة')
        return value
