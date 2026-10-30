"""Regression test: upgrading an existing v2 database never erases stored shifts."""
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config as AlembicConfig
from sqlalchemy import create_engine, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from shift_app.config import ROOT
from shift_app.models import Entry, Shift, ShiftVersion, User


def test_upgrade_preserves_financial_records_and_append_only_trigger(tmp_path, monkeypatch):
    url = 'sqlite:///' + str(tmp_path / 'previous-version.db')
    monkeypatch.setenv('APP_ENV', 'test')
    monkeypatch.setenv('DATABASE_URL', url)
    monkeypatch.setenv('IDEMPOTENCY_SECRET', 'test-secret-with-more-than-thirty-two-characters')
    alembic = AlembicConfig(str(ROOT / 'backend' / 'shift_alembic.ini'))
    command.upgrade(alembic, '20261029_02')
    engine = create_engine(url)
    with Session(engine) as db, db.begin():
        db.add(User(id=2, username='testuser', full_name='موظف', role='employee', active=True,
                    password_hash='test-unused'))
        db.flush()
        shift = Shift(employee_id=2, business_date=date(2026, 9, 28), current_version=1)
        db.add(shift)
        db.flush()
        version = ShiftVersion(shift_id=shift.id, number=1, business_date=date(2026, 9, 28),
                               deposit_date=date(2026, 9, 28), deposit_number='SAFE-OLD',
                               deposit_amount=Decimal('100'), device_sales=Decimal('100'),
                               reason='بيانات قديمة', created_by=2)
        db.add(version)
        db.flush()
        old = Entry(version_id=version.id, line_key=str(uuid4()), kind='off_device',
                    name='صنف اختبار', amount=Decimal('10'), item_code='0001', quantity=1)
        db.add(old)
        db.flush()
        old_shift_id, old_entry_id = shift.id, old.id
    engine.dispose()

    command.upgrade(alembic, 'head')
    engine = create_engine(url)
    with Session(engine) as db, db.begin():
        stored_shift = db.get(Shift, old_shift_id)
        stored_entry = db.get(Entry, old_entry_id)
        assert stored_shift.employee_id == 2
        assert stored_entry.item_code == '0001'
        assert stored_entry.amount == Decimal('10.00')
        # The old same-date unique index is gone after the migration.
        db.add(Shift(employee_id=2, business_date=date(2026, 9, 28), current_version=1))
        db.flush()
        assert db.scalar(select(Shift.id).order_by(Shift.id.desc()).limit(1)) != old_shift_id
    with engine.begin() as connection:
        with pytest.raises(IntegrityError):
            connection.execute(text('DELETE FROM shift_entries WHERE id=:id'), {'id':old_entry_id})
    engine.dispose()
