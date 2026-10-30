import hashlib
import hmac
import io
import json
import re
import secrets
import unicodedata
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import quote, unquote
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from fastapi import APIRouter, FastAPI, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError, OperationalError
from . import notifications as notifications_service, services
from .common import audit, digest, get_or_404, mutate, reading, row, wire
from .config import Config, ROOT
from .db import make_engine, make_factory
from .request_limits import RequestLimits
from .finance import RuleError, reference_key
from .models import (Approval, Attachment, AuditLog, AuthSession, Customer, Entry,
                     NotificationDelivery, NotificationEvent, Shift, ShiftVersion, Store, User)
from .schemas import (ConfirmShiftInput, DeliveryResult, LoginInput,
                      RetryInput, RevisionInput, SettingsInput, ShiftInput,
                      UserInput, UserUpdate)
from .security import COOKIE, CSRF_COOKIE, authenticate, hasher, login, public_user


def create_app(config=None):
    config = config or Config()
    app = FastAPI(title='سوبر ماركت بن دول | إغلاق الورديات', version='2.4.0',
                  docs_url='/api/docs' if config.app_env != 'production' else None,
                  redoc_url=None, openapi_url='/api/openapi.json' if config.app_env != 'production' else None)
    app.state.config = config
    app.state.engine = make_engine(config.database_url)
    app.state.factory = make_factory(app.state.engine)
    factory = app.state.factory
    app.add_middleware(CORSMiddleware, allow_origins=config.origins, allow_credentials=True,
                       allow_methods=['GET','POST','PUT','DELETE'],
                       allow_headers=['Content-Type','X-CSRF-Token','Idempotency-Key','X-Filename','Authorization'])
    app.add_middleware(RequestLimits, upload_limit=config.max_attachment_bytes)

    @app.middleware('http')
    async def safeguards(request, call_next):
        origin = request.headers.get('origin')
        if origin and origin not in config.origins:
            response = JSONResponse({'message':'المصدر غير مصرح له.'}, status_code=403)
        else:
            response = await call_next(request)
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'same-origin'
        response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
        if config.app_env == 'production':
            response.headers['Strict-Transport-Security'] = 'max-age=31536000'
        if request.url.path == '/api/docs' and config.app_env != 'production':
            response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' https://cdn.jsdelivr.net 'unsafe-inline'; style-src 'self' https://cdn.jsdelivr.net 'unsafe-inline'; img-src 'self' data: https://fastapi.tiangolo.com; connect-src 'self'; frame-ancestors 'none'"
        elif request.url.path.startswith('/api/'):
            response.headers['Content-Security-Policy'] = "default-src 'none'; frame-ancestors 'none'; sandbox"
        else:
            response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        return response

    @app.exception_handler(RuleError)
    async def business_error(_, error):
        return JSONResponse({'message': error.message}, status_code=error.status)

    @app.exception_handler(RequestValidationError)
    async def invalid_input(_, error):
        errors = []
        for item in error.errors():
            message = item['msg']
            if message.startswith('Value error, '):
                message = message[len('Value error, '):]
            elif item['type'] == 'missing':
                message = 'هذا الحقل إلزامي.'
            elif item['type'] in {'string_too_short','string_too_long'}:
                message = 'طول النص غير صحيح؛ أكمل الحقل وفق المطلوب.'
            else:
                message = 'قيمة الحقل غير صحيحة أو خارج الحد المسموح.'
            errors.append({'field': '.'.join(str(x) for x in item['loc'][1:]), 'message': message})
        return JSONResponse({'message': 'راجع البيانات المطلوبة: '+errors[0]['message'], 'errors': errors}, status_code=422)

    @app.exception_handler(IntegrityError)
    async def duplicate_or_constraint(_, __):
        return JSONResponse({'message':'تعذر الحفظ بسبب تكرار سجل أو مخالفة قيد مالي. أعد فتح البيانات وراجع المراجع.'}, status_code=409)

    @app.exception_handler(OperationalError)
    async def unavailable_database(_, __):
        return JSONResponse({'message':'تعذر الاتصال بقاعدة البيانات أو إكمال المعاملة. لم يؤكد الحفظ؛ أعد المحاولة بالمفتاح نفسه.'}, status_code=503)

    def change(request, data, operation, admin=False):
        identity = authenticate(request, admin=admin)
        return mutate(factory, identity.id, request.headers.get('Idempotency-Key'),
                      {'path':request.url.path, 'query':str(request.url.query),
                       'data':data.model_dump(mode='json') if hasattr(data,'model_dump') else data},
                      operation, config.idempotency_secret, admin=admin)

    def service_identity(request):
        expected = 'Bearer '+config.n8n_api_token
        supplied = request.headers.get('Authorization','')
        if len(config.n8n_api_token) < 32 or not hmac.compare_digest(supplied.encode(), expected.encode()):
            raise RuleError('رمز خدمة الإشعارات غير صالح.',401)

    def service_change(request, data, operation):
        service_identity(request)
        return mutate(factory, None, request.headers.get('Idempotency-Key'),
                      {'path':request.url.path,'query':str(request.url.query),'data':data},
                      operation, config.idempotency_secret, service=True)

    api = APIRouter(prefix='/api')

    def report_range(month,day,from_date=None,to_date=None):
        if day==date.max or to_date==date.max:
            raise RuleError('نهاية الفترة تتجاوز نطاق التواريخ المدعوم.')
        if sum([bool(month),bool(day),bool(from_date or to_date)])>1:
            raise RuleError('اختر يومًا أو شهرًا أو نطاقًا مخصصًا واحدًا.')
        if from_date or to_date:
            if not from_date or not to_date or to_date<from_date:
                raise RuleError('أدخل بداية ونهاية نطاق صحيح.')
            return from_date,to_date+timedelta(days=1)
        return (day,day+timedelta(days=1)) if day else notifications_service.month_range(month) if month else (None,None)

    @api.get('/health')
    def health():
        with reading(factory) as db:
            get_or_404(db, Store, 1)
        return {'status':'ok','database':app.state.engine.dialect.name,'version':'2.4.0'}

    @api.post('/auth/login')
    def sign_in(data: LoginInput, request: Request, response: Response):
        user, token, csrf = login(factory, data, request.client.host if request.client else 'unknown', config.session_hours)
        for name, value, http_only in [(COOKIE,token,True),(CSRF_COOKIE,csrf,False)]:
            response.set_cookie(name,value,httponly=http_only,secure=config.cookie_secure,
                                 samesite='strict',max_age=config.session_hours*3600,path='/')
        return {'user':user}

    @api.get('/auth/me')
    def me(request: Request):
        identity = authenticate(request)
        with reading(factory) as db:
            user, store = db.get(User,identity.id), db.get(Store,1)
            today = datetime.now(ZoneInfo(store.timezone)).date()
            submitted = services.employee_day_exists(db,user.id,today)
            return wire({'user':public_user(user),'store':{'store_name':store.store_name,'currency':'YER','timezone':store.timezone},
                         'today':today,'submitted_today':submitted})

    @api.post('/auth/logout')
    def logout(request: Request, response: Response):
        identity = authenticate(request)
        change(request,{},lambda db,actor: (db.execute(delete(AuthSession).where(AuthSession.token_hash==identity.token_hash)), {'ok':True})[1])
        response.delete_cookie(COOKIE,path='/')
        response.delete_cookie(CSRF_COOKIE,path='/')
        return {'ok':True}

    @api.post('/shifts')
    def submit_shift(data: ShiftInput, request: Request):
        return change(request,data,lambda db,actor:services.submission(db,actor,data,config))

    @api.get('/shifts')
    def list_shifts(request: Request, month: str | None=None, day: date | None=None,
                    employee_id: int | None=None, status: str='all', q: str='', from_date: date | None=None, to_date: date | None=None):
        authenticate(request,admin=True)
        start,end = report_range(month,day,from_date,to_date)
        with reading(factory) as db:
            records = services.report_data(db,start,end,employee_id)['shifts']
            if status not in {'all','pending','confirmed'}:
                raise RuleError('حالة المطابقة غير صحيحة.')
            return wire([s for s in records if (status=='all' or (status=='confirmed' and s['approved']) or (status=='pending' and not s['approved']))
                         and reference_key(q) in reference_key(f"{s['id']} {s['employee']} {s['business_date']} {s['deposit_number']}")])

    @api.get('/shifts/{identifier}')
    def details(identifier: int, request: Request, version: int | None=None):
        authenticate(request,admin=True)
        with reading(factory) as db:
            return wire(services.shift_detail(db,identifier,version))

    @api.put('/shifts/{identifier}')
    def edit_shift(identifier: int, data: RevisionInput, request: Request):
        return change(request,data,lambda db,actor:services.revise(db,actor,identifier,data,config),admin=True)

    @api.post('/shifts/{identifier}/confirm')
    def confirm_shift(identifier: int, data: ConfirmShiftInput, request: Request):
        return change(request,data,lambda db,actor:services.confirm_shift(db,actor,identifier,data),admin=True)

    @api.post('/attachments')
    async def upload(request: Request):
        authenticate(request)
        content = bytearray()
        async for chunk in request.stream():
            content.extend(chunk)
            if len(content)>config.max_attachment_bytes:
                raise RuleError('حجم المرفق يجب ألا يتجاوز 5 ميجابايت.',413)
        blob = bytes(content)
        mime = 'application/pdf' if blob.startswith(b'%PDF-') else 'image/png' if blob.startswith(b'\x89PNG\r\n\x1a\n') else 'image/jpeg' if blob.startswith(b'\xff\xd8\xff') else None
        if not mime or len(blob)<16:
            raise RuleError('أرفق ملف PDF أو صورة PNG/JPG صالحة فقط.')
        if mime == 'application/pdf':
            from .file_validation import validate_pdf
            from starlette.concurrency import run_in_threadpool
            await run_in_threadpool(validate_pdf, blob)
        if mime.startswith('image/'):
            from PIL import Image
            try:
                with Image.open(io.BytesIO(blob)) as image:
                    if image.width*image.height>20000000:
                        raise ValueError('size')
                    image.verify()
            except Exception:
                raise RuleError('الصورة تالفة أو أكبر من الحد المسموح.') from None
        filename = Path(unquote(request.headers.get('X-Filename','invoice')).replace(chr(92),'/')).name[:150]
        if not filename or any(ord(c)<32 for c in filename):
            raise RuleError('اسم المرفق غير صالح.')
        extensions = {'application/pdf': {'.pdf'}, 'image/png': {'.png'}, 'image/jpeg': {'.jpg', '.jpeg'}}
        if Path(filename).suffix.casefold() not in extensions[mime] or any(
            unicodedata.bidirectional(char) in {'RLO','LRO','RLE','LRE','PDF','FSI','LRI','RLI','PDI'} for char in filename):
            raise RuleError('امتداد واسم المرفق يجب أن يطابقا نوع الملف PDF أو PNG أو JPG دون محارف عرض مخفية.')
        sha = hashlib.sha256(blob).hexdigest()
        def store_file(db,actor):
            file = Attachment(id=str(uuid4()),owner_id=actor.id,filename=filename,mime_type=mime,
                              sha256=sha,size=len(blob),content=blob)
            db.add(file)
            db.flush()
            audit(db,actor,'invoice.uploaded',file,{'sha256':sha,'size':len(blob)})
            return row(file,exclude=('content',))
        return change(request,{'sha256':sha,'filename':filename},store_file)

    @api.get('/attachments/{identifier}')
    def download_attachment(identifier: str, request: Request):
        authenticate(request,admin=True)
        with reading(factory) as db:
            file = get_or_404(db,Attachment,identifier)
            return Response(file.content,media_type=file.mime_type,headers={
                'Content-Disposition':"attachment; filename*=UTF-8''"+quote(file.filename)})

    @api.get('/reports')
    def report(request: Request, month: str | None=None, day: date | None=None, employee_id: int | None=None, from_date: date | None=None, to_date: date | None=None):
        authenticate(request,admin=True)
        start,end = report_range(month,day,from_date,to_date)
        with reading(factory) as db:
            return wire(services.report_data(db,start,end,employee_id))

    @api.get('/reports/analytics')
    def monthly_analytics(request: Request, month: str, months: int = Query(default=6, ge=1, le=24),
                          employee_id: int | None = Query(default=None, ge=1)):
        authenticate(request, admin=True)
        with reading(factory) as db:
            return wire(services.analytics_data(db, month, months, employee_id))

    @api.get('/reports/export.{extension}')
    def export_report(extension: str, request: Request, month: str | None=None, day: date | None=None, employee_id: int | None=None, from_date: date | None=None, to_date: date | None=None):
        authenticate(request,admin=True)
        start,end = report_range(month,day,from_date,to_date)
        with reading(factory) as db:
            data = services.report_data(db,start,end,employee_id)
            from .reports import report_csv, report_pdf
            if extension == 'pdf':
                return Response(report_pdf(data),media_type='application/pdf',headers={'Content-Disposition':'attachment; filename="bin-doul-report.pdf"'})
            if extension == 'csv':
                return Response(report_csv(data),media_type='text/csv; charset=utf-8',headers={'Content-Disposition':'attachment; filename="bin-doul-report.csv"'})
            raise RuleError('التصدير يدعم PDF وCSV فقط.',404)

    @api.get('/shifts/{identifier}/export.pdf')
    def shift_pdf(identifier: int, request: Request):
        authenticate(request,admin=True)
        from .reports import shift_pdf as render_shift
        with reading(factory) as db:
            detail = services.shift_detail(db,identifier)
            return Response(render_shift(detail,row(db.get(Store,1))),media_type='application/pdf',headers={'Content-Disposition':f'attachment; filename="shift-{identifier}.pdf"'})

    @api.get('/users')
    def users(request: Request):
        authenticate(request,admin=True)
        with reading(factory) as db:
            return [public_user(u) for u in db.scalars(select(User).order_by(User.id))]

    @api.post('/users')
    def create_user(data: UserInput, request: Request):
        def operation(db,actor):
            user = User(username=data.username,full_name=data.full_name,role=data.role,
                        password_hash=hasher.hash(data.password),created_by=actor.id)
            db.add(user)
            db.flush()
            audit(db,actor,'user.created',user,public_user(user))
            return public_user(user)
        return change(request,data,operation,admin=True)

    @api.put('/users/{identifier}')
    def update_user(identifier: int, data: UserUpdate, request: Request):
        def operation(db,actor):
            user = get_or_404(db,User,identifier)
            if not user.active:
                raise RuleError('الحساب محذوف؛ أنشئ حسابًا جديدًا باسم مختلف.')
            if actor.id == user.id and data.role != 'admin':
                raise RuleError('لا يمكنك إزالة صلاحية المدير من حسابك الحالي.')
            user.full_name,user.role = data.full_name,data.role
            if data.password:
                user.password_hash = hasher.hash(data.password)
            db.execute(delete(AuthSession).where(AuthSession.user_id==user.id))
            audit(db,actor,'user.updated',user,public_user(user))
            return public_user(user)
        return change(request,data,operation,admin=True)

    @api.delete('/users/{identifier}')
    def remove_user(identifier: int, request: Request):
        def operation(db,actor):
            user = get_or_404(db,User,identifier)
            if actor.id == user.id:
                raise RuleError('لا يمكنك حذف حسابك الحالي.')
            user.active=False
            db.execute(delete(AuthSession).where(AuthSession.user_id==user.id))
            audit(db,actor,'user.disabled',user,{'records_preserved':True})
            return {'disabled':True}
        return change(request,{},operation,admin=True)

    @api.get('/settings')
    def settings(request: Request):
        authenticate(request,admin=True)
        with reading(factory) as db:
            return {**row(db.get(Store,1)),'channels':config.channels,'password_min_length':8,
                    'opening_locked':bool(db.scalar(select(Approval.id).limit(1)))}

    @api.put('/settings')
    def save_settings(data: SettingsInput, request: Request):
        def operation(db,actor):
            try:
                ZoneInfo(data.timezone)
            except (ZoneInfoNotFoundError,ValueError):
                raise RuleError('المنطقة الزمنية غير صحيحة.') from None
            store=db.get(Store,1)
            if data.initial_opening_cash != store.initial_opening_cash and db.scalar(select(Approval.id).limit(1)):
                raise RuleError('لا يمكن تغيير العهدة الأولى بعد اعتماد أول وردية؛ لا تعدّل الرصيد الافتتاحي بصمت.',409)
            before=row(store)
            store.store_name,store.timezone,store.initial_opening_cash=data.store_name,data.timezone,data.initial_opening_cash
            audit(db,actor,'settings.updated',store,{'before':before,'after':row(store)})
            return row(store)
        return change(request,data,operation,admin=True)

    @api.get('/audit')
    def logs(request: Request):
        authenticate(request,admin=True)
        with reading(factory) as db:
            return [row(a) for a in db.scalars(select(AuditLog).order_by(AuditLog.id.desc()).limit(200))]

    @api.get('/notifications')
    def deliveries(request: Request):
        authenticate(request,admin=True)
        with reading(factory) as db:
            return [{'delivery':row(d),'event':row(e)} for d,e in db.execute(select(NotificationDelivery,NotificationEvent)
                     .join(NotificationEvent,NotificationDelivery.event_id==NotificationEvent.id)
                     .order_by(NotificationDelivery.id.desc()).limit(300))]

    @api.post('/notifications/{identifier}/retry')
    def retry_delivery(identifier: int, data: RetryInput, request: Request):
        return change(request,data,lambda db,actor:notifications_service.retry(db,actor,identifier,data.reason),admin=True)

    @api.post('/notifications/monthly')
    def queue_reports(request: Request, month: str | None=None):
        return change(request,{'month':month},lambda db,actor:notifications_service.monthly_reports(db,config,month),admin=True)

    @api.post('/integrations/outbox/claim')
    def claim_delivery(request: Request):
        service_identity(request)
        return wire(notifications_service.claim(factory,config,request.headers.get('Idempotency-Key')))

    @api.post('/integrations/deliveries/{identifier}/result')
    def confirm_delivery(identifier: int, data: DeliveryResult, request: Request):
        return service_change(request,data.model_dump(),lambda db,_:notifications_service.result(db,identifier,data))

    @api.post('/integrations/monthly-reports')
    def scheduled_reports(request: Request, month: str | None=None):
        return service_change(request,{'month':month},lambda db,_:notifications_service.monthly_reports(db,config,month))

    @api.get('/integrations/events/{identifier}/report.pdf')
    def scheduled_pdf(identifier: int, request: Request):
        service_identity(request)
        with reading(factory) as db:
            event=get_or_404(db,NotificationEvent,identifier)
            if event.kind!='monthly_report':
                raise RuleError('هذا الحدث ليس تقريرًا شهريًا.',404)
            from .reports import report_pdf
            payload=json.loads(event.payload_json)
            return Response(report_pdf(payload['report']),media_type='application/pdf',headers={'Content-Disposition':f'attachment; filename="employee-{payload["employee_id"]}-{payload["month"]}.pdf"'})

    app.include_router(api)
    dist=ROOT/'frontend'/'dist'
    if dist.is_dir():
        app.mount('/',StaticFiles(directory=dist,html=True),name='frontend')
    return app
