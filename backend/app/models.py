from datetime import date, datetime, timezone
from decimal import Decimal
from sqlalchemy import (Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index,
                        Integer, Numeric, String, Unicode, UnicodeText, UniqueConstraint, text)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


class Timestamped:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class User(Timestamped, Base):
    __tablename__ = 'users'
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True)
    full_name: Mapped[str] = mapped_column(Unicode(150))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(15))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey('users.id'))
    __table_args__ = (CheckConstraint("role IN ('admin','employee')", name='ck_user_role'),)


class AuthSession(Base):
    __tablename__ = 'auth_sessions'
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    csrf_hash: Mapped[str] = mapped_column(String(64))
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class LoginThrottle(Base):
    __tablename__ = 'login_throttles'
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    attempts: Mapped[int] = mapped_column(default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime)


class Store(Timestamped, Base):
    __tablename__ = 'settings'
    id: Mapped[int] = mapped_column(primary_key=True)
    revision: Mapped[int] = mapped_column(default=0)
    store_name: Mapped[str] = mapped_column(Unicode(150), default='متجري')
    currency: Mapped[str] = mapped_column(String(3), default='SAR')
    timezone: Mapped[str] = mapped_column(String(64), default='Asia/Riyadh')
    __table_args__ = (CheckConstraint('id = 1', name='ck_single_store'),)


MONEY = Numeric(18, 2, asdecimal=True)
LONG_TEXT = UnicodeText().with_variant(Unicode(), "mssql")


class CashSession(Timestamped, Base):
    __tablename__ = 'cash_sessions'
    id: Mapped[int] = mapped_column(primary_key=True)
    drawer_id: Mapped[int] = mapped_column(default=1)
    business_date: Mapped[date] = mapped_column(Date, index=True)
    responsible_user_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    created_by: Mapped[int] = mapped_column(ForeignKey('users.id'))
    previous_session_id: Mapped[int | None] = mapped_column(ForeignKey('cash_sessions.id'))
    opening_cash: Mapped[Decimal] = mapped_column(MONEY)
    total_sales: Mapped[Decimal] = mapped_column(MONEY, default=Decimal('0.00'))
    pos_sales: Mapped[Decimal] = mapped_column(MONEY, default=Decimal('0.00'))
    status: Mapped[str] = mapped_column(String(10), default='open')
    version: Mapped[int] = mapped_column(default=1)
    actual_cash: Mapped[Decimal | None] = mapped_column(MONEY)
    counted_at: Mapped[datetime | None] = mapped_column(DateTime)
    count_version: Mapped[int | None]
    counted_by: Mapped[int | None] = mapped_column(ForeignKey('users.id'))
    notes: Mapped[str] = mapped_column(Unicode(2000), default='')
    closed_at: Mapped[datetime | None] = mapped_column(DateTime)
    closed_by: Mapped[int | None] = mapped_column(ForeignKey('users.id'))
    __table_args__ = (
        UniqueConstraint('drawer_id', 'business_date', name='uq_drawer_date'),
        CheckConstraint('drawer_id = 1', name='ck_single_drawer'),
        CheckConstraint('opening_cash >= 0 AND total_sales >= 0 AND pos_sales >= 0 AND total_sales >= pos_sales', name='ck_session_amounts'),
        CheckConstraint('actual_cash IS NULL OR actual_cash >= 0', name='ck_actual_cash'),
        CheckConstraint("status IN ('open','closed')", name='ck_session_status'),
        CheckConstraint("status <> 'closed' OR (actual_cash IS NOT NULL AND closed_at IS NOT NULL AND closed_by IS NOT NULL AND count_version IS NOT NULL AND count_version = version)", name='ck_closed_count'),
        Index('uq_one_open_drawer', 'drawer_id', unique=True,
              mssql_where=text("status = 'open'"), sqlite_where=text("status = 'open'")),
    )


class FinancialRecord(Timestamped):
    created_by: Mapped[int] = mapped_column(ForeignKey('users.id'))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime)
    cancelled_by: Mapped[int | None] = mapped_column(ForeignKey('users.id'))
    cancellation_reason: Mapped[str | None] = mapped_column(Unicode(1000))


class Customer(Timestamped, Base):
    __tablename__ = 'customers'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(Unicode(150), index=True)
    phone: Mapped[str | None] = mapped_column(Unicode(40))
    notes: Mapped[str] = mapped_column(Unicode(2000), default='')
    created_by: Mapped[int] = mapped_column(ForeignKey('users.id'))


class CustomerDebt(FinancialRecord, Base):
    __tablename__ = 'customer_debts'
    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey('customers.id'), index=True)
    debt_date: Mapped[date] = mapped_column(Date, index=True)
    amount: Mapped[Decimal] = mapped_column(MONEY)
    due_date: Mapped[date | None] = mapped_column(Date)
    kind: Mapped[str] = mapped_column(String(10))
    session_id: Mapped[int | None] = mapped_column(ForeignKey('cash_sessions.id'), index=True)
    notes: Mapped[str] = mapped_column(Unicode(2000), default='')
    __table_args__ = (
        CheckConstraint('amount > 0', name='ck_debt_positive'),
        CheckConstraint("(kind = 'opening' AND session_id IS NULL) OR (kind = 'credit' AND session_id IS NOT NULL)", name='ck_debt_origin'),
        CheckConstraint('due_date IS NULL OR due_date >= debt_date', name='ck_due_date'),
    )


class DebtPayment(FinancialRecord, Base):
    __tablename__ = 'debt_payments'
    id: Mapped[int] = mapped_column(primary_key=True)
    debt_id: Mapped[int] = mapped_column(ForeignKey('customer_debts.id'), index=True)
    session_id: Mapped[int] = mapped_column(ForeignKey('cash_sessions.id'), index=True)
    payment_date: Mapped[date] = mapped_column(Date)
    amount: Mapped[Decimal] = mapped_column(MONEY)
    payment_method: Mapped[str] = mapped_column(String(10))
    notes: Mapped[str] = mapped_column(Unicode(2000), default='')
    __table_args__ = (CheckConstraint('amount > 0', name='ck_payment_positive'),
                      CheckConstraint("payment_method IN ('cash','card','bank')", name='ck_payment_method'))


class Purchase(FinancialRecord, Base):
    __tablename__ = 'purchases'
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey('cash_sessions.id'), index=True)
    purchase_date: Mapped[date] = mapped_column(Date)
    description: Mapped[str] = mapped_column(Unicode(250))
    supplier: Mapped[str | None] = mapped_column(Unicode(150))
    amount: Mapped[Decimal] = mapped_column(MONEY)
    payment_method: Mapped[str] = mapped_column(String(10))
    from_drawer: Mapped[bool] = mapped_column(Boolean)
    invoice_number: Mapped[str | None] = mapped_column(Unicode(80))
    notes: Mapped[str] = mapped_column(Unicode(2000), default='')
    __table_args__ = (
        CheckConstraint('amount > 0', name='ck_purchase_positive'),
        CheckConstraint("payment_method IN ('cash','card','bank')", name='ck_purchase_method'),
        CheckConstraint("from_drawer = 0 OR payment_method = 'cash'", name='ck_purchase_drawer'),
    )


class CashMovement(FinancialRecord, Base):
    __tablename__ = 'cash_movements'
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey('cash_sessions.id'), index=True)
    movement_date: Mapped[date] = mapped_column(Date)
    kind: Mapped[str] = mapped_column(String(15))
    amount: Mapped[Decimal] = mapped_column(MONEY)
    description: Mapped[str] = mapped_column(Unicode(250))
    responsible_user_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    purchase_id: Mapped[int | None] = mapped_column(ForeignKey('purchases.id'))
    debt_payment_id: Mapped[int | None] = mapped_column(ForeignKey('debt_payments.id'))
    __table_args__ = (
        CheckConstraint('amount > 0', name='ck_movement_positive'),
        CheckConstraint("(kind IN ('expense','withdrawal','deposit','refund') AND purchase_id IS NULL AND debt_payment_id IS NULL) OR (kind = 'purchase' AND purchase_id IS NOT NULL AND debt_payment_id IS NULL) OR (kind = 'collection' AND debt_payment_id IS NOT NULL AND purchase_id IS NULL)", name='ck_movement_source'),
        Index('uq_purchase_movement', 'purchase_id', unique=True,
              mssql_where=text('purchase_id IS NOT NULL'), sqlite_where=text('purchase_id IS NOT NULL')),
        Index('uq_payment_movement', 'debt_payment_id', unique=True,
              mssql_where=text('debt_payment_id IS NOT NULL'), sqlite_where=text('debt_payment_id IS NOT NULL')),
    )


class ClosingSnapshot(Base):
    __tablename__ = 'closing_snapshots'
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey('cash_sessions.id'), index=True)
    approved_by: Mapped[int] = mapped_column(ForeignKey('users.id'))
    approved_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    totals_json: Mapped[str] = mapped_column(LONG_TEXT)
    note: Mapped[str] = mapped_column(Unicode(2000))


class AuditLog(Base):
    __tablename__ = 'audit_logs'
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'), index=True)
    action: Mapped[str] = mapped_column(String(64))
    entity_type: Mapped[str] = mapped_column(String(64))
    entity_id: Mapped[int | None] = mapped_column(index=True)
    before_json: Mapped[str | None] = mapped_column(LONG_TEXT)
    after_json: Mapped[str | None] = mapped_column(LONG_TEXT)
    reason: Mapped[str] = mapped_column(Unicode(2000), default='')
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class IdempotencyRecord(Base):
    __tablename__ = 'idempotency_records'
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    request_key: Mapped[str] = mapped_column(String(64))
    request_hash: Mapped[str] = mapped_column(String(64))
    response_json: Mapped[str] = mapped_column(LONG_TEXT)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    __table_args__ = (UniqueConstraint('user_id', 'request_key', name='uq_idempotency_user_key'),)
