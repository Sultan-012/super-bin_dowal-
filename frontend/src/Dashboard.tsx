import { useState } from "react";
import {
  ArrowLeft,
  Banknote,
  CreditCard,
  HandCoins,
  Plus,
  Receipt,
  ShieldCheck,
  TrendingUp,
  Wallet,
} from "lucide-react";
import { money, useLoad, when } from "./api";
import { useApp } from "./context";
import {
  Badge,
  Empty,
  ErrorBox,
  Loading,
  Metric,
  Period,
  SalesChart,
  TransactionsTable,
} from "./components";
import type { Report } from "./types";

export default function Dashboard() {
  const { me, revision, navigate } = useApp(),
    [start, setStart] = useState(me.today),
    [end, setEnd] = useState(me.today);
  const {
    data: r,
    error,
    loading,
  } = useLoad<Report>(`/dashboard?start=${start}&end=${end}`, revision);
  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow">كل التفاصيل، في مكان واحد</div>
          <h1>نظرة عامة على أعمالك</h1>
          <p>تابع مبيعاتك، والتزامات عملائك، وحركة الصندوق بوضوح.</p>
        </div>
        <button className="primary" onClick={() => navigate("daily")}>
          <Plus size={18} /> إدارة يوم العمل
        </button>
      </div>
      <div className="toolbar">
        <div className="section-kicker">
          <span className="live-dot" />
          {start === end ? "ملخص يوم العمل" : "ملخص تدفقات الفترة"}
          <span className="muted">
            {start === end ? when(start) : `${when(start)} — ${when(end)}`}
          </span>
        </div>
        <Period
          start={start}
          end={end}
          dayOnly={me.user.role !== "admin"}
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
            <div className="metrics four">
              <Metric
                label="إجمالي المبيعات"
                value={r.totals.total_sales}
                icon={<TrendingUp size={19} />}
                tone="featured"
                note="قبل المرتجعات · يشمل النقدي والشبكة والآجل"
              />
              <Metric
                label="المبيعات النقدية"
                value={r.totals.cash_sales}
                icon={<Banknote size={19} />}
                note="النقد المستلم من مبيعات الفترة"
              />
              <Metric
                label="مبيعات الشبكة"
                value={r.totals.pos_sales}
                icon={<CreditCard size={19} />}
                note="مبيعات البطاقات فقط، دون تحصيل الديون"
              />
              <Metric
                label="المبيعات الآجلة الجديدة"
                value={r.totals.new_credit_sales}
                icon={<HandCoins size={19} />}
                note="من سجلات الديون المرتبطة بالفترة"
              />
            </div>
            <div className="dashboard-middle">
              <section className="panel">
                <div className="panel-head">
                  <div>
                    <h2>المبيعات اليومية</h2>
                    <p>تطور المبيعات المسجلة خلال الفترة المحددة</p>
                  </div>
                  <span className="legend">
                    <i /> إجمالي المبيعات
                  </span>
                </div>
                <SalesChart daily={r.daily} />
              </section>
              <section className="panel drawer-panel">
                <div className="panel-head">
                  <div>
                    <h2>مطابقة الصندوق</h2>
                    <p>
                      {r.balance_at_end
                        ? "رصيد في " + when(r.balance_at_end.business_date)
                        : "بانتظار فتح أول جلسة"}
                    </p>
                  </div>
                  <ShieldCheck size={21} />
                </div>
                {r.balance_at_end ? (
                  <>
                    <span className="muted">الرصيد المتوقع للصندوق</span>
                    <div className="drawer-amount">
                      <b dir="ltr">{money(r.balance_at_end.expected_cash)}</b>
                      <small>{me.settings.currency}</small>
                    </div>
                    <div className="count-row">
                      <div>
                        <strong>آخر جرد</strong>
                        <small>
                          {r.last_count
                            ? when(r.last_count.counted_at, r.timezone)
                            : "لم يُسجّل جرد في الفترة"}
                        </small>
                      </div>
                      <b dir="ltr">{money(r.last_count?.amount)}</b>
                    </div>
                    {r.last_count?.stale && (
                      <p className="stale">
                        سُجّلت حركات بعد هذا الجرد؛ لا يمثل النقد الفعلي الحالي.
                      </p>
                    )}
                    <div
                      className={
                        "reconcile-status " +
                        (r.balance_at_end.difference === null
                          ? "pending"
                          : Number(r.balance_at_end.difference) < 0
                            ? "shortage"
                            : Number(r.balance_at_end.difference) > 0
                              ? "surplus"
                              : "balanced")
                      }
                    >
                      <span>{r.balance_at_end.reconciliation_message}</span>
                      <ShieldCheck size={18} />
                    </div>
                    <button
                      className="text-button"
                      onClick={() =>
                        navigate("daily", r.daily[r.daily.length - 1].id)
                      }
                    >
                      عرض تفاصيل الجلسة <ArrowLeft size={15} />
                    </button>
                  </>
                ) : (
                  <Empty text="لم يُفتح يوم عمل في هذه الفترة" />
                )}
              </section>
            </div>
            <div className="metrics four compact">
              <Metric
                label="تحصيل الديون نقدًا"
                value={r.totals.cash_collections}
                icon={<Wallet size={18} />}
                note="يزيد نقد الصندوق دون زيادة المبيعات"
              />
              <Metric
                label="تحصيل الديون بغير النقد"
                value={r.totals.noncash_collections}
                icon={<CreditCard size={18} />}
                note={`شبكة ${money(r.totals.card_collections)} · تحويل ${money(r.totals.bank_collections)}`}
              />
              <Metric
                label="مشتريات من الصندوق"
                value={r.totals.cash_purchases}
                icon={<Receipt size={18} />}
                note="المشتريات النقدية المدفوعة من الدرج فقط"
              />
              <Metric
                label="المصروفات النقدية"
                value={r.totals.cash_expenses}
                icon={<Banknote size={18} />}
                note="دون احتساب المشتريات مرة أخرى"
              />
            </div>
            <div className="dashboard-bottom">
              <section className="panel">
                <div className="panel-head">
                  <div>
                    <h2>أحدث العمليات</h2>
                    <p>حركات الفترة من السجلات المحفوظة</p>
                  </div>
                  <button
                    className="text-button"
                    onClick={() => navigate("movements")}
                  >
                    عرض الكل <ArrowLeft size={15} />
                  </button>
                </div>
                <TransactionsTable items={r.recent_transactions} />
              </section>
              <section className="panel debt-panel">
                <div className="soft-icon">
                  <HandCoins size={25} />
                </div>
                <h2>ديون العملاء المتبقية</h2>
                <p>الرصيد الإجمالي المستحق الآن، لكل العملاء</p>
                <div className="drawer-amount">
                  <b dir="ltr">{money(r.outstanding_debts_now)}</b>
                  <small>{r.currency}</small>
                </div>
                <small className="muted">
                  حتى {when(r.outstanding_as_of, r.timezone)}
                </small>
                <button
                  className="secondary"
                  onClick={() => navigate("customers")}
                >
                  إدارة حسابات العملاء <ArrowLeft size={16} />
                </button>
                <div className="subtle-rule" />
                <div className="mini-count">
                  <span>جلسات الفترة</span>
                  <b>{r.session_count}</b>
                </div>
                <div className="mini-count">
                  <span>جلسات معتمدة</span>
                  <b>{r.closed_count}</b>
                </div>
                <Badge
                  status={
                    r.closed_count === r.session_count && r.session_count > 0
                      ? "closed"
                      : "open"
                  }
                />
              </section>
            </div>
          </>
        )
      )}
    </>
  );
}
