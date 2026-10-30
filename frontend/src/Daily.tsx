import { useState } from "react";
import {
  Banknote,
  CheckCircle2,
  CreditCard,
  HandCoins,
  LockKeyhole,
  Plus,
  RotateCcw,
  Save,
  Wallet,
} from "lucide-react";
import {
  cents,
  decimal,
  kindLabel,
  methodLabel,
  money,
  useLoad,
  useMutation,
  when,
} from "./api";
import { useApp } from "./context";
import {
  AmountInput,
  Badge,
  Empty,
  ErrorBox,
  Field,
  Form,
  Loading,
  Metric,
  PrintExport,
} from "./components";
import { CloseDialog, EntryDialog, ReasonDialog } from "./dialogs";
import type { EntryType } from "./dialogs";
import type { Current, DailySession, Financial } from "./types";

export default function Daily({ selectedId }: { selectedId: number | null }) {
  const { me, revision, refresh, notify } = useApp(),
    current = useLoad<Current>("/sessions/current", revision);
  const selected = useLoad<DailySession>(
    selectedId ? "/sessions/" + selectedId : null,
    revision,
  );
  const [day, setDay] = useState(me.today),
    [opening, setOpening] = useState(""),
    [notes, setNotes] = useState(""),
    m = useMutation();
  const session = selectedId ? selected.data : current.data?.session;
  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow">من أول رصيد حتى آخر جرد</div>
          <h1>الإدخال اليومي</h1>
          <p>سجّل المبيعات والحركات، ثم طابق النقد الفعلي عند الإغلاق.</p>
        </div>
        <PrintExport />
      </div>
      <ErrorBox message={current.error || selected.error} />
      {current.loading || (selectedId && selected.loading) ? (
        <Loading />
      ) : session ? (
        <Workspace
          key={session.id + "-" + session.version + "-" + session.actual_cash}
          session={session}
        />
      ) : (
        !selectedId &&
        current.data && (
          <div className="open-layout">
            <section className="panel open-panel">
              <div className="soft-icon">
                <Wallet size={26} />
              </div>
              <h2>افتح يوم عمل جديدًا</h2>
              <p>جلسة واحدة لكل يوم عمل وصندوق واحد لمتجرك.</p>
              <Form
                onSubmit={() =>
                  m.run(
                    "/sessions",
                    "POST",
                    {
                      business_date: day,
                      opening_cash:
                        current.data?.next_opening_cash ??
                        (opening === "" ? null : opening),
                      notes,
                    },
                    () => {
                      notify("تم فتح جلسة يوم العمل");
                      refresh();
                    },
                  )
                }
              >
                <div className="form-grid">
                  <Field label="تاريخ العمل">
                    <input
                      type="date"
                      value={day}
                      onChange={(e) => setDay(e.target.value)}
                      required
                    />
                  </Field>
                  <Field label="المستخدم المسؤول">
                    <input readOnly value={me.user.full_name} />
                  </Field>
                  <div className="full">
                    <Field
                      label="رصيد افتتاح الصندوق"
                      hint={
                        current.data.next_opening_cash !== null
                          ? "مُرحّل من النقد الفعلي المعتمد للجلسة السابقة"
                          : "أدخل النقد الموجود فعلًا عند بدء استخدام النظام"
                      }
                    >
                      <AmountInput
                        value={current.data.next_opening_cash ?? opening}
                        onChange={setOpening}
                        readOnly={current.data.next_opening_cash !== null}
                        required
                      />
                    </Field>
                  </div>
                  <div className="full">
                    <Field label="ملاحظات">
                      <textarea
                        rows={3}
                        value={notes}
                        onChange={(e) => setNotes(e.target.value)}
                        maxLength={2000}
                      />
                    </Field>
                  </div>
                </div>
                <ErrorBox message={m.error} />
                <button className="primary" disabled={m.busy}>
                  <Plus size={18} /> {m.busy ? "جارٍ الفتح…" : "فتح يوم العمل"}
                </button>
              </Form>
            </section>
            <aside className="panel guidelines">
              <h2>خطوات يومك</h2>
              <ol>
                <li>
                  <b>افتتاح الصندوق</b>
                  <p>يُرحّل النقد الفعلي من آخر إغلاق معتمد تلقائيًا.</p>
                </li>
                <li>
                  <b>تسجيل المبيعات والحركات</b>
                  <p>
                    أدخل إجمالي المبيعات والشبكة، وأضف الآجل والتحصيل والمشتريات
                    بالتفصيل.
                  </p>
                </li>
                <li>
                  <b>الجرد والمطابقة</b>
                  <p>عدّ النقد الفعلي، ثم راجع الفرق واعتمد الإغلاق.</p>
                </li>
              </ol>
              <div className="info-box">
                إجمالي المبيعات يشمل مبيعات الشبكة والآجل، ويُسجّل قبل
                المرتجعات.
              </div>
            </aside>
          </div>
        )
      )}
    </>
  );
}

function Workspace({ session: s }: { session: DailySession }) {
  const { me, refresh, notify } = useApp(),
    [total, setTotal] = useState(s.total_sales),
    [pos, setPos] = useState(s.pos_sales),
    [notes, setNotes] = useState(s.notes),
    [actual, setActual] = useState(
      s.totals.count_stale ? "" : (s.actual_cash ?? ""),
    );
  const [entry, setEntry] = useState<EntryType | null>(null),
    [close, setClose] = useState(false),
    [reason, setReason] = useState<{ title: string; path: string } | null>(
      null,
    );
  const saleMutation = useMutation(),
    countMutation = useMutation(),
    open = s.status === "open",
    t = s.totals;
  const a = cents(total),
    b = cents(pos),
    c = cents(t.new_credit_sales),
    preview =
      a !== null && b !== null && c !== null ? decimal(a - b - c) : null;
  const cancel = (category: string, id: number) =>
    setReason({
      title: "إلغاء السجل مع حفظ أثره",
      path: `/records/${category}/${id}/cancel`,
    });
  function recordTable(
    items: (Financial & { label: string; details: string })[],
    category: string,
  ) {
    return items.length ? (
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>الوصف</th>
              <th>المبلغ</th>
              <th>الحالة</th>
              {me.user.role === "admin" && open && <th>إجراء</th>}
            </tr>
          </thead>
          <tbody>
            {items.map((x) => (
              <tr key={x.id} className={x.cancelled_at ? "cancelled" : ""}>
                <td>
                  <strong>{x.label}</strong>
                  <small className="block">{x.details}</small>
                </td>
                <td className="number">{money(x.amount)}</td>
                <td>
                  <Badge status={x.cancelled_at ? "cancelled" : "valid"} />
                </td>
                {me.user.role === "admin" && open && (
                  <td>
                    {!x.cancelled_at && (
                      <button
                        className="text-button danger-text"
                        onClick={() => cancel(category, x.id)}
                      >
                        إلغاء موثّق
                      </button>
                    )}
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    ) : (
      <Empty text="لم تُسجّل حركات من هذا النوع" />
    );
  }
  return (
    <>
      <div className="session-banner">
        <div className="session-heading">
          <div className="soft-icon">
            <Wallet size={22} />
          </div>
          <div>
            <h2>جلسة {when(s.business_date)}</h2>
            <p>
              المسؤول: {s.responsible_name} · رقم الجلسة #{s.id}
            </p>
          </div>
          <Badge status={s.status} />
        </div>
        <div className="inline-actions no-print">
          {open ? (
            <button className="primary" onClick={() => setClose(true)}>
              <LockKeyhole size={16} /> مراجعة وإغلاق اليوم
            </button>
          ) : (
            me.user.role === "admin" && (
              <button
                className="secondary"
                onClick={() =>
                  setReason({
                    title: "إعادة فتح الجلسة",
                    path: `/sessions/${s.id}/reopen`,
                  })
                }
              >
                <RotateCcw size={16} /> إعادة فتح موثّقة
              </button>
            )
          )}
        </div>
      </div>
      {!open && (
        <div className="alert success">
          <CheckCircle2 size={18} /> الجلسة معتمدة ومغلقة منذ{" "}
          {when(s.closed_at, me.settings.timezone)}. تعرض المجاميع تفاصيل
          إغلاقها.
        </div>
      )}
      <div className="metrics four">
        <Metric
          label="رصيد الافتتاح"
          value={s.opening_cash}
          icon={<Wallet size={18} />}
          note={"رصيد عند بداية " + when(s.business_date)}
        />
        <Metric
          label="المبيعات النقدية"
          value={t.cash_sales}
          icon={<Banknote size={18} />}
          tone="featured"
          note="محسوبة من إجمالي المبيعات والشبكة والآجل"
        />
        <Metric
          label="المبيعات الآجلة"
          value={t.new_credit_sales}
          icon={<HandCoins size={18} />}
          note="من تفاصيل ديون اليوم"
        />
        <Metric
          label="مبيعات الشبكة"
          value={s.pos_sales}
          icon={<CreditCard size={18} />}
          note="لا تزيد النقد الفعلي"
        />
      </div>
      <div className="daily-layout">
        <div className="daily-main">
          <section className="panel">
            <div className="panel-head">
              <div>
                <h2>ملخص المبيعات اليومية</h2>
                <p>إجمالي المبيعات = نقدي + شبكة + آجل. المرتجعات منفصلة.</p>
              </div>
            </div>
            <Form
              onSubmit={() =>
                saleMutation.run(
                  `/sessions/${s.id}/sales`,
                  "PUT",
                  {
                    total_sales: total,
                    pos_sales: pos,
                    notes,
                    expected_version: s.version,
                  },
                  () => {
                    notify("تم حفظ المبيعات وإعادة حساب الصندوق");
                    refresh();
                  },
                )
              }
            >
              <fieldset disabled={!open}>
                <div className="form-grid">
                  <Field label="إجمالي المبيعات قبل المرتجعات">
                    <AmountInput value={total} onChange={setTotal} required />
                  </Field>
                  <Field
                    label="مبيعات الشبكة / البطاقات"
                    hint="جزء من الإجمالي ولا تُضاف إليه مجددًا"
                  >
                    <AmountInput value={pos} onChange={setPos} required />
                  </Field>
                  <Field
                    label="المبيعات الآجلة الجديدة"
                    hint="تأتي من سجلات الديون التفصيلية"
                  >
                    <AmountInput value={t.new_credit_sales} readOnly />
                  </Field>
                  <Field
                    label="معاينة المبيعات النقدية"
                    hint="معاينة دقيقة؛ يتحقق الخادم عند الحفظ"
                  >
                    <input
                      dir="ltr"
                      readOnly
                      value={preview ?? "تحقق من المبالغ"}
                    />
                  </Field>
                  <div className="full">
                    <Field label="ملاحظات يوم العمل">
                      <textarea
                        rows={3}
                        value={notes}
                        onChange={(e) => setNotes(e.target.value)}
                        maxLength={2000}
                      />
                    </Field>
                  </div>
                </div>
                <ErrorBox message={saleMutation.error} />
                {preview?.startsWith("-") && (
                  <div className="alert danger">
                    إجمالي المبيعات أقل من الشبكة والآجل. صحّح المبالغ قبل
                    الحفظ.
                  </div>
                )}
                {open && (
                  <div className="form-actions">
                    <button className="primary" disabled={saleMutation.busy}>
                      <Save size={16} />{" "}
                      {saleMutation.busy ? "جارٍ الحفظ…" : "حفظ ملخص المبيعات"}
                    </button>
                  </div>
                )}
              </fieldset>
            </Form>
          </section>
          <section className="panel">
            <div className="panel-head">
              <div>
                <h2>مبيعات اليوم الآجلة</h2>
                <p>تزيد مبيعات الآجل ولا تمثل نقدًا مستلمًا</p>
              </div>
              {open && (
                <button className="secondary" onClick={() => setEntry("debt")}>
                  <Plus size={15} /> بيع آجل
                </button>
              )}
            </div>
            {recordTable(
              s.debts.map((d) => ({
                ...d,
                label: d.customer_name || "عميل",
                details: `المتبقي ${money(d.remaining)} · ${d.due_date ? "الاستحقاق " + d.due_date : "دون تاريخ استحقاق"}`,
              })),
              "debts",
            )}
          </section>
          <section className="panel">
            <div className="panel-head">
              <div>
                <h2>تحصيل ديون العملاء</h2>
                <p>
                  التحصيل النقدي يزيد هذه الجلسة؛ الشبكة والتحويل يخفضان الدين
                  فقط
                </p>
              </div>
              {open && (
                <button
                  className="secondary"
                  onClick={() => setEntry("payment")}
                >
                  <Plus size={15} /> تحصيل
                </button>
              )}
            </div>
            {recordTable(
              s.payments.map((p) => ({
                ...p,
                label: p.customer_name || "عميل",
                details: `${methodLabel[p.payment_method]} · الدين #${p.debt_id}`,
              })),
              "payments",
            )}
          </section>
          <section className="panel">
            <div className="panel-head">
              <div>
                <h2>المشتريات</h2>
                <p>يُخصم فقط ما دُفع نقدًا من الصندوق</p>
              </div>
              {open && (
                <button
                  className="secondary"
                  onClick={() => setEntry("purchase")}
                >
                  <Plus size={15} /> مشتريات
                </button>
              )}
            </div>
            {recordTable(
              s.purchases.map((p) => ({
                ...p,
                label: p.description,
                details: `${methodLabel[p.payment_method]} · ${p.from_drawer ? "من الصندوق" : "خارج الصندوق"}${p.invoice_number ? " · فاتورة " + p.invoice_number : ""}`,
              })),
              "purchases",
            )}
          </section>
          <section className="panel">
            <div className="panel-head">
              <div>
                <h2>حركات نقدية أخرى</h2>
                <p>كل حركة تؤثر مرة واحدة فقط</p>
              </div>
            </div>
            {open && (
              <div className="quick-actions no-print">
                {(["expense", "deposit", "withdrawal", "refund"] as const).map(
                  (k) => (
                    <button
                      className="secondary"
                      key={k}
                      onClick={() => setEntry(k)}
                    >
                      <Plus size={15} />
                      {kindLabel[k]}
                    </button>
                  ),
                )}
              </div>
            )}
            {recordTable(
              s.movements
                .filter((m) => !m.purchase_id && !m.debt_payment_id)
                .map((m) => ({
                  ...m,
                  label: m.description,
                  details: kindLabel[m.kind],
                })),
              "movements",
            )}
          </section>
        </div>
        <aside className="daily-aside">
          <section className="panel cash-equation">
            <div className="panel-head">
              <div>
                <h2>حساب رصيد الصندوق</h2>
                <p>من السجلات الصحيحة غير الملغاة</p>
              </div>
            </div>
            {[
              ["رصيد الافتتاح", t.opening_cash, ""],
              ["المبيعات النقدية", t.cash_sales, "+"],
              ["تحصيل الديون نقدًا", t.cash_collections, "+"],
              ["الإيداعات النقدية", t.deposits, "+"],
              ["مشتريات من الصندوق", t.cash_purchases, "−"],
              ["المصروفات النقدية", t.cash_expenses, "−"],
              ["السحوبات النقدية", t.withdrawals, "−"],
              ["المرتجعات النقدية", t.cash_refunds, "−"],
            ].map(([l, v, sign]) => (
              <div className="equation-row" key={l}>
                <span>
                  {sign && (
                    <i className={sign === "+" ? "plus" : "minus"}>{sign}</i>
                  )}
                  {l}
                </span>
                <b dir="ltr">{money(v)}</b>
              </div>
            ))}
            <div className="equation-total">
              <span>النقد المتوقع</span>
              <b dir="ltr">{money(t.expected_cash)}</b>
              <small>{me.settings.currency}</small>
            </div>
            <div className="info-box">
              الشبكة والبيع الآجل لا يدخلان الدرج. الربح والخسارة لا يُحسبان من
              فرق الجرد.
            </div>
          </section>
          <section className="panel count-panel">
            <h2>الجرد الفعلي</h2>
            <p className="muted">
              آخر جرد: {when(t.counted_at, me.settings.timezone)}
            </p>
            {t.count_stale && (
              <div className="alert warning">
                سُجّلت حركات بعد آخر جرد. أعد العد قبل الإغلاق.
              </div>
            )}
            <Badge status={t.reconciliation_status} />
            <p>{t.reconciliation_message}</p>
            {open ? (
              <Form
                onSubmit={() =>
                  countMutation.run(
                    `/sessions/${s.id}/count`,
                    "PUT",
                    {
                      actual_cash: actual === "" ? null : actual,
                      expected_version: s.version,
                    },
                    () => {
                      notify("تم حفظ الجرد");
                      refresh();
                    },
                  )
                }
              >
                <Field
                  label="النقد الفعلي المعدود"
                  hint="الحقل الفارغ يعني بانتظار الجرد؛ الصفر مبلغ فعلي"
                >
                  <AmountInput value={actual} onChange={setActual} />
                </Field>
                <ErrorBox message={countMutation.error} />
                <button
                  className="secondary stretch"
                  disabled={countMutation.busy}
                >
                  <Save size={15} /> حفظ الجرد دون إغلاق
                </button>
              </Form>
            ) : (
              <div className="drawer-amount">
                <b dir="ltr">{money(s.actual_cash)}</b>
                <small>{me.settings.currency}</small>
              </div>
            )}
          </section>
          {!!s.snapshots.length && (
            <section className="panel">
              <h2>اعتمادات الإغلاق</h2>
              {s.snapshots.map((x) => (
                <div className="snapshot" key={x.id}>
                  <small>{when(x.approved_at, me.settings.timezone)}</small>
                  <b>{x.totals.reconciliation_message}</b>
                  <p>{x.note || "لا توجد ملاحظة"}</p>
                </div>
              ))}
            </section>
          )}
        </aside>
      </div>
      {entry && (
        <EntryDialog
          type={entry}
          session={s}
          onClose={() => setEntry(null)}
          onDone={refresh}
        />
      )}
      {close && (
        <CloseDialog
          session={s}
          onClose={() => setClose(false)}
          onDone={refresh}
        />
      )}
      {reason && (
        <ReasonDialog
          {...reason}
          onClose={() => setReason(null)}
          onDone={refresh}
        />
      )}
    </>
  );
}
