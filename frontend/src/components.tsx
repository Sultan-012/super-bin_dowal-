import { useEffect, useRef, useState } from "react";
import type { FormEvent, ReactNode } from "react";
import {
  ArrowDownLeft,
  ArrowUpRight,
  Check,
  ChevronLeft,
  Download,
  LoaderCircle,
  Printer,
  Search,
  X,
} from "lucide-react";
import { kindLabel, methodLabel, money, when } from "./api";
import { useApp } from "./context";
import type { Totals, Transaction } from "./types";

export function Empty({
  text = "لا توجد بيانات مسجلة بعد",
  children,
}: {
  text?: string;
  children?: ReactNode;
}) {
  return (
    <div className="empty">
      <div className="empty-icon">≋</div>
      <strong>{text}</strong>
      <p>ستظهر البيانات هنا عند تسجيل العمليات.</p>
      {children}
    </div>
  );
}
export function Loading() {
  return (
    <div className="loading">
      <LoaderCircle className="spin" size={24} /> جارٍ تحميل البيانات…
    </div>
  );
}
export function ErrorBox({ message }: { message: string }) {
  return message ? (
    <div className="alert danger" role="alert">
      {message}
    </div>
  ) : null;
}
export function Badge({ status }: { status: string }) {
  return (
    <span className={"badge " + status}>
      {(
        {
          open: "مفتوحة",
          closed: "مغلقة",
          valid: "صحيح",
          active: "نشط",
          disabled: "معطل",
          pending: "بانتظار الجرد",
          balanced: "مطابق",
          shortage: "عجز",
          surplus: "فائض",
          unpaid: "غير مسدد",
          partial: "مسدد جزئيًا",
          paid: "مسدد بالكامل",
          cancelled: "ملغى",
        } as Record<string, string>
      )[status] || status}
    </span>
  );
}
export function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <label className="field">
      <span>{label}</span>
      {children}
      {hint && <small>{hint}</small>}
    </label>
  );
}
export function AmountInput({
  value,
  onChange,
  required = false,
  readOnly = false,
}: {
  value: string;
  onChange?: (v: string) => void;
  required?: boolean;
  readOnly?: boolean;
}) {
  return (
    <input
      type="text"
      dir="ltr"
      inputMode="decimal"
      pattern="[0-9]+([.][0-9]{1,2})?"
      placeholder="0.00"
      value={value}
      onInvalid={(e) =>
        e.currentTarget.setCustomValidity(
          "أدخل مبلغًا غير سالب وبمنزلتين عشريتين كحد أقصى، مثل 150.00",
        )
      }
      onInput={(e) => e.currentTarget.setCustomValidity("")}
      onChange={(e) =>
        onChange?.(
          e.target.value.replace(/[٠-٩]/g, (d) =>
            String("٠١٢٣٤٥٦٧٨٩".indexOf(d)),
          ),
        )
      }
      required={required}
      readOnly={readOnly}
      maxLength={19}
    />
  );
}
export function Metric({
  label,
  value,
  icon,
  tone = "",
  note,
}: {
  label: string;
  value: string | null | undefined;
  icon?: ReactNode;
  tone?: string;
  note?: string;
}) {
  const { me } = useApp();
  return (
    <article className={"metric " + tone}>
      <div className="metric-head">
        <span>{label}</span>
        {icon && <i>{icon}</i>}
      </div>
      <div className="metric-value">
        <b dir="ltr">{money(value)}</b>
        <small>{me.settings.currency}</small>
      </div>
      {note && <p>{note}</p>}
    </article>
  );
}
export function Modal({
  title,
  subtitle,
  onClose,
  children,
  wide = false,
}: {
  title: string;
  subtitle?: string;
  onClose: () => void;
  children: ReactNode;
  wide?: boolean;
}) {
  const ref = useRef<HTMLDivElement>(null),
    oldFocus = useRef(document.activeElement as HTMLElement | null);
  useEffect(() => {
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const first = ref.current?.querySelector<HTMLElement>(
      "input,select,textarea,button",
    );
    first?.focus();
    return () => {
      document.body.style.overflow = prev;
      oldFocus.current?.focus();
    };
  }, []);
  return (
    <div
      className="modal-backdrop"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
      onKeyDown={(e) => {
        if (e.key === "Escape") onClose();
        if (e.key === "Tab") {
          const list = Array.from(
            ref.current?.querySelectorAll<HTMLElement>(
              "button:not(:disabled),input:not(:disabled),select:not(:disabled),textarea:not(:disabled),a[href]",
            ) || [],
          );
          const first = list[0],
            last = list[list.length - 1];
          if (e.shiftKey && document.activeElement === first) {
            e.preventDefault();
            last?.focus();
          } else if (!e.shiftKey && document.activeElement === last) {
            e.preventDefault();
            first?.focus();
          }
        }
      }}
    >
      <div
        ref={ref}
        className={"modal " + (wide ? "wide" : "")}
        role="dialog"
        aria-modal="true"
        aria-label={title}
      >
        <div className="modal-head">
          <div>
            <h2>{title}</h2>
            {subtitle && <p>{subtitle}</p>}
          </div>
          <button className="icon-button" onClick={onClose} aria-label="إغلاق">
            <X size={20} />
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}
export function Form({
  onSubmit,
  children,
}: {
  onSubmit: (e: FormEvent) => void;
  children: ReactNode;
}) {
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit(e);
      }}
    >
      {children}
    </form>
  );
}
export function FormActions({
  busy,
  onClose,
  label = "حفظ العملية",
}: {
  busy: boolean;
  onClose: () => void;
  label?: string;
}) {
  return (
    <div className="form-actions">
      <button className="primary" type="submit" disabled={busy}>
        {busy ? (
          <LoaderCircle size={17} className="spin" />
        ) : (
          <Check size={17} />
        )}{" "}
        {busy ? "جارٍ الحفظ…" : label}
      </button>
      <button
        className="secondary"
        type="button"
        onClick={onClose}
        disabled={busy}
      >
        إلغاء
      </button>
    </div>
  );
}
export function SearchBox({
  value,
  onChange,
  placeholder,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder: string;
}) {
  return (
    <div className="search">
      <Search size={17} />
      <input
        aria-label={placeholder}
        placeholder={placeholder}
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
    </div>
  );
}
export function Period({
  start,
  end,
  onChange,
  dayOnly = false,
}: {
  start: string;
  end: string;
  onChange: (a: string, b: string) => void;
  dayOnly?: boolean;
}) {
  const { me } = useApp(),
    [mode, setMode] = useState(start === end ? "day" : "custom");
  return (
    <div className="period">
      <select
        aria-label="نوع الفترة"
        value={mode}
        onChange={(e) => {
          const m = e.target.value;
          setMode(m);
          if (m === "day") onChange(me.today, me.today);
          if (m === "month") {
            const first = me.today.slice(0, 7) + "-01";
            const d = new Date(
              Number(me.today.slice(0, 4)),
              Number(me.today.slice(5, 7)),
              0,
            );
            onChange(
              first,
              me.today.slice(0, 7) + "-" + String(d.getDate()).padStart(2, "0"),
            );
          }
        }}
      >
        <option value="day">يوم واحد</option>
        {!dayOnly && (
          <>
            <option value="month">شهر كامل</option>
            <option value="custom">فترة مخصصة</option>
          </>
        )}
      </select>
      {mode === "month" ? (
        <input
          type="month"
          aria-label="الشهر"
          value={start.slice(0, 7)}
          onChange={(e) => {
            if (!e.target.value) return;
            const [y, m] = e.target.value.split("-").map(Number);
            const last = new Date(y, m, 0).getDate();
            onChange(e.target.value + "-01", e.target.value + "-" + last);
          }}
        />
      ) : (
        <>
          <input
            type="date"
            aria-label="من تاريخ"
            value={start}
            onChange={(e) => {
              if (e.target.value)
                onChange(e.target.value, mode === "day" ? e.target.value : end);
            }}
          />
          {mode === "custom" && (
            <>
              <span>إلى</span>
              <input
                type="date"
                aria-label="إلى تاريخ"
                value={end}
                onChange={(e) => {
                  if (e.target.value) onChange(start, e.target.value);
                }}
              />
            </>
          )}
        </>
      )}
    </div>
  );
}
export function PrintExport({ url }: { url?: string }) {
  return (
    <div className="inline-actions no-print">
      {url && (
        <a className="secondary" href={url}>
          <Download size={16} /> تصدير CSV
        </a>
      )}
      <button className="secondary" onClick={() => window.print()}>
        <Printer size={16} /> طباعة
      </button>
    </div>
  );
}
export function SalesChart({
  daily,
  difference = false,
}: {
  daily: Totals[];
  difference?: boolean;
}) {
  const visible = difference
    ? daily.filter((x) => x.status === "closed")
    : daily;
  if (!visible.length)
    return (
      <Empty
        text={
          difference
            ? "لا توجد جلسات مغلقة في هذه الفترة"
            : "لا توجد مبيعات في هذه الفترة"
        }
      />
    );
  const w = 700,
    h = 210,
    left = 25,
    right = 20,
    top = 20,
    bottom = 35;
  const values = visible.map((x) =>
    Number(difference ? x.difference || "0" : x.total_sales),
  );
  const max = Math.max(...values.map(Math.abs), 1),
    base = difference ? (h - bottom + top) / 2 : h - bottom;
  const amp = difference ? (h - bottom - top) / 2 : h - bottom - top;
  const slot = (w - left - right) / visible.length,
    bw = Math.min(38, slot * 0.6);
  return (
    <div className="chart">
      <svg
        viewBox={`0 0 ${w} ${h}`}
        role="img"
        aria-label={
          difference ? "فروق جرد الجلسات المغلقة" : "المبيعات اليومية"
        }
      >
        {[0, 0.5, 1].map((n) => (
          <line
            key={n}
            x1={left}
            x2={w - right}
            y1={top + n * (h - top - bottom)}
            y2={top + n * (h - top - bottom)}
            stroke="#e5ebe8"
            strokeDasharray="4 5"
          />
        ))}
        {difference && (
          <line x1={left} x2={w - right} y1={base} y2={base} stroke="#a5b8ad" />
        )}
        {visible.map((d, i) => {
          const y = base - (values[i] / max) * amp,
            x = left + i * slot + slot / 2;
          return (
            <g key={d.id}>
              <rect
                x={x - bw / 2}
                y={Math.min(base, y)}
                width={bw}
                height={Math.max(Math.abs(y - base), 1.5)}
                rx={5}
                fill={
                  difference
                    ? values[i] < 0
                      ? "#d47861"
                      : "#36a47a"
                    : "#218668"
                }
              >
                <title>
                  {d.business_date}:{" "}
                  {money(difference ? d.difference : d.total_sales)}
                </title>
              </rect>
              {(visible.length <= 12 ||
                i % Math.ceil(visible.length / 9) === 0) && (
                <text
                  x={x}
                  y={h - 8}
                  textAnchor="middle"
                  fontSize="11"
                  fill="#7a8981"
                >
                  {d.business_date.slice(5)}
                </text>
              )}
            </g>
          );
        })}
        <text
          x={w - right}
          y={14}
          textAnchor="end"
          fontSize="11"
          fill="#7a8981"
        >
          {money(max.toFixed(2))}
        </text>
      </svg>
      <p className="chart-caption">
        {difference
          ? "الفروق المعتمدة للجلسات المغلقة فقط؛ الأعمدة أعلى الخط تمثل الفائض وأسفله تمثل العجز."
          : "مرّر المؤشر على العمود لعرض إجمالي المبيعات قبل المرتجعات."}
      </p>
    </div>
  );
}
export function TransactionsTable({
  items,
  onCancel,
}: {
  items: Transaction[];
  onCancel?: (category: string, id: number) => void;
}) {
  const { me, navigate } = useApp();
  return !items.length ? (
    <Empty text="لا توجد حركات في الفترة المحددة" />
  ) : (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>
            <th>العملية</th>
            <th>التاريخ</th>
            <th>طريقة الدفع</th>
            <th>المبلغ</th>
            <th>المسؤول</th>
            <th>الحالة</th>
            {onCancel && <th>إجراء</th>}
          </tr>
        </thead>
        <tbody>
          {items.map((x) => (
            <tr
              key={x.category + "-" + x.id}
              className={x.cancelled_at ? "cancelled" : ""}
            >
              <td>
                <div className="transaction-title">
                  <i
                    className={
                      x.category === "collection" || x.kind === "deposit"
                        ? "green"
                        : "sand"
                    }
                  >
                    {x.category === "collection" || x.kind === "deposit" ? (
                      <ArrowDownLeft size={16} />
                    ) : (
                      <ArrowUpRight size={16} />
                    )}
                  </i>
                  <span>
                    <strong>{x.description}</strong>
                    <small>
                      {kindLabel[x.kind || x.category] || "حركة"} · #{x.id}
                      {x.session_id && (
                        <button
                          className="text-button"
                          onClick={() => navigate("daily", x.session_id!)}
                        >
                          {" "}
                          جلسة #{x.session_id}
                          <ChevronLeft size={12} />
                        </button>
                      )}
                    </small>
                  </span>
                </div>
              </td>
              <td>{when(x.date)}</td>
              <td>
                {x.payment_method ? methodLabel[x.payment_method] : "نقدًا"}
                {x.category === "purchase" && !x.from_drawer && (
                  <small className="block">خارج الصندوق</small>
                )}
              </td>
              <td className="number">
                {money(x.amount)} <small>{me.settings.currency}</small>
              </td>
              <td>{x.recorded_by_name}</td>
              <td>
                <Badge status={x.cancelled_at ? "cancelled" : "valid"} />
              </td>
              {onCancel && (
                <td>
                  {!x.cancelled_at && (
                    <button
                      className="text-button danger-text"
                      onClick={() =>
                        onCancel(
                          x.category === "purchase"
                            ? "purchases"
                            : x.category === "collection"
                              ? "payments"
                              : x.category === "debt"
                                ? "debts"
                                : "movements",
                          x.id,
                        )
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
  );
}
