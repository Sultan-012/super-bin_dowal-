import { useState } from "react";
import { ArrowLeft, CalendarDays } from "lucide-react";
import { money, useLoad, when } from "./api";
import { useApp } from "./context";
import {
  Badge,
  Empty,
  ErrorBox,
  Loading,
  Period,
  SearchBox,
} from "./components";
import type { DailySession } from "./types";

export default function History() {
  const { me, revision, navigate } = useApp(),
    [start, setStart] = useState(me.today.slice(0, 7) + "-01"),
    [end, setEnd] = useState(me.today),
    [q, setQ] = useState(""),
    [status, setStatus] = useState("");
  const { data, error, loading } = useLoad<DailySession[]>(
    `/sessions?start=${start}&end=${end}&limit=367&q=${encodeURIComponent(q)}${status ? "&status=" + status : ""}`,
    revision,
  );
  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow">سجل واضح لكل يوم</div>
          <h1>سجل الجلسات اليومية</h1>
          <p>راجع المبيعات والجرد واعتمادات الإغلاق لكل جلسة.</p>
        </div>
      </div>
      <div className="toolbar wrap">
        <SearchBox
          value={q}
          onChange={setQ}
          placeholder="بحث بالتاريخ أو المسؤول أو رقم الجلسة"
        />
        <div className="inline-actions">
          <select
            aria-label="حالة الجلسة"
            value={status}
            onChange={(e) => setStatus(e.target.value)}
          >
            <option value="">جميع الحالات</option>
            <option value="open">مفتوحة</option>
            <option value="closed">مغلقة</option>
          </select>
          <Period
            start={start}
            end={end}
            onChange={(a, b) => {
              setStart(a);
              setEnd(b);
            }}
          />
        </div>
      </div>
      <ErrorBox message={error} />
      <section className="panel">
        <div className="panel-head">
          <h2>
            <CalendarDays size={18} /> الجلسات المسجلة
          </h2>
          <span className="muted">{data?.length || 0} جلسة معروضة</span>
        </div>
        {loading ? (
          <Loading />
        ) : data?.length ? (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>تاريخ العمل</th>
                  <th>المسؤول</th>
                  <th>إجمالي المبيعات</th>
                  <th>المتوقع</th>
                  <th>آخر جرد</th>
                  <th>الفرق</th>
                  <th>المطابقة</th>
                  <th>الحالة</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {data.map((s) => (
                  <tr key={s.id}>
                    <td>
                      <b>{when(s.business_date)}</b>
                      <small className="block">جلسة #{s.id}</small>
                    </td>
                    <td>{s.responsible_name}</td>
                    <td className="number">{money(s.total_sales)}</td>
                    <td className="number">{money(s.totals.expected_cash)}</td>
                    <td className="number">
                      {money(s.actual_cash)}
                      <small className="block">
                        {s.totals.count_stale
                          ? "جرد سابق للحركات الأخيرة"
                          : when(s.totals.counted_at, me.settings.timezone)}
                      </small>
                    </td>
                    <td className="number">{money(s.totals.difference)}</td>
                    <td>
                      <Badge status={s.totals.reconciliation_status} />
                    </td>
                    <td>
                      <Badge status={s.status} />
                    </td>
                    <td>
                      <button
                        className="text-button"
                        onClick={() => navigate("daily", s.id)}
                      >
                        التفاصيل <ArrowLeft size={14} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <Empty text="لا توجد جلسات تطابق البحث" />
        )}
      </section>
    </>
  );
}
