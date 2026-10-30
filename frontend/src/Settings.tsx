import { useState } from "react";
import { Plus, Save, ShieldCheck } from "lucide-react";
import { useLoad, useMutation, when } from "./api";
import { useApp } from "./context";
import {
  Badge,
  Empty,
  ErrorBox,
  Field,
  Form,
  FormActions,
  Loading,
  Modal,
} from "./components";
import type { Audit, User } from "./types";

const actions: Record<string, string> = {
  open_session: "فتح جلسة",
  update_sales: "تعديل مبيعات",
  close_session: "اعتماد الإغلاق",
  count_cash: "تسجيل الجرد",
  reopen_session: "إعادة فتح جلسة",
  create_customer: "إضافة عميل",
  update_customer: "تعديل عميل",
  create_debt: "إضافة دين",
  create_payment: "تحصيل دين",
  create_purchase: "تسجيل مشتريات",
  create_movement: "حركة نقدية",
  cancel_debts: "إلغاء دين",
  cancel_payments: "إلغاء سداد",
  cancel_purchases: "إلغاء مشتريات",
  cancel_movements: "إلغاء حركة",
  cancel_generated_movement: "إلغاء الأثر النقدي المرتبط",
  login: "تسجيل دخول",
  create_user: "إضافة مستخدم",
  update_user: "تعديل مستخدم",
  update_settings: "تعديل الإعدادات",
  change_password: "تغيير كلمة المرور",
  bootstrap_admin: "إنشاء المدير الأول",
};

function auditText(raw: string, timezone: string): string {
  const fields: Record<string, string> = {
    id: "رقم السجل",
    drawer_id: "رقم الصندوق",
    business_date: "تاريخ العمل",
    responsible_user_id: "المسؤول",
    created_by: "المستخدم المنشئ",
    previous_session_id: "الجلسة السابقة",
    opening_cash: "رصيد الافتتاح",
    total_sales: "إجمالي المبيعات",
    pos_sales: "مبيعات الشبكة",
    status: "الحالة",
    version: "إصدار الجلسة",
    actual_cash: "النقد الفعلي",
    counted_at: "وقت الجرد",
    count_version: "إصدار الجرد",
    counted_by: "المستخدم الذي جرد الصندوق",
    notes: "الملاحظات",
    closed_at: "وقت الإغلاق",
    closed_by: "المستخدم الذي أغلق",
    created_at: "وقت الإنشاء",
    updated_at: "وقت التعديل",
    name: "الاسم",
    phone: "الهاتف",
    customer_id: "رقم العميل",
    debt_date: "تاريخ الدين",
    amount: "المبلغ",
    due_date: "تاريخ الاستحقاق",
    kind: "النوع",
    session_id: "رقم الجلسة",
    cancelled_at: "وقت الإلغاء",
    cancelled_by: "المستخدم الذي ألغى",
    cancellation_reason: "سبب الإلغاء",
    debt_id: "رقم الدين",
    payment_date: "تاريخ السداد",
    payment_method: "طريقة الدفع",
    purchase_date: "تاريخ المشتريات",
    description: "الوصف",
    supplier: "المورّد",
    from_drawer: "مدفوع من الصندوق",
    invoice_number: "رقم الفاتورة",
    movement_date: "تاريخ الحركة",
    purchase_id: "رقم فاتورة المشتريات",
    debt_payment_id: "رقم دفعة السداد",
    username: "اسم المستخدم",
    full_name: "الاسم الكامل",
    role: "الصلاحية",
    is_active: "حساب نشط",
    revision: "إصدار الإعدادات",
    store_name: "اسم المتجر",
    currency: "العملة",
    timezone: "المنطقة الزمنية",
  };
  const values: Record<string, string> = {
    open: "مفتوحة",
    closed: "مغلقة",
    cash: "نقدًا",
    card: "شبكة / بطاقة",
    bank: "تحويل بنكي",
    admin: "مدير",
    employee: "موظف",
    opening: "رصيد عميل افتتاحي",
    credit: "بيع آجل",
    expense: "مصروف نقدي",
    withdrawal: "سحب نقدي",
    deposit: "إيداع نقدي",
    refund: "مرتجع نقدي",
    purchase: "مشتريات",
    collection: "تحصيل دين",
  };
  return Object.entries(JSON.parse(raw) as Record<string, unknown>)
    .map(([key, value]) => {
      const shown =
        value === null
          ? "—"
          : typeof value === "boolean"
            ? value
              ? "نعم"
              : "لا"
            : typeof value === "string"
              ? ["status", "kind", "payment_method", "role"].includes(key)
                ? values[value] || value
                : key.endsWith("_at") || key.endsWith("_date")
                  ? when(value, timezone)
                  : value
              : String(value);
      return `${fields[key] || "قيمة"}: ${shown}`;
    })
    .join("\n");
}

export default function SettingsPage() {
  const { me, revision, refresh, notify } = useApp(),
    [tab, setTab] = useState(me.user.role === "admin" ? "general" : "security");
  const [store, setStore] = useState(me.settings.store_name),
    [currency, setCurrency] = useState(me.settings.currency),
    [timezone, setTimezone] = useState(me.settings.timezone);
  const [currentPassword, setCurrentPassword] = useState(""),
    [newPassword, setNewPassword] = useState(""),
    [offset, setOffset] = useState(0);
  const [edit, setEdit] = useState<User | "new" | null>(null),
    m = useMutation(),
    p = useMutation();
  const users = useLoad<User[]>(
      tab === "users" && me.user.role === "admin" ? "/users" : null,
      revision,
    ),
    logs = useLoad<Audit[]>(
      tab === "audit" && me.user.role === "admin"
        ? "/audit?limit=50&offset=" + offset
        : null,
      revision,
    );
  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow">إدارة وصلاحيات موثّقة</div>
          <h1>
            {me.user.role === "admin"
              ? "الإعدادات والمستخدمون"
              : "إعدادات الحساب"}
          </h1>
          <p>اضبط هوية المتجر، والصلاحيات، وأمان الوصول.</p>
        </div>
      </div>
      <div className="tabs no-print">
        {(me.user.role === "admin"
          ? [
              ["general", "إعدادات المتجر"],
              ["users", "المستخدمون"],
              ["audit", "سجل التدقيق"],
              ["security", "أمان حسابي"],
            ]
          : [["security", "أمان حسابي"]]
        ).map(([v, l]) => (
          <button
            className={tab === v ? "active" : ""}
            key={v}
            onClick={() => setTab(v)}
          >
            {l}
          </button>
        ))}
      </div>
      {tab === "general" && me.user.role === "admin" && (
        <section className="panel narrow">
          <div className="panel-head">
            <h2>بيانات المتجر</h2>
          </div>
          <Form
            onSubmit={() =>
              m.run(
                "/settings",
                "PUT",
                { store_name: store, currency, timezone },
                () => {
                  notify("تم حفظ إعدادات المتجر");
                  refresh();
                },
              )
            }
          >
            <div className="form-grid">
              <div className="full">
                <Field label="اسم المتجر">
                  <input
                    required
                    maxLength={150}
                    value={store}
                    onChange={(e) => setStore(e.target.value)}
                  />
                </Field>
              </div>
              <Field label="عملة المتجر">
                <select
                  value={currency}
                  onChange={(e) => setCurrency(e.target.value)}
                >
                  {["SAR", "YER", "AED", "USD", "EUR", "GBP", "EGP", "QAR"].map(
                    (c) => (
                      <option key={c}>{c}</option>
                    ),
                  )}
                </select>
              </Field>
              <Field
                label="المنطقة الزمنية"
                hint="اسم منطقة IANA، مثل Asia/Aden"
              >
                <input
                  dir="ltr"
                  required
                  maxLength={64}
                  value={timezone}
                  onChange={(e) => setTimezone(e.target.value)}
                />
              </Field>
            </div>
            <div className="info-box">
              عملة واحدة لكل السجلات، بمبالغ من منزلتين عشريتين. لا يمكن تغيير
              العملة بعد إدخال بيانات مالية، ولا تتغير المنطقة الزمنية أثناء
              جلسة مفتوحة.
            </div>
            <ErrorBox message={m.error} />
            <button className="primary" disabled={m.busy}>
              <Save size={16} /> حفظ الإعدادات
            </button>
          </Form>
        </section>
      )}
      {tab === "users" && me.user.role === "admin" && (
        <section className="panel">
          <div className="panel-head">
            <div>
              <h2>مستخدمو النظام</h2>
              <p>
                المدير يدير التطبيق والتقارير، والموظف يسجل عمليات الجلسة
                المفتوحة
              </p>
            </div>
            <button className="primary" onClick={() => setEdit("new")}>
              <Plus size={16} /> مستخدم جديد
            </button>
          </div>
          <ErrorBox message={users.error} />
          {users.loading ? (
            <Loading />
          ) : users.data?.length ? (
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>الاسم</th>
                    <th>اسم المستخدم</th>
                    <th>الدور</th>
                    <th>الحالة</th>
                    <th>إجراء</th>
                  </tr>
                </thead>
                <tbody>
                  {users.data.map((u) => (
                    <tr key={u.id}>
                      <td>
                        <b>{u.full_name}</b>
                      </td>
                      <td dir="ltr">{u.username}</td>
                      <td>{u.role === "admin" ? "مدير" : "موظف"}</td>
                      <td>
                        <Badge status={u.is_active ? "active" : "disabled"} />
                      </td>
                      <td>
                        <button
                          className="text-button"
                          onClick={() => setEdit(u)}
                        >
                          تعديل الصلاحيات
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <Empty />
          )}
        </section>
      )}
      {tab === "audit" && me.user.role === "admin" && (
        <section className="panel">
          <div className="panel-head">
            <div>
              <h2>سجل العمليات والتصحيحات</h2>
              <p>سجل إضافي لا يقبل حذف أو تعديل أحداثه</p>
            </div>
            <ShieldCheck size={20} />
          </div>
          <ErrorBox message={logs.error} />
          {logs.loading ? (
            <Loading />
          ) : logs.data?.length ? (
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>الوقت</th>
                    <th>المستخدم</th>
                    <th>العملية</th>
                    <th>السجل</th>
                    <th>السبب والتفاصيل</th>
                  </tr>
                </thead>
                <tbody>
                  {logs.data.map((a) => (
                    <tr key={a.id}>
                      <td>{when(a.created_at, me.settings.timezone)}</td>
                      <td>{a.user_name}</td>
                      <td>{actions[a.action] || a.action}</td>
                      <td>#{a.entity_id || "—"}</td>
                      <td>
                        {a.reason || "—"}
                        {(a.before_json || a.after_json) && (
                          <details>
                            <summary>عرض القيم قبل وبعد</summary>
                            <pre dir="rtl">
                              {a.before_json &&
                                "قبل:\n" +
                                  auditText(
                                    a.before_json,
                                    me.settings.timezone,
                                  )}
                              {a.after_json &&
                                "\nبعد:\n" +
                                  auditText(a.after_json, me.settings.timezone)}
                            </pre>
                          </details>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <Empty />
          )}
          <div className="pagination">
            <button
              className="secondary"
              disabled={!offset}
              onClick={() => setOffset((v) => v - 50)}
            >
              السابق
            </button>
            <span>الصفحة {offset / 50 + 1}</span>
            <button
              className="secondary"
              disabled={(logs.data?.length || 0) < 50}
              onClick={() => setOffset((v) => v + 50)}
            >
              التالي
            </button>
          </div>
        </section>
      )}
      {tab === "security" && (
        <section className="panel narrow">
          <div className="panel-head">
            <h2>تغيير كلمة المرور</h2>
          </div>
          <Form
            onSubmit={() =>
              p.run(
                "/auth/password",
                "POST",
                {
                  current_password: currentPassword,
                  new_password: newPassword,
                },
                () => {
                  setCurrentPassword("");
                  setNewPassword("");
                  notify("تم تغيير كلمة المرور وإلغاء الجلسات الأخرى");
                },
              )
            }
          >
            <Field label="كلمة المرور الحالية">
              <input
                type="password"
                autoComplete="current-password"
                required
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
              />
            </Field>
            <Field
              label="كلمة المرور الجديدة"
              hint="12 حرفًا على الأقل، وبحد أقصى 128 حرفًا"
            >
              <input
                type="password"
                autoComplete="new-password"
                required
                minLength={12}
                maxLength={128}
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
              />
            </Field>
            <ErrorBox message={p.error} />
            <button className="primary" disabled={p.busy}>
              <Save size={16} /> تغيير كلمة المرور
            </button>
          </Form>
        </section>
      )}
      {edit && (
        <UserDialog
          user={edit === "new" ? null : edit}
          onClose={() => setEdit(null)}
          onDone={refresh}
        />
      )}
    </>
  );
}

function UserDialog({
  user,
  onClose,
  onDone,
}: {
  user: User | null;
  onClose: () => void;
  onDone: () => void;
}) {
  const { notify } = useApp(),
    m = useMutation(),
    [username, setUsername] = useState(user?.username || ""),
    [name, setName] = useState(user?.full_name || ""),
    [role, setRole] = useState(user?.role || "employee"),
    [active, setActive] = useState(user?.is_active ?? true),
    [password, setPassword] = useState("");
  const close = () => {
    if (!m.busy) onClose();
  };
  return (
    <Modal title={user ? "تعديل المستخدم" : "إضافة مستخدم"} onClose={close}>
      <Form
        onSubmit={() =>
          m.run(
            "/users" + (user ? "/" + user.id : ""),
            user ? "PUT" : "POST",
            user
              ? {
                  full_name: name,
                  role,
                  is_active: active,
                  password: password || null,
                }
              : { username, full_name: name, role, password },
            () => {
              notify("تم حفظ المستخدم");
              onDone();
              onClose();
            },
          )
        }
      >
        <div className="form-grid">
          <Field label="الاسم الكامل">
            <input
              required
              maxLength={150}
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </Field>
          <Field label="اسم المستخدم" hint="حروف لاتينية وأرقام و _ . -">
            <input
              dir="ltr"
              required
              pattern="[a-zA-Z0-9_.-]{3,64}"
              value={username}
              readOnly={!!user}
              onChange={(e) => setUsername(e.target.value)}
            />
          </Field>
          <Field label="الصلاحية">
            <select
              value={role}
              onChange={(e) => setRole(e.target.value as User["role"])}
            >
              <option value="employee">موظف</option>
              <option value="admin">مدير</option>
            </select>
          </Field>
          <Field
            label={user ? "كلمة مرور جديدة (اختياري)" : "كلمة المرور"}
            hint="12 حرفًا على الأقل"
          >
            <input
              type="password"
              autoComplete="new-password"
              required={!user}
              minLength={12}
              maxLength={128}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </Field>
          {user && (
            <label className="check-field full">
              <input
                type="checkbox"
                checked={active}
                onChange={(e) => setActive(e.target.checked)}
              />{" "}
              حساب نشط
            </label>
          )}
        </div>
        <ErrorBox message={m.error} />
        <FormActions busy={m.busy} onClose={close} />
      </Form>
    </Modal>
  );
}
