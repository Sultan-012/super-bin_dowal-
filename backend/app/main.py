import csv
import io
import json
import hmac
import hashlib
import re
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from fastapi import Depends, FastAPI, Header, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import delete, func, or_, select, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from . import schemas as s, services as svc
from .common import audit, get_or_404, mutate, row, wire
from .config import Config, ROOT
from .db import make_engine, make_factory
from .finance import RuleError
from .models import (AuditLog, AuthSession, CashSession, Customer, CustomerDebt,
                     Store, User, utcnow)
from .security import (COOKIE, CSRF_COOKIE, authenticate, hasher, login,
                       public_user, verify)


def safe_csv(rows):
    stream = io.StringIO(newline='')
    writer = csv.writer(stream)
    for values in rows:
        # Prevent spreadsheet formula execution in untrusted names/notes.
        writer.writerow([("'" + v if isinstance(v, str) and v.lstrip().startswith(('=', '+', '-', '@', '\t', '\r')) and not re.fullmatch(r'-?\d+(\.\d+)?', v) else v)
                         for v in values])
    return stream.getvalue().encode('utf-8-sig')


def csv_response(rows, filename):
    return Response(safe_csv(rows), media_type='text/csv; charset=utf-8',
                    headers={'Content-Disposition': f'attachment; filename="{filename}"'})


def create_app(config: Config | None = None, engine=None):
    config = config or Config()
    app = FastAPI(title='Daily Sales & Cash Reconciliation System', version='1.0.0',
                  docs_url='/api/docs' if config.app_env != 'production' else None, redoc_url=None)
    app.state.config = config
    app.state.engine = engine or make_engine(config.database_url)
    app.state.factory = make_factory(app.state.engine)
    app.add_middleware(CORSMiddleware, allow_origins=config.origins, allow_credentials=True,
                       allow_methods=['GET', 'POST', 'PUT', 'PATCH'],
                       allow_headers=['Content-Type', 'X-CSRF-Token', 'Idempotency-Key'])

    @app.middleware('http')
    async def security_headers(request, call_next):
        origin = request.headers.get('origin')
        if request.method not in {'GET', 'HEAD', 'OPTIONS'} and origin and origin not in config.origins:
            return JSONResponse({'detail': 'مصدر الطلب غير مسموح'}, status_code=403)
        if request.method not in {'GET', 'HEAD', 'OPTIONS'} and request.headers.get('sec-fetch-site') == 'cross-site':
            return JSONResponse({'detail': 'طلب من موقع خارجي غير مسموح'}, status_code=403)
        try:
            content_length = int(request.headers.get('content-length', '0') or '0')
        except ValueError:
            return JSONResponse({'detail': 'حجم الطلب غير صالح'}, status_code=400)
        if content_length > 65536:
            return JSONResponse({'detail': 'حجم الطلب أكبر من المسموح'}, status_code=413)
        response = await call_next(request)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'same-origin'
        response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
        response.headers['Cache-Control'] = 'no-store' if request.url.path.startswith('/api') else 'no-cache'
        if config.app_env == 'production':
            response.headers['Strict-Transport-Security'] = 'max-age=31536000'
            response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        return response

    @app.exception_handler(RuleError)
    async def rule_error(_, exc):
        return JSONResponse({'detail': exc.message}, status_code=exc.status)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_, exc):
        # Do not echo submitted credentials or raw input in error responses.
        errors = [{'field': '.'.join(map(str, e['loc'][1:])), 'type': e['type']} for e in exc.errors()]
        custom = [str(e.get('ctx', {}).get('error', '')) for e in exc.errors() if e['type'] == 'value_error']
        return JSONResponse({'detail': next((v for v in custom if v), 'تحقق من الحقول المطلوبة: المبالغ غير سالبة وبمنزلتين عشريتين كحد أقصى، والنصوص والتواريخ صحيحة.'),
                             'errors': errors}, status_code=422)

    @app.exception_handler(IntegrityError)
    async def integrity_error(_, exc):
        return JSONResponse({'detail': 'تعارض في السجلات أو قيد سلامة البيانات؛ حدّث الصفحة وراجع العملية'}, status_code=409)

    @app.exception_handler(DBAPIError)
    async def database_error(_, exc):
        # No SQL, database URL, credentials or driver messages reach the browser.
        return JSONResponse({'detail': 'تعذر إكمال العملية بقاعدة البيانات. أعد المحاولة بنفس الطلب، أو راجع إعداد الاتصال.'}, status_code=503)

    def identity(request: Request):
        return authenticate(request)

    def admin(request: Request):
        return authenticate(request, admin=True)

    def read_db():
        with app.state.factory() as db, db.begin():
            if db.bind.dialect.name == 'sqlite':
                db.connection().exec_driver_sql('BEGIN')
            # A shared HOLDLOCK creates a consistent report across its queries.
            # Every writer must first acquire the conflicting exclusive store lock.
            db.scalar(select(Store).where(Store.id == 1).with_hint(Store, 'WITH (HOLDLOCK)', 'mssql'))
            yield db

    def change(request, actor, key, data, operation, admin_only=False):
        body = data.model_dump(mode='json') if data else {}
        # Password-bearing requests must not create a fast offline password oracle.
        for field in ('password', 'current_password', 'new_password'):
            if body.get(field) is not None:
                body[field] = hmac.new(config.idempotency_secret.encode(), body[field].encode(), hashlib.sha256).hexdigest()
        return mutate(app.state.factory, actor.id, key,
                      {'method': request.method, 'path': request.url.path,
                       'body': body}, operation, admin=admin_only)

    Key = Header(alias='Idempotency-Key', min_length=16, max_length=64, pattern=r'^[a-zA-Z0-9_-]+$')

    @app.get('/api/health')
    def health():
        with app.state.factory() as db:
            db.execute(text('SELECT 1'))
            initialized = db.get(Store, 1) is not None
        return {'status': 'ok' if initialized else 'migration_required', 'database': app.state.engine.dialect.name}

    @app.post('/api/auth/login')
    def sign_in(data: s.LoginInput, request: Request, response: Response):
        user, token, csrf = login(app.state.factory, data, request.client.host if request.client else 'unknown', config.session_hours)
        options = dict(secure=config.cookie_secure, samesite='strict', path='/', max_age=config.session_hours * 3600)
        response.set_cookie(COOKIE, token, httponly=True, **options)
        response.set_cookie(CSRF_COOKIE, csrf, httponly=False, **options)
        return user

    @app.get('/api/auth/me')
    def me(actor=Depends(identity), db=Depends(read_db)):
        store = db.get(Store, 1)
        return {'user': public_user(db.get(User, actor.id)), 'settings': row(store),
                'today': datetime.now(ZoneInfo(store.timezone)).date().isoformat()}

    @app.post('/api/auth/logout')
    def sign_out(response: Response, actor=Depends(identity)):
        from .common import lock_store
        with app.state.factory() as db, db.begin():
            lock_store(db)
            db.execute(delete(AuthSession).where(AuthSession.token_hash == actor.token_hash))
        response.delete_cookie(COOKIE, path='/')
        response.delete_cookie(CSRF_COOKIE, path='/')
        return {'ok': True}

    @app.post('/api/auth/password')
    def password(data: s.PasswordInput, request: Request, actor=Depends(identity), key: str = Key):
        def op(db, user):
            if not verify(data.current_password, user.password_hash):
                raise RuleError('كلمة المرور الحالية غير صحيحة', 403)
            user.password_hash = hasher.hash(data.new_password)
            db.execute(delete(AuthSession).where(AuthSession.user_id == user.id, AuthSession.token_hash != actor.token_hash))
            audit(db, user, 'change_password', user)
            return {'ok': True}
        # Fingerprint is one-way SHA256; neither passwords nor hashes enter audit responses.
        return change(request, actor, key, data, op)

    @app.get('/api/sessions')
    def sessions(start: date | None = None, end: date | None = None, q: str = Query('', max_length=100),
                 status: str | None = Query(None, pattern='^(open|closed)$'),
                 offset: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=367),
                 actor=Depends(identity), db=Depends(read_db)):
        query = select(CashSession)
        if start: query = query.where(CashSession.business_date >= start)
        if end: query = query.where(CashSession.business_date <= end)
        if status: query = query.where(CashSession.status == status)
        if q:
            ids = select(User.id).where(User.full_name.contains(q, autoescape=True))
            conditions = [CashSession.notes.contains(q, autoescape=True), CashSession.responsible_user_id.in_(ids)]
            if q.isdigit(): conditions.append(CashSession.id == int(q))
            try: conditions.append(CashSession.business_date == date.fromisoformat(q))
            except ValueError: pass
            query = query.where(or_(*conditions))
        items = list(db.scalars(query.order_by(CashSession.business_date.desc()).offset(offset).limit(limit)))
        return [dict(row(x), totals=wire(svc.metrics(db, x)), responsible_name=db.get(User, x.responsible_user_id).full_name) for x in items]

    @app.get('/api/sessions/current')
    def current(actor=Depends(identity), db=Depends(read_db)):
        session = db.scalar(select(CashSession).where(CashSession.status == 'open'))
        latest = db.scalar(select(CashSession).order_by(CashSession.business_date.desc()).limit(1))
        return {'session': svc.session_detail(db, session) if session else None,
                'next_opening_cash': wire(latest.actual_cash) if latest and latest.status == 'closed' else None,
                'last_business_date': wire(latest.business_date) if latest else None}

    @app.get('/api/sessions/{sid}')
    def get_session(sid: int, actor=Depends(identity), db=Depends(read_db)):
        return svc.session_detail(db, get_or_404(db, CashSession, sid))

    @app.post('/api/sessions')
    def open_session(data: s.OpenInput, request: Request, actor=Depends(identity), key: str = Key):
        return change(request, actor, key, data, lambda db, u: svc.create_session(db, u, data))

    @app.put('/api/sessions/{sid}/sales')
    def save_sales(sid: int, data: s.SalesInput, request: Request, actor=Depends(identity), key: str = Key):
        return change(request, actor, key, data, lambda db, u: svc.update_sales(db, u, sid, data))

    @app.post('/api/sessions/{sid}/preview')
    def preview(sid: int, data: s.CountInput, actor=Depends(identity), db=Depends(read_db)):
        session = svc.require_open(db, sid)
        svc.require_version(session, data.expected_version)
        return wire(svc.metrics(db, session, data.actual_cash))

    @app.put('/api/sessions/{sid}/count')
    def count(sid: int, data: s.CountInput, request: Request, actor=Depends(identity), key: str = Key):
        return change(request, actor, key, data, lambda db, u: svc.count_cash(db, u, sid, data))

    @app.post('/api/sessions/{sid}/close')
    def close(sid: int, data: s.CloseInput, request: Request, actor=Depends(identity), key: str = Key):
        return change(request, actor, key, data, lambda db, u: svc.count_cash(db, u, sid, data, close=True))

    @app.post('/api/sessions/{sid}/reopen')
    def reopen(sid: int, data: s.ReasonInput, request: Request, actor=Depends(admin), key: str = Key):
        return change(request, actor, key, data, lambda db, u: svc.reopen_session(db, u, sid, data), admin_only=True)

    @app.get('/api/customers')
    def customers(q: str = Query('', max_length=100), offset: int = Query(0, ge=0),
                  limit: int = Query(100, ge=1, le=200), actor=Depends(identity), db=Depends(read_db)):
        query = select(Customer)
        if q: query = query.where(or_(Customer.name.contains(q, autoescape=True), Customer.phone.contains(q, autoescape=True)))
        result = []
        for c in db.scalars(query.order_by(Customer.name).offset(offset).limit(limit)):
            debts = list(db.scalars(select(CustomerDebt).where(CustomerDebt.customer_id == c.id, CustomerDebt.cancelled_at.is_(None))))
            balance = sum((svc.debt_balance(db, d)['remaining'] for d in debts), svc.ZERO)
            result.append(dict(row(c), outstanding=wire(balance), debt_count=len(debts)))
        return result

    @app.post('/api/customers')
    def add_customer(data: s.CustomerInput, request: Request, actor=Depends(identity), key: str = Key):
        return change(request, actor, key, data, lambda db, u: svc.save_customer(db, u, data))

    @app.put('/api/customers/{cid}')
    def edit_customer(cid: int, data: s.CustomerInput, request: Request, actor=Depends(identity), key: str = Key):
        return change(request, actor, key, data, lambda db, u: svc.save_customer(db, u, data, cid))

    @app.get('/api/customers/{cid}/statement')
    def statement(cid: int, actor=Depends(identity), db=Depends(read_db)):
        return svc.customer_statement(db, cid)

    @app.get('/api/customers/{cid}/statement.csv')
    def statement_csv(cid: int, actor=Depends(identity), db=Depends(read_db)):
        data = svc.customer_statement(db, cid)
        rows = [['كشف حساب العميل', data['customer']['name']], ['التاريخ', 'النوع', 'رقم السجل', 'المبلغ', 'ملغى', 'الرصيد المتبقي']]
        for e in data['entries']:
            rows.append([e['date'], 'دين' if e['kind'] == 'debt' else 'سداد', e['id'], e['amount'], 'نعم' if e['cancelled'] else 'لا', e['running_balance']])
        return csv_response(rows, f'customer-{cid}.csv')

    @app.post('/api/debts')
    def add_debt(data: s.DebtInput, request: Request, actor=Depends(identity), key: str = Key):
        return change(request, actor, key, data, lambda db, u: svc.create_debt(db, u, data))

    @app.post('/api/payments')
    def add_payment(data: s.PaymentInput, request: Request, actor=Depends(identity), key: str = Key):
        return change(request, actor, key, data, lambda db, u: svc.create_payment(db, u, data))

    @app.post('/api/purchases')
    def add_purchase(data: s.PurchaseInput, request: Request, actor=Depends(identity), key: str = Key):
        return change(request, actor, key, data, lambda db, u: svc.create_purchase(db, u, data))

    @app.post('/api/movements')
    def add_movement(data: s.MovementInput, request: Request, actor=Depends(identity), key: str = Key):
        return change(request, actor, key, data, lambda db, u: svc.create_movement(db, u, data))

    @app.post('/api/records/{category}/{identifier}/cancel')
    def cancel(category: str, identifier: int, data: s.ReasonInput, request: Request, actor=Depends(admin), key: str = Key):
        return change(request, actor, key, data, lambda db, u: svc.cancel_record(db, u, category, identifier, data.reason), admin_only=True)

    @app.get('/api/transactions')
    def transactions(start: date, end: date, session_id: int | None = None,
                     actor=Depends(identity), db=Depends(read_db)):
        if end < start or (end - start).days > 366:
            raise RuleError('اختر فترة صحيحة لا تتجاوز 367 يومًا')
        return wire(svc.transaction_list(db, start, end, session_id))

    @app.get('/api/reports')
    def reports(start: date, end: date, actor=Depends(admin), db=Depends(read_db)):
        return svc.report(db, start, end)

    @app.get('/api/dashboard')
    def dashboard(start: date, end: date, actor=Depends(identity), db=Depends(read_db)):
        if actor.role != 'admin' and start != end:
            raise RuleError('تقارير الفترات تتطلب صلاحية مدير؛ اختر يومًا واحدًا', 403)
        return svc.report(db, start, end)

    @app.get('/api/reports/export.csv')
    def report_csv(start: date, end: date, actor=Depends(admin), db=Depends(read_db)):
        data = svc.report(db, start, end)
        labels = ['التاريخ', 'الحالة', 'إجمالي المبيعات', 'نقدي', 'شبكة', 'آجل', 'تحصيل نقدي', 'تحصيل شبكة', 'تحصيل تحويل', 'مشتريات الصندوق', 'مصروفات', 'إيداعات', 'سحوبات', 'مرتجعات', 'رصيد الافتتاح', 'المتوقع', 'آخر جرد', 'الفرق المعتمد']
        fields = ['business_date', 'status', 'total_sales', 'cash_sales', 'pos_sales', 'new_credit_sales', 'cash_collections', 'card_collections', 'bank_collections', 'cash_purchases', 'cash_expenses', 'deposits', 'withdrawals', 'cash_refunds', 'opening_cash', 'expected_cash', 'actual_cash', 'difference']
        rows = [['الفترة', data['start'], data['end'], 'العملة', data['currency']], labels]
        for d in data['daily']:
            values = dict(d, status='مغلقة' if d['status'] == 'closed' else 'مفتوحة')
            if d['status'] != 'closed': values['difference'] = None
            rows.append([values.get(f, '') for f in fields])
        rows.extend([[], ['إجمالي العجز', data['totals']['total_shortages']], ['إجمالي الفائض', data['totals']['total_surpluses']], ['صافي فرق الصندوق', data['totals']['net_difference']]])
        return csv_response(rows, f'report-{start}-{end}.csv')

    @app.get('/api/users')
    def users(actor=Depends(admin), db=Depends(read_db)):
        return [public_user(u) for u in db.scalars(select(User).order_by(User.id))]

    @app.post('/api/users')
    def create_user(data: s.UserInput, request: Request, actor=Depends(admin), key: str = Key):
        def op(db, u):
            user = User(username=data.username.lower(), full_name=data.full_name, role=data.role,
                        password_hash=hasher.hash(data.password), created_by=u.id)
            db.add(user)
            db.flush()
            audit(db, u, 'create_user', user, after=public_user(user))
            return public_user(user)
        return change(request, actor, key, data, op, admin_only=True)

    @app.put('/api/users/{uid}')
    def edit_user(uid: int, data: s.UserEdit, request: Request, actor=Depends(admin), key: str = Key):
        def op(db, u):
            user = get_or_404(db, User, uid)
            if user.role == 'admin' and user.is_active and (not data.is_active or data.role != 'admin'):
                other = db.scalar(select(User.id).where(User.role == 'admin', User.is_active.is_(True), User.id != uid))
                if not other: raise RuleError('لا يمكن تعطيل أو خفض صلاحية آخر مدير نشط')
            before = public_user(user)
            user.full_name, user.role, user.is_active = data.full_name, data.role, data.is_active
            if data.password: user.password_hash = hasher.hash(data.password)
            if data.password or not data.is_active or before['role'] != data.role:
                db.execute(delete(AuthSession).where(AuthSession.user_id == uid))
            audit(db, u, 'update_user', user, before, public_user(user))
            return public_user(user)
        return change(request, actor, key, data, op, admin_only=True)

    @app.get('/api/settings')
    def get_settings(actor=Depends(identity), db=Depends(read_db)):
        return row(db.get(Store, 1))

    @app.put('/api/settings')
    def settings(data: s.SettingsInput, request: Request, actor=Depends(admin), key: str = Key):
        def op(db, u):
            store = db.get(Store, 1)
            if data.currency != store.currency and (db.scalar(select(CashSession.id).limit(1)) or db.scalar(select(CustomerDebt.id).limit(1))):
                raise RuleError('لا يمكن تغيير العملة بعد تسجيل أرصدة أو معاملات مالية')
            if data.timezone != store.timezone and db.scalar(select(CashSession.id).where(CashSession.status == 'open')):
                raise RuleError('أغلق الجلسة قبل تغيير المنطقة الزمنية')
            before = row(store)
            for field, value in data.model_dump().items(): setattr(store, field, value)
            audit(db, u, 'update_settings', store, before, row(store))
            return row(store)
        return change(request, actor, key, data, op, admin_only=True)

    @app.get('/api/audit')
    def logs(offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200), actor=Depends(admin), db=Depends(read_db)):
        return [dict(row(a), user_name=db.get(User, a.user_id).full_name if a.user_id else 'النظام') for a in
                db.scalars(select(AuditLog).order_by(AuditLog.id.desc()).offset(offset).limit(limit))]

    dist = ROOT / 'frontend' / 'dist'
    if dist.is_dir():
        app.mount('/assets', StaticFiles(directory=dist / 'assets'), name='assets')

        @app.get('/')
        def index():
            return FileResponse(dist / 'index.html')

        @app.get('/{path:path}', include_in_schema=False)
        def spa(path: str):
            if path.startswith('api/'):
                return JSONResponse({'detail': 'المسار غير موجود'}, status_code=404)
            return FileResponse(dist / 'index.html')
    return app
