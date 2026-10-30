from datetime import date, datetime, timezone
from decimal import Decimal
from sqlalchemy import (Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index,
                        Integer, LargeBinary, Numeric, String, Text, UniqueConstraint)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


class Timestamped:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


MONEY = Numeric(18, 2, asdecimal=True)


class User(Timestamped, Base):
    __tablename__ = 'shift_users'
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True)
    full_name: Mapped[str] = mapped_column(String(150))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(12))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey('shift_users.id'))
    __table_args__ = (CheckConstraint("role IN ('admin','employee')", name='ck_shift_role'),)


class Store(Base):
    __tablename__ = 'shift_settings'
    id: Mapped[int] = mapped_column(primary_key=True)
    revision: Mapped[int] = mapped_column(default=0)
    store_name: Mapped[str] = mapped_column(String(150), default='سوبر ماركت بن دول')
    currency: Mapped[str] = mapped_column(String(3), default='YER')
    timezone: Mapped[str] = mapped_column(String(64), default='Asia/Aden')
    initial_opening_cash: Mapped[Decimal] = mapped_column(MONEY, default=Decimal('0.00'))
    __table_args__ = (CheckConstraint("id = 1 AND currency = 'YER' AND initial_opening_cash >= 0", name='ck_shift_store'),)


class AuthSession(Base):
    __tablename__ = 'shift_auth_sessions'
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    csrf_hash: Mapped[str] = mapped_column(String(64))
    user_id: Mapped[int] = mapped_column(ForeignKey('shift_users.id'), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)


class LoginThrottle(Base):
    __tablename__ = 'shift_login_throttles'
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    attempts: Mapped[int] = mapped_column(default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime)


class Shift(Timestamped, Base):
    __tablename__ = 'shifts'
    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey('shift_users.id'), index=True)
    business_date: Mapped[date] = mapped_column(Date, index=True)
    current_version: Mapped[int] = mapped_column(default=1)
    approved_version: Mapped[int | None]
    previous_shift_id: Mapped[int | None] = mapped_column(ForeignKey('shifts.id'))
    submitted_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    # Several separate shifts may be submitted by one employee on one business date.
    # Idempotency keys and unique financial references prevent accidental resubmission.


class ShiftVersion(Base):
    __tablename__ = 'shift_versions'
    id: Mapped[int] = mapped_column(primary_key=True)
    shift_id: Mapped[int] = mapped_column(ForeignKey('shifts.id'), index=True)
    number: Mapped[int]
    business_date: Mapped[date] = mapped_column(Date, index=True)
    deposit_date: Mapped[date] = mapped_column(Date)
    deposit_number: Mapped[str] = mapped_column(String(100))
    deposit_amount: Mapped[Decimal] = mapped_column(MONEY)
    device_sales: Mapped[Decimal] = mapped_column(MONEY)
    opening_cash: Mapped[Decimal | None] = mapped_column(MONEY)
    pos_sales: Mapped[Decimal | None] = mapped_column(MONEY)
    retained_cash: Mapped[Decimal | None] = mapped_column(MONEY)
    notes: Mapped[str] = mapped_column(Text, default='')
    reason: Mapped[str] = mapped_column(String(1000))
    created_by: Mapped[int] = mapped_column(ForeignKey('shift_users.id'))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    __table_args__ = (
        UniqueConstraint('shift_id', 'number', name='uq_shift_version'),
        CheckConstraint('deposit_amount >= 0 AND device_sales >= 0', name='ck_shift_version_money'),
        CheckConstraint('(opening_cash IS NULL AND pos_sales IS NULL AND retained_cash IS NULL) OR (opening_cash >= 0 AND pos_sales >= 0 AND retained_cash >= 0 AND opening_cash IS NOT NULL AND pos_sales IS NOT NULL AND retained_cash IS NOT NULL)', name='ck_shift_count_fields'),
        CheckConstraint('length(trim(deposit_number)) > 0', name='ck_shift_deposit_number'),
    )


class Attachment(Base):
    __tablename__ = 'shift_attachments'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey('shift_users.id'))
    shift_id: Mapped[int | None] = mapped_column(ForeignKey('shifts.id'), index=True)
    filename: Mapped[str] = mapped_column(String(150))
    mime_type: Mapped[str] = mapped_column(String(30))
    sha256: Mapped[str] = mapped_column(String(64))
    size: Mapped[int]
    content: Mapped[bytes] = mapped_column(LargeBinary)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    __table_args__ = (CheckConstraint('size > 0 AND size <= 5242880', name='ck_attachment_size'),)


class Entry(Base):
    __tablename__ = 'shift_entries'
    id: Mapped[int] = mapped_column(primary_key=True)
    version_id: Mapped[int] = mapped_column(ForeignKey('shift_versions.id'), index=True)
    line_key: Mapped[str] = mapped_column(String(36))
    kind: Mapped[str] = mapped_column(String(15), index=True)
    name: Mapped[str] = mapped_column(String(150))
    amount: Mapped[Decimal] = mapped_column(MONEY)
    reference: Mapped[str] = mapped_column(String(100), default='')
    description: Mapped[str] = mapped_column(Text, default='')
    item_code: Mapped[str] = mapped_column(String(100), default='')
    quantity: Mapped[int | None]
    invoice_number: Mapped[str] = mapped_column(String(100), default='')
    invoice_total: Mapped[Decimal | None] = mapped_column(MONEY)
    purpose: Mapped[str | None] = mapped_column(String(25))
    attachment_id: Mapped[str | None] = mapped_column(ForeignKey('shift_attachments.id'))
    __table_args__ = (
        UniqueConstraint('version_id', 'line_key', name='uq_shift_line_key'),
        CheckConstraint('amount > 0 AND length(trim(name)) > 0', name='ck_shift_entry_amount_name'),
        CheckConstraint("kind IN ('purchase','off_device','debt','bank')", name='ck_shift_entry_kind'),
        CheckConstraint("kind <> 'purchase' OR length(trim(description)) > 0", name='ck_purchase_invoice_required'),
        CheckConstraint("kind <> 'off_device' OR (length(trim(item_code)) > 0 AND quantity > 0 AND quantity IS NOT NULL)", name='ck_off_device_required'),
        CheckConstraint("kind <> 'debt' OR (length(trim(description)) > 0 AND invoice_total >= amount AND invoice_total IS NOT NULL)", name='ck_debt_invoice_required'),
        CheckConstraint("kind <> 'bank' OR (length(trim(reference)) > 0 AND purpose IN ('current_shift','customer_account') AND purpose IS NOT NULL)", name='ck_bank_required'),
    )


class InvoiceReview(Timestamped, Base):
    __tablename__ = 'shift_invoice_reviews'
    id: Mapped[int] = mapped_column(primary_key=True)
    entry_id: Mapped[int] = mapped_column(ForeignKey('shift_entries.id'), unique=True)
    status: Mapped[str] = mapped_column(String(12), default='pending', index=True)
    note: Mapped[str] = mapped_column(String(1000), default='')
    debt_id: Mapped[int | None] = mapped_column(ForeignKey('shift_customer_debts.id'))
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey('shift_users.id'))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)
    __table_args__ = (CheckConstraint("status IN ('pending','matched')", name='ck_invoice_review_status'),)


class ReferenceReservation(Base):
    __tablename__ = 'shift_references'
    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(20))
    normalized_key: Mapped[str] = mapped_column(String(64))
    shift_id: Mapped[int] = mapped_column(ForeignKey('shifts.id'))
    __table_args__ = (UniqueConstraint('kind', 'normalized_key', name='uq_shift_reference'),)


class Customer(Timestamped, Base):
    __tablename__ = 'shift_customers'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150))
    name_key: Mapped[str] = mapped_column(String(64), unique=True)
    notes: Mapped[str] = mapped_column(Text, default='')


class CustomerDebt(Timestamped, Base):
    __tablename__ = 'shift_customer_debts'
    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey('shift_customers.id'), index=True)
    invoice_number: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text)
    debt_date: Mapped[date] = mapped_column(Date, index=True)
    amount: Mapped[Decimal] = mapped_column(MONEY)
    source_key: Mapped[str | None] = mapped_column(String(36), unique=True)
    shift_id: Mapped[int | None] = mapped_column(ForeignKey('shifts.id'), index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[int] = mapped_column(ForeignKey('shift_users.id'))
    __table_args__ = (CheckConstraint('amount > 0', name='ck_shift_debt_amount'),)


class DebtPayment(Timestamped, Base):
    __tablename__ = 'shift_debt_payments'
    id: Mapped[int] = mapped_column(primary_key=True)
    debt_id: Mapped[int] = mapped_column(ForeignKey('shift_customer_debts.id'), index=True)
    shift_id: Mapped[int] = mapped_column(ForeignKey('shifts.id'), index=True)
    source_key: Mapped[str] = mapped_column(String(36), unique=True)
    payment_date: Mapped[date] = mapped_column(Date)
    amount: Mapped[Decimal] = mapped_column(MONEY)
    method: Mapped[str] = mapped_column(String(10), default='bank')
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[int] = mapped_column(ForeignKey('shift_users.id'))
    __table_args__ = (CheckConstraint("amount > 0 AND method = 'bank'", name='ck_shift_debt_payment'),)


class Approval(Base):
    __tablename__ = 'shift_approvals'
    id: Mapped[int] = mapped_column(primary_key=True)
    shift_id: Mapped[int] = mapped_column(ForeignKey('shifts.id'), index=True)
    version_id: Mapped[int] = mapped_column(ForeignKey('shift_versions.id'), unique=True)
    totals_json: Mapped[str] = mapped_column(Text)
    note: Mapped[str] = mapped_column(String(1000))
    approved_by: Mapped[int] = mapped_column(ForeignKey('shift_users.id'))
    approved_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class AuditLog(Base):
    __tablename__ = 'shift_audit_logs'
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey('shift_users.id'))
    action: Mapped[str] = mapped_column(String(64))
    entity_type: Mapped[str] = mapped_column(String(50))
    entity_id: Mapped[str | None] = mapped_column(String(64), index=True)
    detail_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class IdempotencyRecord(Base):
    __tablename__ = 'shift_idempotency'
    id: Mapped[int] = mapped_column(primary_key=True)
    actor_key: Mapped[str] = mapped_column(String(80))
    request_key: Mapped[str] = mapped_column(String(64))
    request_hash: Mapped[str] = mapped_column(String(64))
    response_json: Mapped[str] = mapped_column(Text)
    __table_args__ = (UniqueConstraint('actor_key', 'request_key', name='uq_shift_idempotency'),)


class NotificationEvent(Base):
    __tablename__ = 'shift_notification_events'
    id: Mapped[int] = mapped_column(primary_key=True)
    event_key: Mapped[str] = mapped_column(String(160), unique=True)
    kind: Mapped[str] = mapped_column(String(30), index=True)
    shift_id: Mapped[int | None] = mapped_column(ForeignKey('shifts.id'))
    payload_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class NotificationDelivery(Timestamped, Base):
    __tablename__ = 'shift_notification_deliveries'
    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey('shift_notification_events.id'), index=True)
    channel: Mapped[str] = mapped_column(String(12))
    status: Mapped[str] = mapped_column(String(15), default='pending', index=True)
    lease_hash: Mapped[str | None] = mapped_column(String(64))
    claim_key: Mapped[str | None] = mapped_column(String(64), unique=True)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime)
    attempts: Mapped[int] = mapped_column(default=0)
    provider_reference: Mapped[str] = mapped_column(String(200), default='')
    last_error: Mapped[str] = mapped_column(String(500), default='')
    __table_args__ = (
        UniqueConstraint('event_id', 'channel', name='uq_shift_event_channel'),
        CheckConstraint("status IN ('pending','leased','sent','uncertain','cancelled')", name='ck_delivery_status'),
        CheckConstraint("channel IN ('email','whatsapp')", name='ck_delivery_channel'),
    )


Index('ix_shift_entry_version_kind', Entry.version_id, Entry.kind)
