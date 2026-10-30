import json
from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo
from sqlalchemy import func, select
from .common import audit, digest, get_or_404, json_text, row, wire
from .finance import ZERO, RuleError, calculate, reference_key
from .models import (Approval, Attachment, Customer, CustomerDebt, DebtPayment, Entry,
                     InvoiceReview, ReferenceReservation, Shift, ShiftVersion, Store, User, utcnow)

VERSION_FIELDS = ('business_date', 'deposit_date', 'deposit_number', 'deposit_amount', 'device_sales', 'notes')
ENTRY_FIELDS = ('line_key', 'kind', 'name', 'amount', 'reference', 'description', 'item_code',
                'quantity', 'invoice_number', 'invoice_total', 'purpose', 'attachment_id')


def version_for(db, shift, number=None):
    version = db.scalar(select(ShiftVersion).where(ShiftVersion.shift_id == shift.id,
                        ShiftVersion.number == (number or shift.current_version)))
    if not version:
        raise RuleError('نسخة الوردية غير موجودة.', 404)
    return version


def entries_for(db, version):
    return list(db.scalars(select(Entry).where(Entry.version_id == version.id).order_by(Entry.id)))


def entry_values(entry):
    return {name: getattr(entry, name) for name in ENTRY_FIELDS}


def version_values(version):
    return {name: getattr(version, name) for name in VERSION_FIELDS}


def totals_for(db, version):
    snapshot=db.scalar(select(Approval).where(Approval.version_id==version.id))
    if snapshot:
        values=json.loads(snapshot.totals_json)
        for key in ('device_sales','outside_sales','total_sales','purchases','new_debts','shift_bank',
                    'account_bank','total_bank','deposit_amount','opening_cash','pos_sales','retained_cash',
                    'cash_sales','expected_cash','actual_cash','difference','shortage','surplus'):
            if values.get(key) is not None:
                values[key]=Decimal(values[key])
        return values
    return calculate(version_values(version), [entry_values(e) for e in entries_for(db, version)],
                     version.opening_cash, version.pos_sales, version.retained_cash)


def public_totals(values, approved=False):
    """Expose only current, supported metrics; never present legacy cash results
    as a reconciliation performed under the new administrative workflow.
    """
    keep = ('device_sales','outside_sales','total_sales','purchases','shift_bank',
            'total_bank','deposit_amount')
    result = {key: values[key] for key in keep}
    result.update(status='confirmed' if approved else 'pending',
                  message='معتمدة من المدير' if approved else 'بانتظار اعتماد المدير',
                  confirmation_mode=values.get('confirmation_mode','legacy' if approved else None),
                  financial_variance_calculated=False)
    return result


def check_version(shift, expected):
    if shift.current_version != expected:
        raise RuleError('تغيرت نسخة الوردية. أعد فتح أحدث نسخة قبل المتابعة.', 409)


def employee_day_exists(db, employee_id, business_date, excluding_id=None):
    query=select(Shift.id).outerjoin(ShiftVersion,
            (ShiftVersion.shift_id==Shift.id)&(ShiftVersion.number==Shift.approved_version)).where(
            Shift.employee_id==employee_id,
            (Shift.business_date==business_date)|(ShiftVersion.business_date==business_date))
    if excluding_id is not None:
        query=query.where(Shift.id!=excluding_id)
    return db.scalar(query.limit(1)) is not None


def reserve(db, kind, key, shift_id):
    hashed = digest(json_text(key))
    existing = db.scalar(select(ReferenceReservation).where(
        ReferenceReservation.kind == kind, ReferenceReservation.normalized_key == hashed))
    if existing and existing.shift_id != shift_id:
        raise RuleError('رقم سند إيداع أو حوالة أو فاتورة مسجل في وردية أخرى. راجع المرجع.', 409)
    if not existing:
        db.add(ReferenceReservation(kind=kind, normalized_key=hashed, shift_id=shift_id))


def persist_version(db, actor, shift, data, reason, counts=None, copied_reviews=None):
    values = {key: data[key] for key in VERSION_FIELDS}
    version = ShiftVersion(shift_id=shift.id, number=shift.current_version, **values,
                           reason=reason, created_by=actor.id,
                           opening_cash=counts[0] if counts else None,
                           pos_sales=counts[1] if counts else None,
                           retained_cash=counts[2] if counts else None)
    db.add(version)
    db.flush()
    reserve(db, 'deposit', reference_key(data['deposit_number']), shift.id)
    for raw in data['entries']:
        item = {key: raw.get(key) for key in ENTRY_FIELDS}
        item['line_key'] = str(item['line_key'])
        item['attachment_id'] = str(item['attachment_id']) if item['attachment_id'] else None
        key_owner = db.scalar(select(ShiftVersion.shift_id).join(Entry, Entry.version_id == ShiftVersion.id)
                              .where(Entry.line_key == item['line_key']).limit(1))
        if key_owner is not None and key_owner != shift.id:
            raise RuleError('معرّف صف مستخدم في وردية أخرى.', 409)
        if item['attachment_id']:
            attachment = get_or_404(db, Attachment, item['attachment_id'])
            if attachment.shift_id not in (None, shift.id) or (attachment.shift_id is None and attachment.owner_id != actor.id):
                raise RuleError('المرفق غير متاح لهذه الوردية.', 403)
            attachment.shift_id = shift.id
        if item['kind'] == 'purchase' and item['invoice_number']:
            reserve(db, 'purchase', [reference_key(item['name']), reference_key(item['invoice_number'])], shift.id)
        if item['kind'] == 'bank':
            reserve(db, 'bank', reference_key(item['reference']), shift.id)
        if item['kind'] == 'debt' and item['invoice_number']:
            reserve(db, 'credit_invoice', [reference_key(item['name']), reference_key(item['invoice_number'])], shift.id)
        entry = Entry(version_id=version.id, **item)
        db.add(entry)
        db.flush()
        previous = (copied_reviews or {}).get(entry.line_key)
        db.add(InvoiceReview(entry_id=entry.id, status=previous.status if previous else 'pending',
                             note=previous.note if previous else '', debt_id=previous.debt_id if previous else None,
                             reviewed_by=previous.reviewed_by if previous else None,
                             reviewed_at=previous.reviewed_at if previous else None))
    db.flush()
    return version


def input_values(data):
    return data.model_dump(mode='python', exclude={'expected_version', 'reason'})


def submission(db, actor, data, config):
    values = input_values(data)
    today = datetime.now(ZoneInfo(db.get(Store, 1).timezone)).date()
    if data.business_date > today:
        raise RuleError('تاريخ الصندوق لا يمكن أن يكون في المستقبل.')
    calculate(values, values['entries'])
    shift = Shift(employee_id=actor.id, business_date=data.business_date, current_version=1)
    db.add(shift)
    db.flush()
    version = persist_version(db, actor, shift, values, 'التسليم الأول من الموظف')
    audit(db, actor, 'shift.submitted', shift, {'version': 1})
    outside_event(db, shift, version, config)
    # Intentionally no ID, balances, amounts or data echo for blind employee entry.
    return {'submitted': True, 'message': 'تم تسليم الوردية للمدير بنجاح.'}


def outside_event(db, shift, version, config):
    from .notifications import enqueue
    items = [entry_values(e) for e in entries_for(db, version) if e.kind == 'off_device']
    if items:
        employee = db.get(User, shift.employee_id)
        enqueue(db, config, f'shift:{shift.id}:v{version.number}:off-device', 'off_device_sales',
                dict(shift_id=shift.id, version=version.number, business_date=version.business_date,
                     employee_id=employee.id, employee=employee.full_name,
                     items=[{k: x[k] for k in ('name','item_code','quantity','amount')} for x in items]), shift.id)


def revise(db, actor, identifier, data, config):
    shift = get_or_404(db, Shift, identifier)
    check_version(shift, data.expected_version)
    prior_version = version_for(db, shift)
    prior_entries = entries_for(db, prior_version)
    if (any(e.kind == 'debt' or (e.kind == 'bank' and e.purpose == 'customer_account') for e in prior_entries)
        or db.scalar(select(CustomerDebt.id).where(CustomerDebt.shift_id == shift.id).limit(1))
        or db.scalar(select(DebtPayment.id).where(DebtPayment.shift_id == shift.id).limit(1))
        or (shift.approved_version and version_for(db, shift, shift.approved_version).retained_cash is not None)):
        raise RuleError('تحتوي الوردية على قيود مالية من الإصدار السابق. يعرض السجل للقراءة فقط حتى تتم مراجعتها محاسبيًا؛ لا يمكن تصحيحها من الواجهة الجديدة.', 409)
    if data.business_date > datetime.now(ZoneInfo(db.get(Store,1).timezone)).date():
        raise RuleError('تاريخ الصندوق لا يمكن أن يكون في المستقبل.')
    values = input_values(data)
    calculate(values, values['entries'])
    previous = version_for(db, shift)
    previous_outside = [wire(entry_values(e)) for e in entries_for(db, previous) if e.kind == 'off_device']
    shift.current_version += 1
    shift.business_date = data.business_date
    version = persist_version(db, actor, shift, values, data.reason)
    audit(db, actor, 'shift.revised', shift, {'old_version': previous.number, 'new_version': version.number, 'reason': data.reason})
    new_outside = [wire(entry_values(e)) for e in entries_for(db, version) if e.kind == 'off_device']
    if previous_outside != new_outside:
        outside_event(db, shift, version, config)
    return {'id': shift.id, 'version': version.number}


def paid_amount(db, debt_id, excluding_shift=None):
    query = select(func.coalesce(func.sum(DebtPayment.amount), ZERO)).where(
        DebtPayment.debt_id == debt_id, DebtPayment.active.is_(True))
    if excluding_shift is not None:
        query = query.where(DebtPayment.shift_id != excluding_shift)
    return db.scalar(query)


def review_invoice(db, actor, entry_id, data):
    entry = get_or_404(db, Entry, entry_id)
    version = db.get(ShiftVersion, entry.version_id)
    shift = db.get(Shift, version.shift_id)
    check_version(shift, data.expected_version)
    if version.number != shift.current_version or shift.approved_version == version.number:
        raise RuleError('هذه نسخة معتمدة أو مؤرشفة؛ أنشئ تصحيحًا جديدًا أولًا.', 409)
    review = db.scalar(select(InvoiceReview).where(InvoiceReview.entry_id == entry.id))
    if data.status == 'matched' and entry.kind == 'bank' and entry.purpose == 'customer_account':
        if not data.debt_id:
            raise RuleError('اختر الدين السابق الذي تخصه الحوالة قبل المطابقة.')
        debt = get_or_404(db, CustomerDebt, data.debt_id)
        customer = db.get(Customer, debt.customer_id)
        if not debt.active or debt.shift_id == shift.id or debt.debt_date > version.business_date:
            raise RuleError('يجب ربط التحويل بدين سابق صالح قبل تاريخ هذه الوردية.')
        if digest(reference_key(entry.name)) != customer.name_key:
            raise RuleError('اسم صاحب التحويل لا يطابق صاحب الدين المحدد. صحح بيانات الوردية أولًا.')
        others = db.scalars(select(Entry).join(InvoiceReview, InvoiceReview.entry_id == Entry.id)
                             .where(Entry.version_id == version.id, Entry.id != entry.id,
                                    InvoiceReview.status == 'matched', InvoiceReview.debt_id == debt.id))
        requested = entry.amount + sum((e.amount for e in others), ZERO)
        if requested > debt.amount - paid_amount(db, debt.id, shift.id):
            raise RuleError('مجموع التسديدات يتجاوز الرصيد المتبقي للدين.')
        review.debt_id = debt.id
    else:
        review.debt_id = None
    before = row(review)
    review.status, review.note = data.status, data.note
    review.reviewed_by, review.reviewed_at = actor.id, utcnow()
    db.flush()
    audit(db, actor, 'invoice.reviewed', entry, {'before': before, 'after': row(review)})
    return {'entry_id': entry.id, 'status': review.status}


def customer_for(db, name):
    key = digest(reference_key(name))
    customer = db.scalar(select(Customer).where(Customer.name_key == key))
    if customer is None:
        customer = Customer(name=name, name_key=key, notes='')
        db.add(customer)
        db.flush()
    return customer


def opening_debt(db, actor, data):
    customer = customer_for(db, data.name)
    duplicate = any(reference_key(d.invoice_number)==reference_key(data.invoice_number)
                    for d in db.scalars(select(CustomerDebt).where(CustomerDebt.customer_id==customer.id,
                                                                   CustomerDebt.active.is_(True))))
    if duplicate:
        raise RuleError('رقم الفاتورة مسجل لهذا العميل بالفعل.', 409)
    debt = CustomerDebt(customer_id=customer.id, invoice_number=data.invoice_number,
                        description=data.description, debt_date=data.debt_date, amount=data.amount,
                        created_by=actor.id)
    db.add(debt)
    db.flush()
    audit(db, actor, 'debt.opening', debt, row(debt))
    return row(debt)


def cancel_opening_debt(db, actor, identifier, reason):
    debt=get_or_404(db,CustomerDebt,identifier)
    if debt.source_key is not None:
        raise RuleError('دين الوردية يصحح من نسخة الوردية الأصلية، لا من الرصيد الافتتاحي.')
    if paid_amount(db,debt.id)>ZERO:
        raise RuleError('لا يمكن عكس دين افتتاحي له تسديدات معتمدة. صحح تسديداته أولًا.',409)
    before=row(debt)
    debt.active=False
    audit(db,actor,'debt.opening-reversed',debt,{'before':before,'reason':reason})
    return {'reversed':True}


def replace_ledger(db, actor, shift, version):
    entries = entries_for(db, version)
    desired_debts = {e.line_key: e for e in entries if e.kind == 'debt'}
    old_debts = list(db.scalars(select(CustomerDebt).where(CustomerDebt.shift_id == shift.id)))
    old_payments = list(db.scalars(select(DebtPayment).where(DebtPayment.shift_id == shift.id)))
    before = {'debts': [row(d) for d in old_debts], 'payments': [row(p) for p in old_payments]}
    for payment in old_payments:
        payment.active = False
    db.flush()
    for debt in old_debts:
        if debt.source_key not in desired_debts:
            if paid_amount(db, debt.id) > ZERO:
                raise RuleError('لا يمكن إلغاء دين له تسديدات لاحقة. راجع تسديداته أولًا.', 409)
            debt.active = False
    for key, entry in desired_debts.items():
        customer = customer_for(db, entry.name)
        duplicate=bool(entry.invoice_number) and any(
            reference_key(d.invoice_number)==reference_key(entry.invoice_number) and d.source_key!=key
            for d in db.scalars(select(CustomerDebt).where(CustomerDebt.customer_id==customer.id,
                                                             CustomerDebt.active.is_(True))))
        if duplicate:
            raise RuleError('فاتورة الدين مسجلة مسبقًا لهذا العميل. راجع الرصيد الافتتاحي والفاتورة قبل الاعتماد.',409)
        debt = db.scalar(select(CustomerDebt).where(CustomerDebt.source_key == key))
        paid = paid_amount(db, debt.id) if debt else ZERO
        if debt and paid > ZERO and customer.id != debt.customer_id:
            raise RuleError('لا يمكن نقل دين له تسديدات إلى عميل مختلف.', 409)
        if paid > entry.amount:
            raise RuleError('قيمة الدين الجديدة أقل من التسديدات المعتمدة عليه.', 409)
        if not debt:
            debt = CustomerDebt(source_key=key, shift_id=shift.id, created_by=shift.employee_id)
            db.add(debt)
        debt.customer_id, debt.invoice_number = customer.id, entry.invoice_number
        debt.description, debt.debt_date, debt.amount, debt.active = entry.description, version.business_date, entry.amount, True
    db.flush()
    for entry in entries:
        if entry.kind != 'bank' or entry.purpose != 'customer_account':
            continue
        review = db.scalar(select(InvoiceReview).where(InvoiceReview.entry_id == entry.id))
        debt = get_or_404(db, CustomerDebt, review.debt_id)
        if not debt.active or debt.shift_id == shift.id or debt.debt_date > version.business_date:
            raise RuleError('ربط الحوالة بالدين السابق لم يعد صالحًا. أعد مطابقة العملية.', 409)
        if db.get(Customer, debt.customer_id).name_key != digest(reference_key(entry.name)):
            raise RuleError('اسم المسدد لا يطابق صاحب الدين المحدد.')
        if entry.amount > debt.amount - paid_amount(db, debt.id):
            raise RuleError('التسديد يتجاوز الرصيد المتبقي؛ قد اعتمدت وردية أخرى تسديدًا في الوقت نفسه.', 409)
        payment = db.scalar(select(DebtPayment).where(DebtPayment.source_key == entry.line_key))
        if not payment:
            payment = DebtPayment(source_key=entry.line_key, shift_id=shift.id, created_by=shift.employee_id)
            db.add(payment)
        payment.debt_id, payment.amount, payment.active = debt.id, entry.amount, True
        payment.payment_date, payment.method = version.business_date, 'bank'
        db.flush()
    after = {'debts': [row(d) for d in db.scalars(select(CustomerDebt).where(CustomerDebt.shift_id == shift.id))],
             'payments': [row(p) for p in db.scalars(select(DebtPayment).where(DebtPayment.shift_id == shift.id))]}
    audit(db, actor, 'ledger.replaced', shift, {'before': before, 'after': after, 'version': version.number})


def opening_context(db, shift):
    store = db.get(Store, 1)
    if shift.approved_version:
        approved = version_for(db, shift, shift.approved_version)
        return approved.opening_cash, shift.previous_shift_id
    approved_shifts = list(db.scalars(select(Shift).where(Shift.approved_version.is_not(None))))
    # A pending correction can change the displayed report date. Cash carry-forward
    # must still follow the ACTIVE APPROVED snapshot's date, not that draft projection.
    approved_order={s.id:(version_for(db,s,s.approved_version).business_date,s.id) for s in approved_shifts}
    approved_shifts.sort(key=lambda s:approved_order[s.id])
    target_order = (shift.business_date, shift.id)
    if any(approved_order[s.id] > target_order for s in approved_shifts):
        raise RuleError('لا يمكن اعتماد وردية جديدة بتاريخ يسبق وردية معتمدة. راجع التاريخ والترتيب.', 409)
    earlier = db.scalar(select(Shift.id).where(Shift.approved_version.is_(None), Shift.id != shift.id,
                        ((Shift.business_date < shift.business_date) |
                         ((Shift.business_date == shift.business_date) & (Shift.id < shift.id)))).limit(1))
    if earlier:
        raise RuleError('أكمل مطابقة الورديات الأقدم أولًا لترحيل الرصيد الفعلي بالترتيب.', 409)
    previous = approved_shifts[-1] if approved_shifts else None
    return (version_for(db, previous, previous.approved_version).retained_cash, previous.id) if previous else (store.initial_opening_cash, None)


def preview(db, shift, data):
    check_version(shift, data.expected_version)
    opening, previous_id = opening_context(db, shift)
    version = version_for(db, shift)
    totals = calculate(version_values(version), [entry_values(e) for e in entries_for(db, version)],
                       opening, data.pos_sales, data.retained_cash)
    pending = db.scalar(select(func.count()).select_from(InvoiceReview).join(Entry, Entry.id == InvoiceReview.entry_id)
                       .where(Entry.version_id == version.id, InvoiceReview.status == 'pending'))
    return {**totals, 'pending_invoices': pending, 'previous_shift_id': previous_id}


def approve(db, actor, identifier, data, config):
    shift = get_or_404(db, Shift, identifier)
    if shift.approved_version == shift.current_version:
        raise RuleError('هذه الوردية معتمدة بالفعل. استخدم التصحيح الموثق عند الحاجة.', 409)
    totals = preview(db, shift, data)
    if totals['pending_invoices']:
        raise RuleError('طابق جميع الفواتير والعمليات المعلقة قبل اعتماد الوردية.', 409)
    if totals['difference'] != ZERO and len(data.note.strip()) < 3:
        raise RuleError('أدخل ملاحظة تشرح سبب العجز أو الفائض قبل الاعتماد.')
    if shift.approved_version:
        previous_approved = version_for(db, shift, shift.approved_version)
        dependent = db.scalar(select(Shift.id).where(Shift.previous_shift_id == shift.id).limit(1))
        if dependent and (previous_approved.retained_cash != data.retained_cash or previous_approved.business_date != shift.business_date):
            raise RuleError('توجد وردية لاحقة تعتمد على رصيد هذه الوردية. لا يمكن تغيير الرصيد المرحل أو تاريخ الصندوق في هذا الإصدار.', 409)
        if shift.previous_shift_id:
            predecessor=get_or_404(db,Shift,shift.previous_shift_id)
            predecessor_date=version_for(db,predecessor,predecessor.approved_version).business_date
            if (shift.business_date,shift.id) <= (predecessor_date,predecessor.id):
                raise RuleError('لا يمكن نقل تاريخ الصندوق إلى ما قبل الوردية التي رحّلت عهدته.',409)
    version = version_for(db, shift)
    counts = (totals['opening_cash'], data.pos_sales, data.retained_cash)
    if (version.opening_cash, version.pos_sales, version.retained_cash) != counts:
        values = {**version_values(version), 'entries': [entry_values(e) for e in entries_for(db, version)]}
        reviews = {e.line_key: db.scalar(select(InvoiceReview).where(InvoiceReview.entry_id == e.id)) for e in entries_for(db, version)}
        shift.current_version += 1
        version = persist_version(db, actor, shift, values, 'اعتماد المطابقة: ' + (data.note or 'الصندوق مطابق'), counts, reviews)
    replace_ledger(db, actor, shift, version)
    db.add(Approval(shift_id=shift.id, version_id=version.id, totals_json=json_text(totals),
                    approved_by=actor.id, note=data.note))
    shift.approved_version = version.number
    shift.previous_shift_id = totals['previous_shift_id']
    db.flush()
    audit(db, actor, 'shift.reconciled', shift, {'version': version.number, 'totals': totals, 'note': data.note})
    from .notifications import enqueue
    if totals['shortage'] > ZERO:
        employee = db.get(User, shift.employee_id)
        enqueue(db, config, f'shift:{shift.id}:v{version.number}:shortage', 'cash_shortage',
                dict(shift_id=shift.id, version=version.number, business_date=version.business_date,
                     employee_id=employee.id, employee=employee.full_name, shortage=totals['shortage'],
                     expected_cash=totals['expected_cash'], actual_cash=totals['actual_cash'], note=data.note), shift.id)
    return {'id': shift.id, 'version': version.number, 'totals': totals}



def confirm_shift(db, actor, identifier, data):
    """Administrative verification, deliberately NOT a cash reconciliation.

    No POS/counted-cash input, no shortage/surplus claims, and no new debt
    ledger writes. Preserve immutable historical approvals and their amounts.
    """
    shift = get_or_404(db, Shift, identifier)
    check_version(shift, data.expected_version)
    if shift.approved_version == shift.current_version:
        raise RuleError('هذه الوردية معتمدة بالفعل.', 409)
    version = version_for(db, shift)
    current_entries = entries_for(db, version)
    if any(e.kind == 'debt' or (e.kind == 'bank' and e.purpose == 'customer_account') for e in current_entries):
        raise RuleError('هذه الوردية القديمة تحتوي ديونًا أو تسديدات حسابات. يجب مراجعتها محاسبيًا وفق الإصدار السابق؛ الاعتماد المبسط متاح للورديات الجديدة فقط.', 409)
    if (db.scalar(select(CustomerDebt.id).where(CustomerDebt.shift_id == shift.id).limit(1))
        or db.scalar(select(DebtPayment.id).where(DebtPayment.shift_id == shift.id).limit(1))):
        raise RuleError('هناك قيود ديون تاريخية مرتبطة بهذه الوردية. لا يمكن تجاوزها بالاعتماد الإداري.', 409)
    if shift.approved_version and version_for(db, shift, shift.approved_version).retained_cash is not None:
        raise RuleError('لدى هذه الوردية اعتماد نقدي قديم؛ لا يمكن استبداله باعتماد إداري دون مراجعة محاسبية.', 409)
    totals = calculate(version_values(version), [entry_values(e) for e in current_entries])
    totals.update(status='confirmed', message='اعتمد المدير بيانات الوردية دون حساب عجز أو فائض',
                  confirmation_mode='administrative', financial_variance_calculated=False)
    db.add(Approval(shift_id=shift.id, version_id=version.id, totals_json=json_text(totals),
                    approved_by=actor.id, note=data.note))
    shift.approved_version = version.number
    # Never establish a cash carry-forward link without a physical count.
    shift.previous_shift_id = None
    db.flush()
    audit(db, actor, 'shift.confirmed', shift, {'version': version.number,
          'mode': 'administrative', 'cash_reconciliation': False, 'note': data.note})
    return {'id': shift.id, 'version': version.number, 'approved': True,
            'confirmation_mode': 'administrative'}

def shift_summary(db, shift):
    version = version_for(db, shift)
    approved = shift.approved_version == shift.current_version
    totals = public_totals(totals_for(db, version), approved)
    pending = 0  # Invoice matching module retired; old reviews are historical only.
    current_entries = entries_for(db, version)
    legacy_accounting = (any(e.kind == 'debt' or (e.kind == 'bank' and e.purpose == 'customer_account')
                             for e in current_entries)
                         or db.scalar(select(CustomerDebt.id).where(CustomerDebt.shift_id == shift.id).limit(1)) is not None
                         or db.scalar(select(DebtPayment.id).where(DebtPayment.shift_id == shift.id).limit(1)) is not None
                         or (shift.approved_version is not None and
                             version_for(db, shift, shift.approved_version).retained_cash is not None))
    return {**row(shift), 'employee': db.get(User, shift.employee_id).full_name,
            'deposit_date': version.deposit_date, 'deposit_number': version.deposit_number,
            'totals': totals, 'pending_invoices': pending, 'approved': approved,
            'legacy_accounting': bool(legacy_accounting)}


def shift_detail(db, identifier, version_number=None):
    shift = get_or_404(db, Shift, identifier)
    version = version_for(db, shift, version_number)
    entries = []
    for entry in entries_for(db, version):
        review = db.scalar(select(InvoiceReview).where(InvoiceReview.entry_id == entry.id))
        item = {**row(entry), 'review': row(review) if review else None}
        if entry.attachment_id:
            file = db.get(Attachment, entry.attachment_id)
            item['attachment'] = row(file, exclude=('content',))
        entries.append(item)
    approval = db.scalar(select(Approval).where(Approval.version_id == version.id))
    return {'shift': row(shift), 'employee': db.get(User, shift.employee_id).full_name,
            'version': row(version, exclude=('opening_cash','pos_sales','retained_cash')),
            'entries': entries, 'totals': public_totals(totals_for(db, version), approval is not None),
            'approved': approval is not None, 'approval': row(approval, exclude=('totals_json',)) if approval else None,
            'versions': [row(v, exclude=('opening_cash','pos_sales','retained_cash')) for v in db.scalars(select(ShiftVersion).where(ShiftVersion.shift_id == shift.id).order_by(ShiftVersion.number.desc()))],
            'has_legacy_cash': any(v.retained_cash is not None for v in db.scalars(select(ShiftVersion).where(ShiftVersion.shift_id == shift.id)))}


def invoice_list(db, month=None, status='pending', kind=None):
    query = select(Entry, Shift, ShiftVersion, InvoiceReview, User).join(
        ShiftVersion, Entry.version_id == ShiftVersion.id).join(Shift, Shift.id == ShiftVersion.shift_id).join(
        InvoiceReview, InvoiceReview.entry_id == Entry.id).join(User, User.id == Shift.employee_id).where(
        ShiftVersion.number == Shift.current_version)
    if month:
        query = query.where(ShiftVersion.business_date >= month[0], ShiftVersion.business_date < month[1])
    if status != 'all':
        query = query.where(InvoiceReview.status == status)
    if kind:
        query = query.where(Entry.kind == kind)
    return [{**row(entry), 'shift_id': shift.id, 'version_number': version.number,
             'business_date': version.business_date, 'employee': user.full_name,
             'review': row(review)} for entry, shift, version, review, user in db.execute(query.order_by(Shift.business_date, Entry.id))]


def customer_statement(db, identifier):
    customer = get_or_404(db, Customer, identifier)
    debts = []
    for debt in db.scalars(select(CustomerDebt).where(CustomerDebt.customer_id == customer.id).order_by(CustomerDebt.debt_date, CustomerDebt.id)):
        paid = paid_amount(db, debt.id)
        debts.append({**row(debt), 'paid': paid, 'remaining': debt.amount-paid if debt.active else ZERO,
                      'status': 'cancelled' if not debt.active else 'paid' if paid == debt.amount else 'partial' if paid else 'unpaid',
                      'payments': [row(p) for p in db.scalars(select(DebtPayment).where(DebtPayment.debt_id == debt.id).order_by(DebtPayment.payment_date))]})
    return {'customer': row(customer), 'debts': debts, 'remaining': sum((d['remaining'] for d in debts), ZERO)}


def report_data(db, start=None, end=None, employee_id=None):
    query = select(Shift).order_by(Shift.business_date.desc(), Shift.id.desc())
    if start:
        query = query.where(Shift.business_date >= start)
    if end:
        query = query.where(Shift.business_date < end)
    if employee_id:
        query = query.where(Shift.employee_id == employee_id)
    rows = [shift_summary(db, s) for s in db.scalars(query)]
    def total(field):
        return sum((r['totals'][field] or ZERO for r in rows), ZERO)
    totals = {name: total(name) for name in ('total_sales', 'device_sales', 'outside_sales', 'purchases',
                                            'shift_bank', 'total_bank', 'deposit_amount')}
    totals.update(count=len(rows), approved=sum(r['approved'] for r in rows),
                  pending=sum(not r['approved'] for r in rows))
    daily = []
    for day in sorted({r['business_date'] for r in rows}):
        items = [r for r in rows if r['business_date'] == day]
        daily.append(dict(day=day, sales=sum((r['totals']['total_sales'] for r in items), ZERO),
                          count=len(items), pending=sum(not r['approved'] for r in items)))
    staff = []
    for eid in sorted({r['employee_id'] for r in rows}):
        items = [r for r in rows if r['employee_id'] == eid]
        staff.append(dict(id=eid, name=items[0]['employee'], count=len(items),
                          sales=sum((r['totals']['total_sales'] for r in items), ZERO),
                          pending=sum(not r['approved'] for r in items)))
    return {'totals': totals, 'daily': daily, 'employees': staff, 'shifts': rows,
            'store': row(db.get(Store, 1)), 'generated_at': utcnow(),
            'start': start, 'end_exclusive': end}


def analytics_data(db, month, months=6, employee_id=None):
    """Exact sales and historical counted-cash variances, never invented counts."""
    import re
    if not re.fullmatch(r'[0-9]{4}-(?:0[1-9]|1[0-2])', month or ''):
        raise RuleError('حدد شهرًا صحيحًا بصيغة سنة-شهر.')
    year, number = map(int, month.split('-'))
    if year < 1 or (year == 9999 and number == 12):
        raise RuleError('الشهر خارج نطاق التقارير المدعوم.')
    if not 1 <= months <= 24:
        raise RuleError('عدد شهور التحليل يجب أن يكون بين 1 و24.')
    last = (year - 1) * 12 + number - 1
    indices = list(range(max(0, last - months + 1), last + 1))

    def month_date(index):
        return date(index // 12 + 1, index % 12 + 1, 1)

    begin, end = month_date(indices[0]), month_date(last + 1)
    groups = {f'{month_date(i).year:04d}-{month_date(i).month:02d}':
              {'month': f'{month_date(i).year:04d}-{month_date(i).month:02d}',
               'total_sales': ZERO, 'shortage': ZERO, 'surplus': ZERO,
               'net_difference': ZERO, 'cash_count_sessions': 0} for i in indices}
    for item in report_data(db, begin, end, employee_id)['shifts']:
        groups[item['business_date'][:7]]['total_sales'] += item['totals']['total_sales']
    query = select(Approval, ShiftVersion).join(ShiftVersion, Approval.version_id == ShiftVersion.id).join(
        Shift, Shift.id == ShiftVersion.shift_id).where(
        Shift.approved_version == ShiftVersion.number,
        ShiftVersion.business_date >= begin, ShiftVersion.business_date < end)
    if employee_id is not None:
        query = query.where(Shift.employee_id == employee_id)
    for approval, version in db.execute(query):
        snapshot = json.loads(approval.totals_json)
        if snapshot.get('confirmation_mode') == 'administrative' or version.retained_cash is None:
            continue
        raw = snapshot.get('difference')
        if raw is None:
            continue
        try:
            difference = Decimal(str(raw))
            if not difference.is_finite() or difference.as_tuple().exponent < -2:
                raise ValueError('invalid snapshot')
        except Exception:
            raise RuleError('لقطة مطابقة نقدية قديمة غير صالحة؛ راجع السجل المحاسبي.') from None
        values = groups[f'{version.business_date.year:04d}-{version.business_date.month:02d}']
        values['cash_count_sessions'] += 1
        values['shortage'] += max(-difference, ZERO)
        values['surplus'] += max(difference, ZERO)
        values['net_difference'] += difference
    for values in groups.values():
        if not values['cash_count_sessions']:
            values.update(shortage=None, surplus=None, net_difference=None)
    return {'months': list(groups.values()), 'employee_id': employee_id,
            'variance_source': 'approved_historical_cash_snapshots',
            'new_shifts_have_counted_cash': False, 'generated_at': utcnow()}
