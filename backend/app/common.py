import hashlib
import json
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import select, update
from sqlalchemy.inspection import inspect
from .models import AuditLog, IdempotencyRecord, Store, User
from .finance import RuleError


def wire(value):
    if isinstance(value, Decimal):
        return format(value, '.2f')
    if isinstance(value, datetime):
        return value.isoformat(timespec='seconds') + 'Z'
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: wire(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [wire(v) for v in value]
    return value


def row(obj, exclude=()):
    return wire({c.key: getattr(obj, c.key) for c in inspect(obj).mapper.column_attrs if c.key not in exclude})


def json_text(value):
    return json.dumps(wire(value), ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def digest(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def audit(db, user, action, obj, before=None, after=None, reason=''):
    db.add(AuditLog(user_id=user.id if user else None, action=action,
                    entity_type=obj.__tablename__, entity_id=getattr(obj, 'id', None),
                    before_json=json_text(before) if before is not None else None,
                    after_json=json_text(after) if after is not None else None, reason=reason))


def lock_store(db):
    # First statement of every write transaction; UPDATE holds an exclusive DB row
    # lock until commit. All workers use the same singleton, including CLI tools.
    result = db.execute(update(Store).where(Store.id == 1).values(revision=Store.revision + 1))
    if result.rowcount != 1:
        raise RuleError('شغّل ترحيلات قاعدة البيانات أولًا', 503)


def mutate(factory, actor_id, key, fingerprint, operation, admin=False):
    with factory() as db, db.begin():
        lock_store(db)
        actor = db.get(User, actor_id)
        if not actor or not actor.is_active:
            raise RuleError('المستخدم غير مصرح له', 401)
        if admin and actor.role != 'admin':
            raise RuleError('هذه العملية تتطلب صلاحية مدير', 403)
        request_hash = digest(json_text(fingerprint))
        previous = db.scalar(select(IdempotencyRecord).where(
            IdempotencyRecord.user_id == actor.id, IdempotencyRecord.request_key == key))
        if previous:
            if previous.request_hash != request_hash:
                raise RuleError('مفتاح الطلب مستخدم لعملية مختلفة؛ أعد تحميل النموذج', 409)
            return json.loads(previous.response_json)
        result = wire(operation(db, actor))
        db.add(IdempotencyRecord(user_id=actor.id, request_key=key,
                                request_hash=request_hash, response_json=json_text(result)))
        # Source record, generated movement, audit and idempotency response commit together.
        return result


def get_or_404(db, model, identifier):
    obj = db.get(model, identifier)
    if obj is None:
        raise RuleError('السجل غير موجود', 404)
    return obj
