import calendar
import hashlib
import hmac
import json
import re
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from sqlalchemy import select
from .common import audit, digest, get_or_404, json_text, lock_store, row
from .finance import RuleError
from .models import NotificationDelivery, NotificationEvent, Shift, Store, User, utcnow


def month_range(month):
    if not re.fullmatch(r'\d{4}-\d{2}', month or ''):
        raise RuleError('الشهر يجب أن يكون بالصيغة YYYY-MM.')
    try:
        year, number = map(int, month.split('-'))
        start = date(year, number, 1)
        end = date(year+1, 1, 1) if number == 12 else date(year, number+1, 1)
        return start, end
    except ValueError:
        raise RuleError('قيمة الشهر غير صحيحة.') from None


def enqueue(db, config, key, kind, payload, shift_id=None):
    existing = db.scalar(select(NotificationEvent).where(NotificationEvent.event_key == key))
    if existing:
        for channel in config.channels:
            if not db.scalar(select(NotificationDelivery.id).where(NotificationDelivery.event_id==existing.id,
                                                                   NotificationDelivery.channel==channel)):
                db.add(NotificationDelivery(event_id=existing.id,channel=channel,status='pending'))
        return existing
    store = db.get(Store, 1)
    event = NotificationEvent(event_key=key, kind=kind, shift_id=shift_id,
             payload_json=json_text({'store': store.store_name, 'currency': 'YER', **payload}))
    db.add(event)
    db.flush()
    for channel in config.channels:
        db.add(NotificationDelivery(event_id=event.id, channel=channel, status='pending'))
    return event


def monthly_reports(db, config, month=None):
    from .services import report_data
    store = db.get(Store, 1)
    current_month = datetime.now(ZoneInfo(store.timezone)).date().replace(day=1)
    month = month or (current_month-timedelta(days=1)).strftime('%Y-%m')
    start, end = month_range(month)
    if end > current_month:
        raise RuleError('التقرير المجدول مخصص للشهور المكتملة فقط.')
    employees = list(db.scalars(select(User).join(Shift, Shift.employee_id == User.id).where(
                     Shift.business_date >= start, Shift.business_date < end).distinct()))
    ids = []
    for employee in employees:
        report = report_data(db, start, end, employee.id)
        # A reasoned later correction generates a new report snapshot rather than
        # silently altering an already queued attachment.
        revision_key = digest(json_text([(s['id'], s['current_version'], s['approved_version']) for s in report['shifts']]))[:24]
        event = enqueue(db, config, f'month:{month}:employee:{employee.id}:{revision_key}', 'monthly_report',
                        {'month': month, 'employee_id': employee.id, 'employee': employee.full_name, 'report': report})
        ids.append(event.id)
    return {'month': month, 'events': ids, 'count': len(ids)}


def lease_token(config, delivery, key):
    return hmac.new(config.n8n_api_token.encode(), f'{delivery.id}:{key}'.encode(), hashlib.sha256).hexdigest()


def claim(factory, config, key):
    if not re.fullmatch(r'[A-Za-z0-9_.:-]{16,64}', key or ''):
        raise RuleError('مفتاح طلب n8n غير صالح.', 400)
    with factory() as db, db.begin():
        lock_store(db)
        now = utcnow()
        expired = db.scalars(select(NotificationDelivery).where(NotificationDelivery.status == 'leased',
                                                                  NotificationDelivery.lease_until < now))
        for delivery in expired:
            delivery.status = 'uncertain'
            delivery.last_error = 'انتهت مهلة العامل دون تأكيد. تحقق من المزود قبل إعادة الإرسال.'
        db.flush()
        previous = db.scalar(select(NotificationDelivery).where(NotificationDelivery.claim_key == key))
        if previous:
            delivery = previous if previous.status == 'leased' else None
        else:
            delivery = db.scalar(select(NotificationDelivery).where(NotificationDelivery.status == 'pending',
                         NotificationDelivery.channel.in_(config.channels)).order_by(NotificationDelivery.id).limit(1)) if config.channels else None
            if delivery:
                delivery.claim_key = key
                delivery.status = 'leased'
                delivery.lease_until = now + timedelta(minutes=10)
                delivery.attempts += 1
                delivery.lease_hash = digest(lease_token(config, delivery, key))
        if not delivery:
            return {'delivery': None}
        event = db.get(NotificationEvent, delivery.event_id)
        return {'delivery': {'id': delivery.id, 'event_id': event.id, 'event_key': event.event_key,
                            'channel': delivery.channel, 'kind': event.kind,
                            'lease_token': lease_token(config, delivery, key),
                            'payload': json.loads(event.payload_json)}}


def result(db, identifier, data):
    delivery = get_or_404(db, NotificationDelivery, identifier)
    if not delivery.lease_hash or not hmac.compare_digest(delivery.lease_hash, digest(data.lease_token)):
        raise RuleError('رمز تسليم الإشعار غير صالح.', 403)
    if delivery.status == 'sent':
        return {'status': 'sent'}
    if delivery.status != 'leased':
        raise RuleError('لم تعد مهمة الإرسال قيد المعالجة. راجع سجل الإشعارات.', 409)
    delivery.status = data.outcome
    delivery.provider_reference = data.provider_reference
    delivery.last_error = data.detail if data.outcome == 'uncertain' else ''
    audit(db, None, 'notification.'+data.outcome, delivery, {'event_id': delivery.event_id})
    return {'status': delivery.status}


def retry(db, actor, identifier, reason):
    delivery = get_or_404(db, NotificationDelivery, identifier)
    if delivery.status != 'uncertain':
        raise RuleError('إعادة المحاولة اليدوية متاحة للحالات غير المؤكدة فقط.', 409)
    delivery.status, delivery.lease_hash, delivery.lease_until, delivery.claim_key = 'pending', None, None, None
    audit(db, actor, 'notification.retry-authorized', delivery, {'reason': reason, 'previous_error': delivery.last_error})
    return {'id': delivery.id, 'status': 'pending'}
