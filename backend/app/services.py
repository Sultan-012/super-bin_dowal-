import json
from datetime import date
from decimal import Decimal
from sqlalchemy import func, select
from .common import audit, get_or_404, json_text, row, wire
from .finance import ZERO, RuleError, calculate, money
from .models import (CashMovement, CashSession, ClosingSnapshot, Customer,
                     CustomerDebt, DebtPayment, Purchase, Store, User, utcnow)

UNSET = object()


def sum_amount(db, model, *conditions):
    return money(db.scalar(select(func.coalesce(func.sum(model.amount), 0)).where(*conditions)) or ZERO)


def debt_balance(db, debt):
    paid = sum_amount(db, DebtPayment, DebtPayment.debt_id == debt.id, DebtPayment.cancelled_at.is_(None))
    remaining = money(debt.amount - paid) if debt.cancelled_at is None else ZERO
    return {'paid': paid, 'remaining': remaining,
            'debt_status': 'cancelled' if debt.cancelled_at else 'paid' if remaining == ZERO else 'unpaid' if paid == ZERO else 'partial'}


def metrics(db, session, actual=UNSET):
    sid = session.id
    active_move = (CashMovement.session_id == sid, CashMovement.cancelled_at.is_(None))
    movement = {kind: sum_amount(db, CashMovement, *active_move, CashMovement.kind == kind)
                for kind in ['collection', 'purchase', 'expense', 'withdrawal', 'deposit', 'refund']}
    credit = sum_amount(db, CustomerDebt, CustomerDebt.session_id == sid, CustomerDebt.cancelled_at.is_(None))
    active_pay = (DebtPayment.session_id == sid, DebtPayment.cancelled_at.is_(None))
    card = sum_amount(db, DebtPayment, *active_pay, DebtPayment.payment_method == 'card')
    bank = sum_amount(db, DebtPayment, *active_pay, DebtPayment.payment_method == 'bank')
    stale = session.actual_cash is not None and session.count_version != session.version
    counted = (None if stale else session.actual_cash) if actual is UNSET else actual
    result = calculate(opening=session.opening_cash, total=session.total_sales, pos=session.pos_sales,
                       credit=credit, collections=movement['collection'], deposits=movement['deposit'],
                       purchases=movement['purchase'], expenses=movement['expense'],
                       withdrawals=movement['withdrawal'], refunds=movement['refund'], actual=counted)
    return dict(id=sid, business_date=session.business_date, status=session.status, version=session.version,
                opening_cash=session.opening_cash, total_sales=session.total_sales, pos_sales=session.pos_sales,
                new_credit_sales=credit, cash_collections=movement['collection'], card_collections=card,
                bank_collections=bank, noncash_collections=money(card + bank), cash_purchases=movement['purchase'],
                cash_expenses=movement['expense'], deposits=movement['deposit'], withdrawals=movement['withdrawal'],
                cash_refunds=movement['refund'], actual_cash=session.actual_cash if actual is UNSET else actual,
                counted_at=session.counted_at, count_stale=stale if actual is UNSET else False,
                **result)


def session_detail(db, session):
    result = row(session)
    result['totals'] = wire(metrics(db, session))
    result['responsible_name'] = db.get(User, session.responsible_user_id).full_name
    result['debts'] = [dict(row(d), **wire(debt_balance(db, d)), customer_name=db.get(Customer, d.customer_id).name)
                       for d in db.scalars(select(CustomerDebt).where(CustomerDebt.session_id == session.id).order_by(CustomerDebt.id.desc()))]
    result['payments'] = []
    for p in db.scalars(select(DebtPayment).where(DebtPayment.session_id == session.id).order_by(DebtPayment.id.desc())):
        debt = db.get(CustomerDebt, p.debt_id)
        result['payments'].append(dict(row(p), customer_name=db.get(Customer, debt.customer_id).name))
    result['purchases'] = [row(p) for p in db.scalars(select(Purchase).where(Purchase.session_id == session.id).order_by(Purchase.id.desc()))]
    result['movements'] = [row(m) for m in db.scalars(select(CashMovement).where(CashMovement.session_id == session.id).order_by(CashMovement.id.desc()))]
    result['snapshots'] = [dict(row(s, exclude=('totals_json',)), totals=json.loads(s.totals_json)) for s in
                           db.scalars(select(ClosingSnapshot).where(ClosingSnapshot.session_id == session.id).order_by(ClosingSnapshot.id.desc()))]
    return result


def require_open(db, sid, transaction_date=None):
    session = get_or_404(db, CashSession, sid)
    if session.status != 'open':
        raise RuleError('الجلسة مغلقة؛ لا يمكن إضافة أو تعديل حركاتها', 409)
    if transaction_date is not None and transaction_date != session.business_date:
        raise RuleError('تاريخ الحركة يجب أن يطابق تاريخ عمل الجلسة التي استلمت أو دفعت المبلغ')
    return session


def require_version(session, expected):
    if session.version != expected:
        raise RuleError('تغيّرت بيانات الجلسة. حدّث الصفحة وراجع المبالغ ثم أعد المحاولة', 409)


def bump(session):
    session.version += 1
    session.updated_at = utcnow()


def create_session(db, actor, data):
    if db.scalar(select(CashSession.id).where(CashSession.status == 'open')):
        raise RuleError('أغلق الجلسة المفتوحة قبل فتح يوم جديد', 409)
    latest = db.scalar(select(CashSession).order_by(CashSession.business_date.desc()).limit(1))
    if latest:
        if data.business_date <= latest.business_date:
            raise RuleError('تاريخ اليوم الجديد يجب أن يلي آخر جلسة مسجلة', 409)
        opening = latest.actual_cash
        if opening is None:
            raise RuleError('الجلسة السابقة لا تحتوي على جرد معتمد', 409)
        if data.opening_cash is not None and data.opening_cash != opening:
            raise RuleError('رصيد الافتتاح يُرحّل من النقد الفعلي المعتمد للجلسة السابقة ولا يُعدّل يدويًا')
    else:
        if data.opening_cash is None:
            raise RuleError('أدخل رصيد افتتاح الصندوق لأول جلسة')
        opening = data.opening_cash
    session = CashSession(business_date=data.business_date, opening_cash=opening,
                          previous_session_id=latest.id if latest else None,
                          responsible_user_id=actor.id, created_by=actor.id, notes=data.notes)
    db.add(session)
    db.flush()
    audit(db, actor, 'open_session', session, after=row(session))
    return session_detail(db, session)


def update_sales(db, actor, sid, data):
    session = require_open(db, sid)
    require_version(session, data.expected_version)
    before = row(session)
    credit = sum_amount(db, CustomerDebt, CustomerDebt.session_id == sid, CustomerDebt.cancelled_at.is_(None))
    calculate(opening=session.opening_cash, total=data.total_sales, pos=data.pos_sales, credit=credit)
    session.total_sales, session.pos_sales, session.notes = data.total_sales, data.pos_sales, data.notes
    bump(session)
    db.flush()
    metrics(db, session)  # Rechecks total >= POS + detailed credit sales.
    audit(db, actor, 'update_sales', session, before, row(session))
    return session_detail(db, session)


def count_cash(db, actor, sid, data, close=False):
    session = require_open(db, sid)
    require_version(session, data.expected_version)
    if close and data.actual_cash is None:
        raise RuleError('بانتظار الجرد؛ يجب إدخال النقد الفعلي قبل إغلاق الجلسة')
    approved = metrics(db, session, data.actual_cash)
    if close and approved['difference'] != ZERO and not data.note.strip():
        raise RuleError('أدخل ملاحظة توضح سبب العجز أو الفائض قبل الإغلاق')
    before = row(session)
    session.actual_cash = data.actual_cash
    session.counted_at = utcnow() if data.actual_cash is not None else None
    session.counted_by = actor.id if data.actual_cash is not None else None
    session.count_version = session.version if data.actual_cash is not None else None
    if close:
        session.status, session.closed_at, session.closed_by = 'closed', utcnow(), actor.id
        approved.update(status='closed', counted_at=session.counted_at)
        db.add(ClosingSnapshot(session_id=sid, approved_by=actor.id,
                               totals_json=json_text(approved), note=data.note))
    db.flush()
    audit(db, actor, 'close_session' if close else 'count_cash', session, before, row(session), data.note if close else '')
    return session_detail(db, session)


def reopen_session(db, actor, sid, data):
    session = get_or_404(db, CashSession, sid)
    if session.status != 'closed':
        raise RuleError('الجلسة مفتوحة بالفعل', 409)
    if db.scalar(select(CashSession.id).where(CashSession.business_date > session.business_date)):
        raise RuleError('لا يمكن إعادة الفتح لوجود جلسة لاحقة تعتمد على رصيد الإغلاق', 409)
    before = row(session)
    session.status, session.closed_at, session.closed_by = 'open', None, None
    bump(session)  # An old count never silently becomes a new approved count.
    audit(db, actor, 'reopen_session', session, before, row(session), data.reason)
    return session_detail(db, session)


def save_customer(db, actor, data, cid=None):
    customer = get_or_404(db, Customer, cid) if cid else Customer(created_by=actor.id)
    before = row(customer) if cid else None
    for key, value in data.model_dump().items():
        setattr(customer, key, value)
    db.add(customer)
    db.flush()
    audit(db, actor, 'update_customer' if cid else 'create_customer', customer, before, row(customer))
    return row(customer)


def create_debt(db, actor, data):
    get_or_404(db, Customer, data.customer_id)
    session = None
    if data.kind == 'opening':
        if actor.role != 'admin':
            raise RuleError('أرصدة العملاء الافتتاحية تتطلب صلاحية مدير', 403)
    else:
        session = require_open(db, data.session_id, data.debt_date)
    debt = CustomerDebt(**data.model_dump(), created_by=actor.id)
    db.add(debt)
    if session:
        bump(session)
    db.flush()
    if session:
        metrics(db, session)
    audit(db, actor, 'create_debt', debt, after=row(debt))
    return dict(row(debt), **wire(debt_balance(db, debt)))


def generated_movement(db, actor, *, session, kind, amount, description, purchase_id=None, debt_payment_id=None):
    movement = CashMovement(session_id=session.id, movement_date=session.business_date,
                            kind=kind, amount=amount, description=description,
                            responsible_user_id=actor.id, created_by=actor.id,
                            purchase_id=purchase_id, debt_payment_id=debt_payment_id)
    db.add(movement)
    db.flush()
    return movement


def create_payment(db, actor, data):
    session = require_open(db, data.session_id, data.payment_date)
    debt = get_or_404(db, CustomerDebt, data.debt_id)
    if debt.cancelled_at:
        raise RuleError('لا يمكن سداد دين ملغى')
    if data.payment_date < debt.debt_date:
        raise RuleError('تاريخ التحصيل لا يمكن أن يسبق تاريخ الدين')
    remaining = debt_balance(db, debt)['remaining']
    if data.amount > remaining:
        raise RuleError(f'مبلغ السداد يتجاوز الرصيد المتبقي ({remaining:.2f})')
    payment = DebtPayment(**data.model_dump(), created_by=actor.id)
    db.add(payment)
    db.flush()
    if data.payment_method == 'cash':
        generated_movement(db, actor, session=session, kind='collection', amount=data.amount,
                           description=f'تحصيل دين #{debt.id}', debt_payment_id=payment.id)
    bump(session)
    db.flush()
    metrics(db, session)
    audit(db, actor, 'create_payment', payment, after=row(payment))
    return dict(row(payment), debt=wire(debt_balance(db, debt)))


def create_purchase(db, actor, data):
    session = require_open(db, data.session_id, data.purchase_date)
    purchase = Purchase(**data.model_dump(), created_by=actor.id)
    db.add(purchase)
    db.flush()
    if data.from_drawer:
        generated_movement(db, actor, session=session, kind='purchase', amount=data.amount,
                           description=data.description, purchase_id=purchase.id)
    bump(session)
    db.flush()
    metrics(db, session)
    audit(db, actor, 'create_purchase', purchase, after=row(purchase))
    return row(purchase)


def create_movement(db, actor, data):
    session = require_open(db, data.session_id, data.movement_date)
    movement = CashMovement(**data.model_dump(), created_by=actor.id, responsible_user_id=actor.id)
    db.add(movement)
    bump(session)
    db.flush()
    metrics(db, session)
    audit(db, actor, 'create_movement', movement, after=row(movement))
    return row(movement)


def cancel_record(db, actor, category, identifier, reason):
    models = {'debts': CustomerDebt, 'payments': DebtPayment, 'purchases': Purchase, 'movements': CashMovement}
    if category not in models:
        raise RuleError('نوع السجل غير صالح', 404)
    obj = get_or_404(db, models[category], identifier)
    if obj.cancelled_at:
        raise RuleError('السجل ملغى بالفعل', 409)
    if isinstance(obj, CashMovement) and (obj.purchase_id or obj.debt_payment_id):
        raise RuleError('ألغِ السداد أو المشتريات الأصلية؛ لا تُلغى الحركة المرتبطة منفردة')
    session = require_open(db, obj.session_id) if obj.session_id else None
    if isinstance(obj, CustomerDebt) and debt_balance(db, obj)['paid'] > ZERO:
        raise RuleError('لا يمكن إلغاء دين له دفعات سداد صحيحة')
    before = row(obj)
    obj.cancelled_at, obj.cancelled_by, obj.cancellation_reason = utcnow(), actor.id, reason
    if isinstance(obj, (Purchase, DebtPayment)):
        condition = CashMovement.purchase_id == obj.id if isinstance(obj, Purchase) else CashMovement.debt_payment_id == obj.id
        movement = db.scalar(select(CashMovement).where(condition))
        if movement:
            movement.cancelled_at, movement.cancelled_by, movement.cancellation_reason = obj.cancelled_at, actor.id, reason
            audit(db, actor, 'cancel_generated_movement', movement, after=row(movement), reason=reason)
    if session:
        bump(session)
    db.flush()
    if session:
        metrics(db, session)
    audit(db, actor, 'cancel_' + category, obj, before, row(obj), reason)
    return row(obj)


def customer_statement(db, cid):
    customer = get_or_404(db, Customer, cid)
    debts, payments, entries = [], [], []
    original, paid, outstanding = ZERO, ZERO, ZERO
    for debt in db.scalars(select(CustomerDebt).where(CustomerDebt.customer_id == cid).order_by(CustomerDebt.debt_date, CustomerDebt.id)):
        balance = debt_balance(db, debt)
        debts.append(dict(row(debt), **wire(balance)))
        if not debt.cancelled_at:
            original += debt.amount
            outstanding += balance['remaining']
        entries.append(dict(kind='debt', date=debt.debt_date, created_at=debt.created_at,
                            id=debt.id, amount=debt.amount, cancelled=bool(debt.cancelled_at), debt_kind=debt.kind))
        for p in db.scalars(select(DebtPayment).where(DebtPayment.debt_id == debt.id).order_by(DebtPayment.payment_date, DebtPayment.id)):
            payments.append(dict(row(p), recorded_by_name=db.get(User, p.created_by).full_name))
            if not p.cancelled_at:
                paid += p.amount
            entries.append(dict(kind='payment', date=p.payment_date, created_at=p.created_at,
                                id=p.id, debt_id=debt.id, amount=p.amount, payment_method=p.payment_method,
                                cancelled=bool(p.cancelled_at)))
    running = ZERO
    for e in sorted(entries, key=lambda x: (x['date'], x['created_at'], x['kind'] == 'payment', x['id'])):
        if not e['cancelled']:
            running += e['amount'] if e['kind'] == 'debt' else -e['amount']
        e['running_balance'] = money(running)
    entries.sort(key=lambda x: (x['date'], x['created_at'], x['kind'] == 'payment', x['id']))
    return wire(dict(customer=row(customer), debts=debts, payments=payments, entries=entries,
                     original=money(original), paid=money(paid), outstanding=money(outstanding)))


FLOW_FIELDS = ['total_sales', 'cash_sales', 'pos_sales', 'new_credit_sales', 'cash_collections',
               'card_collections', 'bank_collections', 'noncash_collections', 'cash_purchases',
               'cash_expenses', 'deposits', 'withdrawals', 'cash_refunds']


def report(db, start: date, end: date):
    if end < start:
        raise RuleError('نهاية الفترة يجب ألا تسبق بدايتها')
    if (end - start).days > 366:
        raise RuleError('اختر فترة لا تتجاوز 367 يومًا لكل تقرير')
    sessions = list(db.scalars(select(CashSession).where(CashSession.business_date.between(start, end)).order_by(CashSession.business_date)))
    daily = []
    for s in sessions:
        if s.status == 'closed':
            snapshot = db.scalar(select(ClosingSnapshot).where(ClosingSnapshot.session_id == s.id).order_by(ClosingSnapshot.id.desc()).limit(1))
            totals = json.loads(snapshot.totals_json)
            for f in FLOW_FIELDS + ['opening_cash', 'expected_cash', 'actual_cash', 'difference']:
                totals[f] = Decimal(totals[f]) if totals.get(f) is not None else None
        else:
            totals = metrics(db, s)
        daily.append(totals)
    totals = {field: money(sum((d[field] for d in daily), ZERO)) for field in FLOW_FIELDS}
    differences = [d['difference'] for d in daily if d['status'] == 'closed' and d['difference'] is not None]
    totals.update(total_shortages=money(-sum((d for d in differences if d < ZERO), ZERO)),
                  total_surpluses=money(sum((d for d in differences if d > ZERO), ZERO)),
                  net_difference=money(sum(differences, ZERO)))
    last_count = db.scalar(select(CashSession).where(CashSession.business_date.between(start, end), CashSession.actual_cash.is_not(None))
                           .order_by(CashSession.business_date.desc()).limit(1))
    outstanding = ZERO
    for debt in db.scalars(select(CustomerDebt).where(CustomerDebt.cancelled_at.is_(None))):
        outstanding += debt_balance(db, debt)['remaining']
    latest = daily[-1] if daily else None
    transactions = transaction_list(db, start, end)
    store = db.get(Store, 1)
    return wire(dict(start=start, end=end, totals=totals, daily=daily, session_count=len(sessions),
                     closed_count=sum(s.status == 'closed' for s in sessions),
                     balance_at_end=dict(business_date=latest['business_date'], opening_cash=latest['opening_cash'],
                                         expected_cash=latest['expected_cash'], status=latest['status'],
                                         difference=latest['difference'], reconciliation_message=latest['reconciliation_message']) if latest else None,
                     last_count=dict(business_date=last_count.business_date, amount=last_count.actual_cash,
                                     counted_at=last_count.counted_at, stale=last_count.count_version != last_count.version or (bool(sessions) and last_count.id != sessions[-1].id),
                                     session_id=last_count.id) if last_count else None,
                     outstanding_debts_now=money(outstanding), outstanding_as_of=utcnow(),
                     recent_transactions=transactions[:12], currency=store.currency, timezone=store.timezone))


def transaction_list(db, start, end, session_id=None):
    result = []
    configs = [(Purchase, Purchase.purchase_date, 'purchase'), (DebtPayment, DebtPayment.payment_date, 'collection'),
               (CashMovement, CashMovement.movement_date, 'movement'), (CustomerDebt, CustomerDebt.debt_date, 'debt')]
    for model, column, kind in configs:
        query = select(model).where(column.between(start, end))
        if session_id:
            query = query.where(model.session_id == session_id)
        for obj in db.scalars(query):
            if isinstance(obj, CashMovement) and (obj.purchase_id or obj.debt_payment_id):
                continue  # Generated cash effect has one visible source transaction.
            description = getattr(obj, 'description', None)
            if isinstance(obj, DebtPayment):
                debt = db.get(CustomerDebt, obj.debt_id)
                description = 'تحصيل من ' + db.get(Customer, debt.customer_id).name
            if isinstance(obj, CustomerDebt):
                description = ('رصيد افتتاحي: ' if obj.kind == 'opening' else 'بيع آجل: ') + db.get(Customer, obj.customer_id).name
            entry = row(obj)
            entry.update(category=kind, description=description, date=getattr(obj, column.key),
                         recorded_by_name=db.get(User, obj.created_by).full_name)
            result.append(entry)
    return sorted(result, key=lambda x: (str(x['date']), x['created_at'], x['id']), reverse=True)
