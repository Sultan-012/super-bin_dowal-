import { useState } from "react";
import { BadgeCheck } from "lucide-react";
import { money, useLoad, when } from "./api";
import { useApp } from "./context";
import {
  Badge,
  Empty,
  ErrorBox,
  Loading,
  Metric,
  Period,
  PrintExport,
  SalesChart,
} from "./components";
import type { Report } from "./types";

export default function Reports() {
  const { me, revision, navigate } = useApp(),
    [start, setStart] = useState(me.today.slice(0, 7) + "-01"),
    [end, setEnd] = useState(me.today);
  const {
    data: r,
    error,
    loading,
  } = useLoad<Report>(`/reports?start=${start}&end=${end}`, revision);
  if (me.user.role !== "admin")
    return <div className="alert warning">التقارير متاحة للمدير فقط.</div>;
  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow">أرقام يمكن الرجوع إليها</div>
          <h1>التقارير والمطابقة</h1>
          <p>تدفقات الفترة، وأرصدة في تواريخ محددة، وفروق الجرد المعتمدة.</p>
        </div>
        <PrintExport
          url={`/api/reports/export.csv?start=${start}&end=${end}`}
        />
      </div>
      <div className="toolbar">
        <div className="section-kicker">
          <BadgeCheck size={18} /> تقرير الفترة{" "}
          <span className="muted">
            {when(start)} — {when(end)}
          </span>
        </div>
        <Period
          start={start}
          end={end}
          onChange={(a, b) => {
            setStart(a);
            setEnd(b);
          }}
        />
      </div>
      <ErrorBox message={error} />
      {loading ? (
        <Loading />
      ) : (
        r && (
          <>
            <div className="print-title">
              {me.settings.store_name} · تقرير المبيعات ومطابقة الصندوق ·{" "}
              {start} — {end} · {me.settings.currency}
            </div>
            <div className="metrics four">
              <Metric
                label="إجمالي مبيعات الفترة"
                value={r.totals.total_sales}
                tone="featured"
              />
              <Metric
                label="إجمالي العجز المعتمد"
                value={r.totals.total_shortages}
                tone="shortage"
                note="مجموع العجز فقط للجلسات المغلقة"
              />
              <Metric
                label="إجمالي الفائض المعتمد"
                value={r.totals.total_surpluses}
                tone="surplus"
                note="مجموع الفائض فقط للجلسات المغلقة"
              />
              <Metric
                label="صافي فرق الصندوق"
                value={r.totals.net_difference}
                note="الفائض ناقص العجز · ليس ربحًا أو خسارة"
              />
            </div>
            <div className="two-columns">
              <section className="panel">
                <div className="panel-head">
                  <h2>المبيعات اليومية</h2>
                </div>
                <SalesChart daily={r.daily} />
              </section>
              <section className="panel">
                <div className="panel-head">
                  <h2>العجز والفائض المعتمد</h2>
                </div>
                <SalesChart daily={r.daily} difference />
              </section>
            </div>
            <section className="panel">
              <div className="panel-head">
                <h2>تفاصيل التدفقات المالية للفترة</h2>
                <span className="muted">
                  {r.session_count} جلسة · {r.closed_count} مغلقة
                </span>
              </div>
              <div className="report-flow">
                {[
                  ["نقدي من المبيعات", r.totals.cash_sales],
                  ["مبيعات الشبكة", r.totals.pos_sales],
                  ["مبيعات آجلة جديدة", r.totals.new_credit_sales],
                  ["تحصيل الديون نقدًا", r.totals.cash_collections],
                  ["تحصيل الديون بالشبكة", r.totals.card_collections],
                  ["تحصيل الديون بتحويل", r.totals.bank_collections],
                  ["مشتريات الصندوق", r.totals.cash_purchases],
                  ["المصروفات النقدية", r.totals.cash_expenses],
                  ["الإيداعات النقدية", r.totals.deposits],
                  ["السحوبات النقدية", r.totals.withdrawals],
                  ["المرتجعات النقدية", r.totals.cash_refunds],
                ].map(([label, value]) => (
                  <div key={label}>
                    <span>{label}</span>
                    <b dir="ltr">{money(value)}</b>
                  </div>
                ))}
              </div>
            </section>
            {r.balance_at_end && (
              <section className="panel">
                <div className="panel-head">
                  <div>
                    <h2>أرصدة بتاريخ {when(r.balance_at_end.business_date)}</h2>
                    <p>
                      أرصدة في تاريخ آخر جلسة في الفترة؛ لا تُجمع عبر الأيام
                    </p>
                  </div>
                </div>
                <div className="balance-strip">
                  <div>
                    <span>افتتاح آخر جلسة</span>
                    <b dir="ltr">{money(r.balance_at_end.opening_cash)}</b>
                  </div>
                  <div>
                    <span>الرصيد المتوقع بنهاية آخر جلسة</span>
                    <b dir="ltr">{money(r.balance_at_end.expected_cash)}</b>
                  </div>
                  <div>
                    <span>
                      آخر جرد ·{" "}
                      {r.last_count
                        ? when(r.last_count.counted_at, r.timezone)
                        : "لم يسجل"}
                    </span>
                    <b dir="ltr">{money(r.last_count?.amount)}</b>
                    {r.last_count?.stale && (
                      <small>جرد سابق للحركات الأخيرة</small>
                    )}
                  </div>
                </div>
              </section>
            )}
            <section className="panel">
              <div className="panel-head">
                <h2>تفاصيل الجلسات</h2>
              </div>
              {r.daily.length ? (
                <div className="table-scroll">
                  <table>
                    <thead>
                      <tr>
                        <th>التاريخ</th>
                        <th>المبيعات</th>
                        <th>نقدي</th>
                        <th>شبكة</th>
                        <th>آجل</th>
                        <th>المتوقع</th>
                        <th>آخر جرد</th>
                        <th>الفرق المعتمد</th>
                        <th>الحالة</th>
                      </tr>
                    </thead>
                    <tbody>
                      {r.daily.map((d) => (
                        <tr key={d.id}>
                          <td>
                            <button
                              className="text-button"
                              onClick={() => navigate("daily", d.id)}
                            >
                              {when(d.business_date)}
                            </button>
                          </td>
                          <td className="number">{money(d.total_sales)}</td>
                          <td className="number">{money(d.cash_sales)}</td>
                          <td className="number">{money(d.pos_sales)}</td>
                          <td className="number">
                            {money(d.new_credit_sales)}
                          </td>
                          <td className="number">{money(d.expected_cash)}</td>
                          <td className="number">
                            {money(d.actual_cash)}
                            {d.count_stale && (
                              <small className="block">جرد سابق</small>
                            )}
                          </td>
                          <td className="number">
                            {d.status === "closed"
                              ? money(d.difference)
                              : "غير معتمد"}
                          </td>
                          <td>
                            <Badge status={d.status} />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <Empty text="لا توجد جلسات خلال الفترة" />
              )}
            </section>
          </>
        )
      )}
    </>
  );
}
