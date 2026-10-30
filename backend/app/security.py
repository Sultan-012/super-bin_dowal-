import hmac
import secrets
from dataclasses import dataclass
from datetime import timedelta
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHashError, VerificationError
from fastapi import Request
from sqlalchemy import delete, select
from .common import audit, digest, lock_store, row
from .finance import RuleError
from .models import AuthSession, LoginThrottle, User, utcnow

hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2)
DUMMY_HASH = hasher.hash(secrets.token_urlsafe(32))
COOKIE = 'daily_sales_session'
CSRF_COOKIE = 'daily_sales_csrf'


def verify(password, encoded):
    try:
        return hasher.verify(encoded, password)
    except (VerifyMismatchError, InvalidHashError, VerificationError):
        return False


def public_user(user):
    return row(user, exclude=('password_hash',))


@dataclass(frozen=True)
class Identity:
    id: int
    role: str
    token_hash: str


def authenticate(request: Request, admin=False):
    token = request.cookies.get(COOKIE, '')
    if not token:
        raise RuleError('يرجى تسجيل الدخول', 401)
    with request.app.state.factory() as db:
        auth = db.get(AuthSession, digest(token))
        user = db.get(User, auth.user_id) if auth and auth.expires_at > utcnow() else None
        if not user or not user.is_active:
            raise RuleError('انتهت الجلسة؛ سجّل الدخول مجددًا', 401)
        if admin and user.role != 'admin':
            raise RuleError('هذه الصفحة تتطلب صلاحية مدير', 403)
        if request.method not in {'GET', 'HEAD', 'OPTIONS'}:
            csrf = request.headers.get('X-CSRF-Token', '')
            if not csrf or not hmac.compare_digest(digest(csrf), auth.csrf_hash):
                raise RuleError('تعذر التحقق من الطلب؛ أعد تحميل الصفحة', 403)
        return Identity(user.id, user.role, auth.token_hash)


def login(factory, data, client_ip, hours):
    failure = None
    result = None
    with factory() as db, db.begin():
        lock_store(db)
        # Both account and client limits are database backed, across API workers.
        throttle_keys = [digest('user:' + data.username.lower()), digest('ip:' + client_ip)]
        throttles = []
        for key in throttle_keys:
            throttle = db.get(LoginThrottle, key)
            if not throttle:
                throttle = LoginThrottle(key=key, attempts=0)
                db.add(throttle)
            throttles.append(throttle)
        if any(t.locked_until and t.locked_until > utcnow() for t in throttles):
            failure = RuleError('محاولات كثيرة؛ حاول مجددًا بعد 15 دقيقة', 429)
        else:
            for t in throttles:
                if t.locked_until:
                    t.attempts, t.locked_until = 0, None
            user = db.scalar(select(User).where(User.username == data.username.lower()))
            valid = verify(data.password, user.password_hash if user else DUMMY_HASH)
            if not valid or not user or not user.is_active:
                for t in throttles:
                    t.attempts += 1
                    if t.attempts >= 5:
                        t.locked_until = utcnow() + timedelta(minutes=15)
                failure = RuleError('اسم المستخدم أو كلمة المرور غير صحيحة', 401)
            else:
                for t in throttles:
                    t.attempts = 0
                if hasher.check_needs_rehash(user.password_hash):
                    user.password_hash = hasher.hash(data.password)
                token, csrf = secrets.token_urlsafe(48), secrets.token_urlsafe(32)
                db.add(AuthSession(token_hash=digest(token), csrf_hash=digest(csrf), user_id=user.id,
                                   expires_at=utcnow() + timedelta(hours=hours)))
                db.execute(delete(AuthSession).where(AuthSession.expires_at < utcnow()))
                audit(db, user, 'login', user)
                result = public_user(user), token, csrf
    if failure:
        raise failure
    return result
