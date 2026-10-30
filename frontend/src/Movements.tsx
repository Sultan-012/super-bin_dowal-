import { useState } from "react";
import { Plus } from "lucide-react";
import { kindLabel, useLoad } from "./api";
import { useApp } from "./context";
import { ErrorBox, Loading, Period, TransactionsTable } from "./components";
import { EntryDialog, ReasonDialog } from "./dialogs";
import type { EntryType } from "./dialogs";
import type { Current, Transaction } from "./types";

export default function Movements() {
  const { me, revision, refresh, navigate } = useApp(),
    [start, setStart] = useState(me.today),
    [end, setEnd] = useState(me.today),
    [entry, setEntry] = useState<EntryType | null>(null),
    [filter, setFilter] = useState("");
  const [reason, setReason] = useState<{ title: string; path: string } | null>(
    null,
  );
  const current = useLoad<Current>("/sessions/current", revision),
    list = useLoad<Transaction[]>(
      `/transactions?start=${start}&end=${end}`,
      revision,
    );
  const session = current.data?.session || null;
  const filtered =
    list.data?.filter(
      (t) =>
        !filter ||
        (filter === "purchase" ? t.category === "purchase" : t.kind === filter),
    ) || [];
  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow">كل حركة لها مصدر</div>
          <h1>المشتريات وحركات الصندوق</h1>
          <p>فواتير مفصلة وحركات نقدية مرتبطة بجلسة استلام أو دفع المبلغ.</p>
        </div>
        <button
          className="primary"
          disabled={!session}
          onClick={() => setEntry("purchase")}
        >
          <Plus size={17} /> تسجيل مشتريات
        </button>
      </div>
      <ErrorBox message={current.error || list.error} />
      {!session && !current.loading && (
        <div className="alert warning">
          لا توجد جلسة مفتوحة.{" "}
          <button className="text-button" onClick={() => navigate("daily")}>
            فتح يوم عمل
          </button>
        </div>
      )}
      <div className="quick-actions no-print">
        {(["expense", "deposit", "withdrawal", "refund"] as const).map((k) => (
          <button
            className="secondary"
            key={k}
            disabled={!session}
            onClick={() => setEntry(k)}
          >
            <Plus size={16} />
            {kindLabel[k]}
          </button>
        ))}
      </div>
      <div className="toolbar">
        <select
          value={filter}
          aria-label="نوع العملية"
          onChange={(e) => setFilter(e.target.value)}
        >
          <option value="">جميع العمليات</option>
          {["purchase", "expense", "deposit", "withdrawal", "refund"].map(
            (k) => (
              <option key={k} value={k}>
                {kindLabel[k]}
              </option>
            ),
          )}
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
      <section className="panel">
        <div className="panel-head">
          <div>
            <h2>العمليات المسجلة</h2>
            <p>حركات التحصيل والمشتريات تظهر عبر مصدرها مرة واحدة</p>
          </div>
          <span className="muted">{filtered.length} عملية</span>
        </div>
        {list.loading ? (
          <Loading />
        ) : (
          <TransactionsTable
            items={filtered}
            onCancel={
              me.user.role === "admin"
                ? (category, id) =>
                    setReason({
                      title: "إلغاء عملية مع حفظ السجل",
                      path: `/records/${category}/${id}/cancel`,
                    })
                : undefined
            }
          />
        )}
      </section>
      {entry && (
        <EntryDialog
          type={entry}
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
