import hashlib
import hmac
import json
import re
from contextlib import contextmanager
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID
from sqlalchemy import select, text, update
from sqlalchemy.inspection import inspect
from .finance import RuleError
from .models import AuditLog, IdempotencyRecord, Store, User


def wire(value):
    if isinstance(value, Decimal):
        return format(value, '.2f')
    if isinstance(value, datetime):
        return value.isoformat(timespec='seconds') + 'Z'
    if isinstance(value, (date, UUID)):
        return str(value)
    if isinstance(value, dict):
        return {k: wire(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [wire(v) for v in value]
    return value


def row(obj, exclude=()):
    return wire({c.key: getattr(obj, c.key) for c in inspect(obj).mapper.column_attrs if c.key not in exclude})


def json_text(value):
    return json.dumps(wire(value), ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def digest(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def audit(db, actor, action, obj, detail=None):
    db.add(AuditLog(user_id=actor.id if actor else None, action=action,
                    entity_type=obj.__tablename__, entity_id=str(obj.id) if getattr(obj, 'id', None) is not None else None,
                    detail_json=json_text(detail or {})))


def lock_store(db):
    # Serialize all financial writes, user revocation, CLI writes and n8n claims
    # on one persisted row. The lock is held until the database transaction commits.
    result = db.execute(update(Store).where(Store.id == 1).values(revision=Store.revision + 1))
    if result.rowcount != 1:
        raise RuleError('شغّل ترحيلات قاعدة البيانات أولًا.', 503)


def mutate(factory, actor_id, key, fingerprint, operation, secret, admin=False, service=False):
    if not key or not re.fullmatch(r'[A-Za-z0-9_.:-]{16,64}', key):
        raise RuleError('مفتاح منع التكرار مفقود أو غير صالح.', 400)
    with factory() as db, db.begin():
        lock_store(db)
        actor = None if service else db.get(User, actor_id)
        if not service and (not actor or not actor.active):
            raise RuleError('المستخدم غير مصرح له.', 401)
        if admin and actor.role != 'admin':
            raise RuleError('هذه العملية للمدير فقط.', 403)
        actor_key = 'n8n' if service else 'user:' + str(actor.id)
        hashed = hmac.new(secret.encode(), json_text(fingerprint).encode(), hashlib.sha256).hexdigest()
        previous = db.scalar(select(IdempotencyRecord).where(
            IdempotencyRecord.actor_key == actor_key, IdempotencyRecord.request_key == key))
        if previous:
            if not hmac.compare_digest(previous.request_hash, hashed):
                raise RuleError('مفتاح الطلب مستخدم لبيانات مختلفة. أعد بدء العملية.', 409)
            return json.loads(previous.response_json)
        result = wire(operation(db, actor))
        db.add(IdempotencyRecord(actor_key=actor_key, request_key=key,
                                request_hash=hashed, response_json=json_text(result)))
        # Entries, files, ledger changes, audit, outbox and acknowledgement commit together.
        return result


@contextmanager
def reading(factory):
    with factory() as db, db.begin():
        if db.bind.dialect.name == 'postgresql':
            db.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY'))
        yield db


def get_or_404(db, model, identifier):
    obj = db.get(model, identifier)
    if not obj:
        raise RuleError('السجل غير موجود.', 404)
    return obj
