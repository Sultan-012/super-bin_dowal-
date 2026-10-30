import { useState } from "react";
import { api, methodLabel, money, useLoad, useMutation } from "./api";
import { useApp } from "./context";
import {
  AmountInput,
  Badge,
  ErrorBox,
  Field,
  Form,
  FormActions,
  Loading,
  Modal,
} from "./components";
import type { Customer, DailySession, Statement, Totals } from "./types";

export type EntryType =
  | "customer"
  | "debt"
  | "payment"
  | "purchase"
  | "expense"
  | "deposit"
  | "withdrawal"
  | "refund";
const titles: Record<EntryType, string> = {
  customer: "بيانات العميل",
  debt: "إضافة دين عميل",
  payment: "تحصيل دين",
  purchase: "تسجيل مشتريات",
  expense: "مصروف نقدي",
  deposit: "إيداع نقدي",
  withdrawal: "سحب نقدي",
  refund: "مرتجع نقدي",
};

export function EntryDialog({
  type,
  session,
  customer,
  onClose,
  onDone,
}: {
  type: EntryType;
  session: DailySession | null;
  customer?: Customer;
  onClose: () => void;
  onDone: () => void;
}) {
  const { me, notify } = useApp(),
    mutation = useMutation();
  const [name, setName] = useState(customer?.name || ""),
    [phone, setPhone] = useState(customer?.phone || ""),
    [notes, setNotes] = useState(
      type === "customer" ? customer?.notes || "" : "",
    );
  const [amount, setAmount] = useState(""),
    [description, setDescription] = useState(""),
    [supplier, setSupplier] = useState(""),
    [invoice, setInvoice] = useState("");
  const [method, setMethod] = useState("cash"),
    [drawer, setDrawer] = useState(true);
  const [date, setDate] = useState(session?.business_date || me.today),
    [due, setDue] = useState(""),
    [origin, setOrigin] = useState(session ? "credit" : "opening");
  const [query, setQuery] = useState(""),
    [cid, setCid] = useState(customer?.id ? String(customer.id) : ""),
    [did, setDid] = useState("");
  const needsCustomer = type === "debt" || type === "payment";
  const customers = useLoad<Customer[]>(
    needsCustomer && !customer
      ? "/customers?limit=200&q=" + encodeURIComponent(query)
      : null,
  );
  const statement = useLoad<Statement>(
    type === "payment" && cid ? `/customers/${cid}/statement` : null,
  );
  const close = () => {
    if (!mutation.busy) onClose();
  };
  function submit() {
    let path = "",
      verb = "POST",
      data: Record<string, unknown> = {};
    if (type === "customer") {
      path = "/customers" + (customer ? "/" + customer.id : "");
      verb = customer ? "PUT" : "POST";
      data = { name, phone: phone || null, notes };
    } else if (type === "debt") {
      path = "/debts";
      data = {
        customer_id: Number(cid),
        debt_date: date,
        amount,
        due_date: due || null,
        kind: origin,
        session_id: origin === "credit" ? session?.id : null,
        notes,
      };
    } else if (type === "payment") {
      path = "/payments";
      data = {
        debt_id: Number(did),
        session_id: session?.id,
        payment_date: date,
        amount,
        payment_method: method,
        notes,
      };
    } else if (type === "purchase") {
      path = "/purchases";
      data = {
        session_id: session?.id,
        purchase_date: date,
        description,
        supplier: supplier || null,
        amount,
        payment_method: method,
        from_drawer: method === "cash" && drawer,
        invoice_number: invoice || null,
        notes,
      };
    } else {
      path = "/movements";
      data = {
        session_id: session?.id,
        movement_date: date,
        kind: type,
        amount,
        description,
      };
    }
    mutation.run(path, verb, data, () => {
      notify("تم حفظ العملية بنجاح");
      onDone();
      onClose();
    });
  }
  return (
    <Modal
      title={titles[type]}
      subtitle={
        type === "customer"
          ? "حساب واضح لكل عميل"
          : `يسجلها ${me.user.full_name}${session ? " · جلسة " + session.business_date : ""}`
      }
      onClose={close}
    >
      <Form onSubmit={submit}>
        <div className="form-grid">
          {type === "customer" ? (
            <>
              <Field label="اسم العميل">
                <input
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                  maxLength={150}
                />
              </Field>
              <Field label="رقم الهاتف (اختياري)">
                <input
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  dir="ltr"
                  maxLength={40}
                />
              </Field>
            </>
          ) : (
            <>
              {needsCustomer && (
                <div className="full">
                  {customer ? (
                    <div className="info-box">
                      العميل: <b>{customer.name}</b>
                    </div>
                  ) : (
                    <>
                      <Field label="بحث عن عميل">
                        <input
                          placeholder="الاسم أو رقم الهاتف"
                          value={query}
                          onChange={(e) => setQuery(e.target.value)}
                        />
                      </Field>
                      <Field label="العميل">
                        <select
                          required
                          value={cid}
                          onChange={(e) => {
                            setCid(e.target.value);
                            setDid("");
                          }}
                        >
                          <option value="">اختر العميل</option>
                          {customers.data?.map((c) => (
                            <option key={c.id} value={c.id}>
                              {c.name} · {c.phone || "دون هاتف"}
                            </option>
                          ))}
                        </select>
                      </Field>
                      <ErrorBox message={customers.error} />
                    </>
                  )}
                </div>
              )}
              {type === "debt" && (
                <Field label="نوع الدين">
                  <select
                    value={origin}
                    onChange={(e) => setOrigin(e.target.value)}
                  >
                    <option value="credit" disabled={!session}>
                      بيع آجل من الجلسة الحالية
                    </option>
                    {me.user.role === "admin" && (
                      <option value="opening">
                        رصيد عميل افتتاحي سابق للنظام
                      </option>
                    )}
                  </select>
                </Field>
              )}
              {type === "payment" && (
                <div className="full">
                  {statement.loading ? (
                    <Loading />
                  ) : (
                    <Field label="الدين المطلوب سداده">
                      <select
                        required
                        value={did}
                        onChange={(e) => setDid(e.target.value)}
                      >
                        <option value="">اختر الدين</option>
                        {statement.data?.debts
                          .filter(
                            (d) => !d.cancelled_at && d.remaining !== "0.00",
                          )
                          .map((d) => (
                            <option key={d.id} value={d.id}>
                              #{d.id} · {d.debt_date} · المتبقي{" "}
                              {money(d.remaining)}
                            </option>
                          ))}
                      </select>
                    </Field>
                  )}
                  <ErrorBox message={statement.error} />
                </div>
              )}
              <Field
                label={type === "debt" ? "تاريخ الدين" : "تاريخ الحركة"}
                hint={
                  session && !(type === "debt" && origin === "opening")
                    ? "يجب أن يطابق تاريخ عمل الجلسة"
                    : undefined
                }
              >
                <input
                  type="date"
                  value={date}
                  onChange={(e) => setDate(e.target.value)}
                  required
                />
              </Field>
              <Field label="المبلغ">
                <AmountInput value={amount} onChange={setAmount} required />
              </Field>
              {type === "debt" && (
                <>
                  <Field label="تاريخ الاستحقاق (اختياري)">
                    <input
                      type="date"
                      value={due}
                      onChange={(e) => setDue(e.target.value)}
                      min={date}
                    />
                  </Field>
                  <div className="full info-box">
                    {origin === "opening"
                      ? "رصيد العميل الافتتاحي لا يضاف لمبيعات اليوم ولا يؤثر في الصندوق."
                      : "يُحتسب المبلغ تلقائيًا ضمن مبيعات اليوم الآجلة. أدخل إجمالي المبيعات أولًا بما يغطي هذه المبيعات."}
                  </div>
                </>
              )}
              {(type === "payment" || type === "purchase") && (
                <Field label="طريقة الدفع">
                  <select
                    value={method}
                    onChange={(e) => setMethod(e.target.value)}
                  >
                    {Object.entries(methodLabel).map(([v, l]) => (
                      <option key={v} value={v}>
                        {l}
                      </option>
                    ))}
                  </select>
                </Field>
              )}
              {type === "payment" && (
                <div className="full info-box">
                  {method === "cash"
                    ? "يخفض السداد دين العميل ويزيد نقد الجلسة الحالية مرة واحدة."
                    : "يخفض السداد دين العميل دون زيادة نقد الصندوق أو مبيعات الشبكة."}{" "}
                  التحصيل ليس بيعًا جديدًا.
                </div>
              )}
              {!needsCustomer && (
                <div className="full">
                  <Field label="وصف العملية">
                    <input
                      value={description}
                      onChange={(e) => setDescription(e.target.value)}
                      required
                      maxLength={250}
                    />
                  </Field>
                </div>
              )}
              {type === "purchase" && (
                <>
                  <Field label="المورّد (اختياري)">
                    <input
                      value={supplier}
                      onChange={(e) => setSupplier(e.target.value)}
                      maxLength={150}
                    />
                  </Field>
                  <Field label="رقم الفاتورة (اختياري)">
                    <input
                      value={invoice}
                      onChange={(e) => setInvoice(e.target.value)}
                      maxLength={80}
                    />
                  </Field>
                  {method === "cash" && (
                    <label className="check-field full">
                      <input
                        type="checkbox"
                        checked={drawer}
                        onChange={(e) => setDrawer(e.target.checked)}
                      />{" "}
                      دُفعت نقدًا من درج الصندوق
                    </label>
                  )}
                  <div className="full info-box">
                    {method === "cash" && drawer
                      ? "ستُخصم من الصندوق تلقائيًا. لا تسجل الفاتورة مرة أخرى كمصروف."
                      : "هذه المشتريات لا تخفض نقد الصندوق."}
                  </div>
                </>
              )}
            </>
          )}
          {["customer", "debt", "payment", "purchase"].includes(type) && (
            <div className="full">
              <Field label="ملاحظات (اختياري)">
                <textarea
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  rows={3}
                  maxLength={2000}
                />
              </Field>
            </div>
          )}
        </div>
        <ErrorBox message={mutation.error} />
        <FormActions busy={mutation.busy} onClose={close} />
      </Form>
    </Modal>
  );
}

export function ReasonDialog({
  title,
  path,
  onClose,
  onDone,
}: {
  title: string;
  path: string;
  onClose: () => void;
  onDone: () => void;
}) {
  const [reason, setReason] = useState(""),
    m = useMutation(),
    { notify } = useApp();
  const close = () => {
    if (!m.busy) onClose();
  };
  return (
    <Modal
      title={title}
      subtitle="صلاحية مدير · يُحفظ السبب والسجل الأصلي في سجل التدقيق"
      onClose={close}
    >
      <Form
        onSubmit={() =>
          m.run(path, "POST", { reason }, () => {
            notify("تم تنفيذ العملية وتوثيقها");
            onDone();
            onClose();
          })
        }
      >
        <Field label="سبب العملية">
          <textarea
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            required
            minLength={3}
            maxLength={1000}
            rows={4}
          />
        </Field>
        <ErrorBox message={m.error} />
        <FormActions busy={m.busy} onClose={close} label="تأكيد العملية" />
      </Form>
    </Modal>
  );
}

export function CloseDialog({
  session,
  onClose,
  onDone,
}: {
  session: DailySession;
  onClose: () => void;
  onDone: () => void;
}) {
  const { me, notify } = useApp(),
    m = useMutation();
  const [actual, setActual] = useState(
      session.totals.count_stale ? "" : session.actual_cash || "",
    ),
    [note, setNote] = useState("");
  const [preview, setPreview] = useState<Totals | null>(null),
    [loading, setLoading] = useState(false),
    [error, setError] = useState("");
  const close = () => {
    if (!m.busy && !loading) onClose();
  };
  async function calculate() {
    setError("");
    m.setError("");
    setLoading(true);
    try {
      setPreview(
        await api<Totals>(`/sessions/${session.id}/preview`, "POST", {
          actual_cash: actual === "" ? null : actual,
          expected_version: session.version,
        }),
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }
  return (
    <Modal
      title="مراجعة وإغلاق الجلسة"
      subtitle={session.business_date + " · " + session.responsible_name}
      onClose={close}
    >
      <Form
        onSubmit={() => {
          if (!preview) {
            void calculate();
            return;
          }
          m.run(
            `/sessions/${session.id}/close`,
            "POST",
            {
              actual_cash: actual === "" ? null : actual,
              expected_version: preview.version,
              note,
            },
            () => {
              notify("أُغلقت الجلسة وحُفظت لقطة الإغلاق المعتمدة");
              onDone();
              onClose();
            },
          );
        }}
      >
        <div className="info-box">
          عدّ النقد الموجود فعليًا في الدرج، ثم راجع الفرق قبل اعتماد الإغلاق.
        </div>
        <Field label="النقد الفعلي المعدود" hint={me.settings.currency}>
          <AmountInput
            value={actual}
            onChange={(v) => {
              setActual(v);
              setPreview(null);
            }}
            required
          />
        </Field>
        {preview && (
          <>
            <div className="reconcile-preview">
              <div>
                <span>الرصيد المتوقع</span>
                <b dir="ltr">{money(preview.expected_cash)}</b>
              </div>
              <div>
                <span>النقد الفعلي</span>
                <b dir="ltr">{money(actual)}</b>
              </div>
              <div>
                <span>الفرق</span>
                <b dir="ltr">{money(preview.difference)}</b>
              </div>
            </div>
            <div
              className={
                "alert " +
                (preview.reconciliation_status === "balanced"
                  ? "success"
                  : "warning")
              }
            >
              <Badge status={preview.reconciliation_status} />{" "}
              {preview.reconciliation_message}
            </div>
            <Field
              label={
                preview.difference !== "0.00"
                  ? "سبب العجز أو الفائض (مطلوب)"
                  : "ملاحظة الإغلاق (اختياري)"
              }
            >
              <textarea
                value={note}
                onChange={(e) => setNote(e.target.value)}
                rows={3}
                required={preview.difference !== "0.00"}
                maxLength={2000}
              />
            </Field>
            <p className="muted">
              العجز والفائض يصفان فرق الجرد، ولا يمثلان صافي الربح أو الخسارة.
              يتوقف تعديل الجلسة بعد الاعتماد.
            </p>
          </>
        )}
        <ErrorBox message={error || m.error} />
        <FormActions
          busy={m.busy || loading}
          onClose={close}
          label={preview ? "اعتماد وإغلاق الجلسة" : "حساب الفرق والمراجعة"}
        />
      </Form>
    </Modal>
  );
}
