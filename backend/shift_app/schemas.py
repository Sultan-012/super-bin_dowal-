from datetime import date
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID
import unicodedata
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, StringConstraints, field_validator, model_validator
from .finance import money, reference_key

Money = Annotated[Decimal, BeforeValidator(money)]
Text = Annotated[str, Field(min_length=1, max_length=150)]
Password = Annotated[str, StringConstraints(strip_whitespace=False)]


class Schema(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True, hide_input_in_errors=True)

    @field_validator('*', mode='before')
    @classmethod
    def visible_content(cls, value, info):
        if isinstance(value, str) and ('\x00' in value or any(unicodedata.category(char)=='Cs' for char in value)):
            raise ValueError('يحتوي النص على محارف غير صالحة؛ أعد كتابته.')
        if info.field_name != 'password' and isinstance(value, str) and value:
            if not any(unicodedata.category(char)[0] not in {'C', 'Z'} for char in value):
                return ''
        return value


class EntryInput(Schema):
    line_key: UUID
    kind: Literal['purchase', 'off_device', 'bank']
    name: Text
    amount: Money
    reference: str = Field(default='', max_length=100)
    description: str = Field(default='', max_length=2000)
    item_code: str = Field(default='', max_length=100)
    quantity: int | None = Field(default=None, ge=1, le=1000000, strict=True)
    invoice_number: str = Field(default='', max_length=100)
    invoice_total: Money | None = None
    purpose: Literal['current_shift'] | None = None
    attachment_id: UUID | None = None

    @model_validator(mode='after')
    def details_required(self):
        if self.amount <= 0:
            raise ValueError('قيمة العملية يجب أن تكون أكبر من صفر.')
        if self.kind == 'purchase' and not self.description:
            raise ValueError('أدخل اسم المورد وقيمة المشتريات ووصفها؛ رقم الفاتورة والمرفق اختياريان.')
        if self.kind == 'off_device' and (not self.item_code or self.quantity is None):
            raise ValueError('أدخل اسم الصنف ورقمه وعدده وقيمة البيع كاملة.')
        if self.kind == 'bank' and (not self.reference or self.purpose is None):
            raise ValueError('أدخل نوع التحويل واسم الشخص ورقم الحوالة أو الإيداع وقيمته.')
        if self.invoice_total is not None:
            raise ValueError('حقل إجمالي فاتورة الدين أُزيل من الإصدار الجديد.')
        if self.kind != 'bank' and self.purpose is not None:
            raise ValueError('نوع التحويل متاح للحوالات البنكية فقط.')
        if self.kind == 'off_device' and self.attachment_id is not None:
            raise ValueError('المرفقات متاحة فقط للمشتريات والتحويلات البنكية.')
        return self


class ShiftInput(Schema):
    business_date: date
    deposit_date: date
    deposit_number: str = Field(min_length=1, max_length=100)
    deposit_amount: Money
    device_sales: Money
    notes: str = Field(default='', max_length=2000)
    entries: list[EntryInput] = Field(default_factory=list, max_length=200)

    @model_validator(mode='after')
    def consistent_entries(self):
        keys = [str(e.line_key) for e in self.entries]
        if len(set(keys)) != len(keys):
            raise ValueError('هناك صف مكرر في الوردية.')
        for kind in ['purchase', 'off_device', 'bank']:
            if sum(e.kind == kind for e in self.entries) > 50:
                raise ValueError('الحد الأقصى 50 صفًا في كل قسم.')
        seen = set()
        for e in self.entries:
            key = None
            if e.kind == 'bank':
                key = ('bank', reference_key(e.reference))
            elif e.kind == 'purchase' and e.invoice_number:
                key = ('purchase', reference_key(e.name), reference_key(e.invoice_number))
            if key and key in seen:
                raise ValueError('رقم حوالة أو فاتورة مكرر في الوردية.')
            if key:
                seen.add(key)
        return self


class RevisionInput(ShiftInput):
    expected_version: int = Field(ge=1)
    reason: str = Field(min_length=3, max_length=1000)


class ConfirmShiftInput(Schema):
    expected_version: int = Field(ge=1)
    confirmed: Literal[True]
    note: str = Field(default='', max_length=1000)


# Historical reconciliation payloads remain readable in archived records only.
# No new API accepts POS or physical cash amounts.
class LoginInput(Schema):
    username: str = Field(min_length=1, max_length=64)
    password: Password = Field(min_length=1, max_length=128)


class UserInput(Schema):
    username: str = Field(pattern=r'^[a-zA-Z0-9_.-]{3,64}$')
    full_name: Text
    password: Password = Field(min_length=8, max_length=128)
    role: Literal['employee', 'admin']

    @field_validator('username')
    @classmethod
    def username_lower(cls, value):
        return value.lower()


class UserUpdate(Schema):
    full_name: Text
    role: Literal['employee', 'admin']
    password: Password | None = Field(default=None, min_length=8, max_length=128)


class SettingsInput(Schema):
    store_name: Text
    timezone: str = Field(min_length=1, max_length=64)
    initial_opening_cash: Money


class DeliveryResult(Schema):
    lease_token: str = Field(min_length=20, max_length=100)
    outcome: Literal['sent', 'uncertain']
    provider_reference: str = Field(default='', max_length=200)
    detail: str = Field(default='', max_length=500)


class RetryInput(Schema):
    reason: str = Field(min_length=3, max_length=500)
