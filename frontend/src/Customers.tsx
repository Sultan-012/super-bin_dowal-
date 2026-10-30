import { useState } from "react";
import { ArrowRight, HandCoins, Plus, UserRoundPen, Users } from "lucide-react";
import { methodLabel, money, useLoad, when } from "./api";
import { useApp } from "./context";
import {
  Badge,
  Empty,
  ErrorBox,
  Loading,
  Metric,
  PrintExport,
  SearchBox,
} from "./components";
import { EntryDialog, ReasonDialog } from "./dialogs";
import type { EntryType } from "./dialogs";
import type { Current, Customer, Statement } from "./types";

export default function Customers() {
  const { me, revision, refresh } = useApp(),
    [q, setQ] = useState(""),
    [offset, setOffset] = useState(0),
    [selected, setSelected] = useState<Customer | null>(null),
    [entry, setEntry] = useState<EntryType | null>(null);
  const [reason, setReason] = useState<{ title: string; path: string } | null>(
    null,
  );
  const list = useLoad<Customer[]>(
      `/customers?q=${encodeURIComponent(q)}&offset=${offset}&limit=50`,
      revision,
    ),
    current = useLoad<Current>("/sessions/current", revision);
  const statement = useLoad<Statement>(
    selected ? `/customers/${selected.id}/statement` : null,
    revision,
  );
  const session = current.data?.session || null;
  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow">حسابات تحفظ حقوقك</div>
          <h1>{selected ? "كشف حساب العميل" : "العملاء والديون"}</h1>
          <p>
            {selected
              ? selected.name
              : "تابع الديون السابقة والمبيعات الآجلة والدفعات دون خلطها بالمبيعات النقدية."}
          </p>
        </div>
        <div className="inline-actions no-print">
          {selected ? (
            <>
              <button className="secondary" onClick={() => setSelected(null)}>
                <ArrowRight size={16} /> كل العملاء
              </button>
              <PrintExport
                url={`/api/customers/${selected.id}/statement.csv`}
              />
            </>
          ) : (
            <button className="primary" onClick={() => setEntry("customer")}>
              <Plus size={17} /> إضافة عميل
            </button>
          )}
        </div>
      </div>
      <ErrorBox message={list.error || statement.error || current.error} />
      {selected ? (
        statement.loading ? (
          <Loading />
        ) : (
          statement.data && (
            <>
              <div className="customer-banner panel">
                <div className="customer-profile">
                  <div className="avatar large">
                    {selected.name.slice(0, 1)}
                  </div>
                  <div>
                    <h2>{statement.data?.customer.name || selected.name}</h2>
                    <p>
                      {statement.data.customer.phone || "لم يُضف رقم هاتف"}
                      {statement.data.customer.notes &&
                        " · " + statement.data.customer.notes}
                    </p>
                  </div>
                </div>
                <div className="inline-actions no-print">
                  <button
                    className="secondary"
                    onClick={() => setEntry("customer")}
                  >
                    <UserRoundPen size={16} /> تعديل العميل
                  </button>
                  <button
                    className="secondary"
                    onClick={() => setEntry("debt")}
                    disabled={!session && me.user.role !== "admin"}
                  >
                    <Plus size={16} /> إضافة دين
                  </button>
                  <button
                    className="primary"
                    onClick={() => setEntry("payment")}
                    disabled={!session}
                  >
                    <HandCoins size={16} /> تحصيل دفعة
                  </button>
                </div>
              </div>
              {!session && (
                <div className="info-box">
                  افتح جلسة يوم عمل لتسجيل التحصيل أو البيع الآجل. يمكن للمدير
                  إضافة أرصدة العملاء الافتتاحية دون جلسة.
                </div>
              )}
              <div className="metrics three">
                <Metric
                  label="إجمالي الديون الصحيحة"
                  value={statement.data.original}
                />
                <Metric
                  label="إجمالي الدفعات الصحيحة"
                  value={statement.data.paid}
                />
                <Metric
                  label="الرصيد المتبقي"
                  value={statement.data.outstanding}
                  tone="featured"
                />
              </div>
              <section className="panel">
                <div className="panel-head">
                  <div>
                    <h2>تفاصيل الديون</h2>
                    <p>أرصدة افتتاحية وبيع آجل، مع حالة كل دين</p>
                  </div>
                </div>
                {statement.data.debts.length ? (
                  <div className="table-scroll">
                    <table>
                      <thead>
                        <tr>
                          <th>الدين</th>
                          <th>النوع</th>
                          <th>المبلغ الأصلي</th>
                          <th>المسدد</th>
                          <th>المتبقي</th>
                          <th>الاستحقاق</th>
                          <th>الحالة</th>
                          {me.user.role === "admin" && <th>إجراء</th>}
                        </tr>
                      </thead>
                      <tbody>
                        {statement.data.debts.map((d) => (
                          <tr
                            key={d.id}
                            className={d.cancelled_at ? "cancelled" : ""}
                          >
                            <td>
                              <b>#{d.id}</b>
                              <small className="block">
                                {when(d.debt_date)}
                              </small>
                              {d.notes && (
                                <small className="block">{d.notes}</small>
                              )}
                            </td>
                            <td>
                              {d.kind === "opening"
                                ? "رصيد عميل افتتاحي"
                                : "بيع آجل"}
                              <small className="block">
                                {d.session_id
                                  ? "جلسة #" + d.session_id
                                  : "سابق للنظام"}
                              </small>
                            </td>
                            <td className="number">{money(d.amount)}</td>
                            <td className="number">{money(d.paid)}</td>
                            <td className="number">
                              <b>{money(d.remaining)}</b>
                            </td>
                            <td>{when(d.due_date)}</td>
                            <td>
                              <Badge status={d.debt_status} />
                            </td>
                            {me.user.role === "admin" && (
                              <td>
                                {!d.cancelled_at &&
                                  (!d.session_id ||
                                    d.session_id === session?.id) && (
                                    <button
                                      className="text-button danger-text"
                                      onClick={() =>
                                        setReason({
                                          title: "إلغاء دين مع حفظ السجل",
                                          path: `/records/debts/${d.id}/cancel`,
                                        })
                                      }
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
                  <Empty text="لم تُسجّل ديون لهذا العميل" />
                )}
              </section>
              <section className="panel">
                <div className="panel-head">
                  <h2>سجل الدفعات</h2>
                </div>
                {statement.data.payments.length ? (
                  <div className="table-scroll">
                    <table>
                      <thead>
                        <tr>
                          <th>التاريخ</th>
                          <th>الدين</th>
                          <th>المبلغ</th>
                          <th>طريقة الدفع</th>
                          <th>المستخدم</th>
                          <th>الحالة</th>
                          {me.user.role === "admin" && <th>إجراء</th>}
                        </tr>
                      </thead>
                      <tbody>
                        {statement.data.payments.map((p) => (
                          <tr
                            key={p.id}
                            className={p.cancelled_at ? "cancelled" : ""}
                          >
                            <td>{when(p.payment_date)}</td>
                            <td>#{p.debt_id}</td>
                            <td className="number">{money(p.amount)}</td>
                            <td>{methodLabel[p.payment_method]}</td>
                            <td>{p.recorded_by_name}</td>
                            <td>
                              <Badge
                                status={p.cancelled_at ? "cancelled" : "paid"}
                              />
                            </td>
                            {me.user.role === "admin" && (
                              <td>
                                {!p.cancelled_at &&
                                  p.session_id === session?.id && (
                                    <button
                                      className="text-button danger-text"
                                      onClick={() =>
                                        setReason({
                                          title: "إلغاء دفعة مع حفظ السجل",
                                          path: `/records/payments/${p.id}/cancel`,
                                        })
                                      }
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
                  <Empty text="لا توجد دفعات بعد" />
                )}
              </section>
              <section className="panel">
                <div className="panel-head">
                  <h2>الحركة المتتابعة للحساب</h2>
                  <span className="muted">الملغى ظاهر دون تأثير في الرصيد</span>
                </div>
                {statement.data.entries.length ? (
                  <div className="table-scroll">
                    <table>
                      <thead>
                        <tr>
                          <th>التاريخ</th>
                          <th>العملية</th>
                          <th>المبلغ</th>
                          <th>الرصيد بعد الحركة</th>
                          <th>الحالة</th>
                        </tr>
                      </thead>
                      <tbody>
                        {statement.data.entries.map((e) => (
                          <tr key={e.kind + "-" + e.id}>
                            <td>{when(e.date)}</td>
                            <td>
                              {e.kind === "debt" ? "دين" : "تحصيل"} #{e.id}
                            </td>
                            <td className="number">{money(e.amount)}</td>
                            <td className="number">
                              {money(e.running_balance)}
                            </td>
                            <td>{e.cancelled ? "ملغى" : "صحيح"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <Empty />
                )}
              </section>
            </>
          )
        )
      ) : (
        <>
          <div className="toolbar">
            <SearchBox
              value={q}
              onChange={(v) => {
                setQ(v);
                setOffset(0);
              }}
              placeholder="بحث باسم العميل أو رقم الهاتف"
            />
            <span className="muted">50 عميلًا لكل صفحة</span>
          </div>
          <section className="panel">
            <div className="panel-head">
              <h2>
                <Users size={18} /> حسابات العملاء
              </h2>
            </div>
            {list.loading ? (
              <Loading />
            ) : list.data?.length ? (
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>العميل</th>
                      <th>الهاتف</th>
                      <th>عدد الديون</th>
                      <th>الرصيد المستحق الآن</th>
                      <th>إجراء</th>
                    </tr>
                  </thead>
                  <tbody>
                    {list.data.map((c) => (
                      <tr key={c.id}>
                        <td>
                          <div className="customer-cell">
                            <div className="avatar">{c.name.slice(0, 1)}</div>
                            <b>{c.name}</b>
                          </div>
                        </td>
                        <td dir="ltr">{c.phone || "—"}</td>
                        <td>{c.debt_count}</td>
                        <td className="number">
                          <b>{money(c.outstanding)}</b>{" "}
                          <small>{me.settings.currency}</small>
                        </td>
                        <td>
                          <button
                            className="text-button"
                            onClick={() => setSelected(c)}
                          >
                            كشف الحساب ←
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <Empty text="لا توجد حسابات تطابق البحث" />
            )}
            <div className="pagination no-print">
              <button
                className="secondary"
                disabled={offset === 0}
                onClick={() => setOffset((v) => v - 50)}
              >
                السابق
              </button>
              <span>الصفحة {offset / 50 + 1}</span>
              <button
                className="secondary"
                disabled={(list.data?.length || 0) < 50}
                onClick={() => setOffset((v) => v + 50)}
              >
                التالي
              </button>
            </div>
          </section>
        </>
      )}
      {entry && (
        <EntryDialog
          type={entry}
          customer={statement.data?.customer || selected || undefined}
          session={session}
          onClose={() => setEntry(null)}
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
