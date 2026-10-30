import { useEffect, useRef, useState } from "react";
export class APIError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}
const csrf = () =>
  decodeURIComponent(
    document.cookie
      .split("; ")
      .find((x) => x.startsWith("daily_sales_csrf="))
      ?.split("=")
      .slice(1)
      .join("=") || "",
  );
export async function api<T>(
  path: string,
  method = "GET",
  data?: unknown,
  key?: string,
): Promise<T> {
  let response: Response;
  try {
    response = await fetch("/api" + path, {
      method,
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "X-CSRF-Token": csrf(),
        ...(key ? { "Idempotency-Key": key } : {}),
      },
      body: data === undefined ? undefined : JSON.stringify(data),
    });
  } catch {
    throw new APIError(
      0,
      "تعذر الاتصال بالخادم. تحقق من الاتصال وأعد المحاولة؛ سيُستخدم مفتاح الطلب نفسه لمنع التكرار.",
    );
  }
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    if (response.status === 401 && !path.includes("/auth/login"))
      window.dispatchEvent(new Event("session-expired"));
    throw new APIError(response.status, body?.detail || "تعذر إكمال الطلب");
  }
  return body as T;
}

export function useLoad<T>(path: string | null, revision = 0) {
  const [data, setData] = useState<T | null>(null),
    [error, setError] = useState(""),
    [loading, setLoading] = useState(true);
  useEffect(() => {
    let active = true;
    setData(null);
    setError("");
    setLoading(!!path);
    if (path)
      api<T>(path)
        .then((x) => {
          if (active) setData(x);
        })
        .catch((e) => {
          if (active) setError(e.message);
        })
        .finally(() => {
          if (active) setLoading(false);
        });
    return () => {
      active = false;
    };
  }, [path, revision]);
  return { data, error, loading };
}

export function useMutation() {
  const [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const pending = useRef(false),
    attempt = useRef({ fingerprint: "", key: "" });
  async function run<T>(
    path: string,
    method: string,
    data: unknown,
    success: (result: T) => void,
  ) {
    if (pending.current) return;
    pending.current = true;
    setBusy(true);
    setError("");
    const fingerprint = JSON.stringify({ path, method, data });
    if (attempt.current.fingerprint !== fingerprint)
      attempt.current = { fingerprint, key: crypto.randomUUID() };
    try {
      const result = await api<T>(path, method, data, attempt.current.key);
      attempt.current = { fingerprint: "", key: "" };
      success(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : "تعذر حفظ العملية");
    } finally {
      pending.current = false;
      setBusy(false);
    }
  }
  return { run, busy, error, setError };
}

export function cents(text: string): bigint | null {
  if (!/^\d+(\.\d{0,2})?$/.test(text)) return null;
  const [a, b = ""] = text.split(".");
  return BigInt(a) * 100n + BigInt(b.padEnd(2, "0"));
}
export function decimal(value: bigint): string {
  const abs = value < 0n ? -value : value;
  return (
    (value < 0n ? "-" : "") +
    abs / 100n +
    "." +
    (abs % 100n).toString().padStart(2, "0")
  );
}
export function money(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === "") return "—";
  const [a, b = "00"] = String(value).split(".");
  return a.replace(/\B(?=(\d{3})+(?!\d))/g, ",") + "." + b.padEnd(2, "0");
}
export function when(
  value: string | null | undefined,
  timezone = "Asia/Riyadh",
): string {
  if (!value) return "—";
  return new Intl.DateTimeFormat("ar-SA-u-ca-gregory-nu-latn", {
    dateStyle: "medium",
    ...(value.includes("T")
      ? { timeStyle: "short" as const, timeZone: timezone }
      : { timeZone: "UTC" }),
  }).format(new Date(value.includes("T") ? value : value + "T00:00:00Z"));
}
export const methodLabel: Record<string, string> = {
  cash: "نقدًا",
  card: "شبكة / بطاقة",
  bank: "تحويل بنكي",
};
export const kindLabel: Record<string, string> = {
  expense: "مصروف نقدي",
  withdrawal: "سحب نقدي",
  deposit: "إيداع نقدي",
  refund: "مرتجع نقدي",
  purchase: "مشتريات",
  collection: "تحصيل دين",
  debt: "دين عميل",
  credit: "بيع آجل",
  opening: "رصيد عميل افتتاحي",
};
