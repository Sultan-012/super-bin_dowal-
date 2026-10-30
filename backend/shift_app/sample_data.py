"""Opt-in administrative-workflow sample, isolated from operational data."""
import hashlib
import secrets
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo
from sqlalchemy import select
from sqlalchemy.engine import make_url
from .common import lock_store
from .models import Attachment, Shift, Store, User
from .reports import ArabicDocument
from .schemas import ConfirmShiftInput, ShiftInput
from .security import hasher
from . import services


def seed_sample(factory, config):
    database = make_url(config.database_url).database or ''
    safe = Path(database).stem.startswith('bin_doul_sample') if config.app_env == 'test' else database.startswith('bin_doul_sample')
    if not safe:
        raise SystemExit('العينة مسموحة فقط في قاعدة مستقلة يبدأ اسمها بـ bin_doul_sample.')
    # Sample insertion never queues external deliveries even if operational
    # notification credentials were accidentally retained in this environment.
    sample_config = config.model_copy(update={'notification_channels': ''})
    with factory() as db, db.begin():
        lock_store(db)
        if db.scalar(select(Shift.id).limit(1)):
            raise SystemExit('قاعدة العينة ليست فارغة؛ لم تضف أي سجلات.')
        admin = db.scalar(select(User).where(User.role == 'admin', User.active.is_(True)))
        if not admin:
            raise SystemExit('أنشئ المدير أولًا باستخدام create-admin.')
        store = db.get(Store, 1)
        employees = []
        for username, name in [('sample_ahmed', 'أحمد محمد · عينة'), ('sample_khaled', 'خالد عبدالله · عينة')]:
            user = User(username=username, full_name=name, role='employee', active=True,
                        password_hash=hasher.hash(secrets.token_urlsafe(32)), created_by=admin.id)
            db.add(user); db.flush(); employees.append(user)
        today = datetime.now(ZoneInfo(store.timezone)).date()
        first = today.replace(day=1)
        days = sorted({today - timedelta(days=i) for i in range(1, 7)} |
                      {first - timedelta(days=1), first - timedelta(days=2)})
        for index, day in enumerate(days):
            employee = employees[index % 2]
            document = ArabicDocument('فاتورة شراء تجريبية', store.store_name)
            document.text('بيانات عينة للتدريب فقط؛ ليست فاتورة تشغيلية.')
            document.text('مورد العينة · مستلزمات تشغيل · 300.00 ريال يمني')
            content = document.bytes()
            file_id = str(uuid4())
            db.add(Attachment(id=file_id, owner_id=employee.id, filename=f'sample-purchase-{index+1}.pdf',
                              mime_type='application/pdf', sha256=hashlib.sha256(content).hexdigest(),
                              size=len(content), content=content))
            db.flush()
            entries = [
                {'line_key': str(uuid4()), 'kind': 'purchase', 'name': 'مورد العينة', 'amount': '300.00',
                 'description': 'رز وزيت · عينة', 'invoice_number': f'SAMPLE-P-{index+1}', 'attachment_id': file_id},
                {'line_key': str(uuid4()), 'kind': 'off_device', 'name': 'عبوة مياه · عينة',
                 'amount': '80.00', 'item_code': '000101', 'quantity': 2},
                {'line_key': str(uuid4()), 'kind': 'bank', 'name': 'علي أحمد · عينة', 'amount': '150.00',
                 'reference': f'SAMPLE-TR-{index+1}', 'purpose': 'current_shift'},
            ]
            data = ShiftInput(business_date=day, deposit_date=day + timedelta(days=1),
                              deposit_number=f'SAMPLE-DEP-{index+1}', deposit_amount='2000.00',
                              device_sales='2500.00', notes='وردية عينة مستقلة للتدريب؛ اعتماد إداري دون جرد.',
                              entries=entries)
            services.submission(db, employee, data, sample_config)
            shift = db.scalar(select(Shift).order_by(Shift.id.desc()).limit(1))
            if index < len(days) - 2:
                services.confirm_shift(db, admin, shift.id, ConfirmShiftInput(expected_version=1,
                                       confirmed=True, note='مراجعة بيانات العينة فقط؛ لا يوجد جرد نقدي.'))
    print('أضيفت العينة إلى القاعدة المنفصلة دون إشعارات خارجية. غيّر كلمات مرور موظفي العينة من حساب المدير عند الحاجة.')
