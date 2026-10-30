import { StrictMode, useCallback, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Banknote,
  CalendarCheck2,
  ChartColumn,
  CheckCircle2,
  ChevronLeft,
  Eye,
  EyeOff,
  History,
  LayoutDashboard,
  LogOut,
  Menu,
  Settings,
  ShieldCheck,
  Users,
  Wallet,
  WalletCards,
  X,
} from "lucide-react";
import { api, useMutation, when } from "./api";
import { Context } from "./context";
import { ErrorBox, Field, Form, Loading } from "./components";
import Dashboard from "./Dashboard";
import Daily from "./Daily";
import HistoryPage from "./History";
import Customers from "./Customers";
import Movements from "./Movements";
import Reports from "./Reports";
import SettingsPage from "./Settings";
import type { Me, Page } from "./types";
import "./styles.css";

const nav: { id: Page; label: string; icon: typeof Wallet }[] = [
  { id: "dashboard", label: "لوحة التحكم", icon: LayoutDashboard },
  { id: "daily", label: "الإدخال اليومي", icon: CalendarCheck2 },
  { id: "history", label: "سجل الجلسات", icon: History },
  { id: "customers", label: "العملاء والديون", icon: Users },
  { id: "movements", label: "المشتريات والحركات", icon: WalletCards },
  { id: "reports", label: "التقارير", icon: ChartColumn },
  { id: "settings", label: "الإعدادات والمستخدمون", icon: Settings },
];
function getPage(): Page {
  const id = location.hash.slice(1).split("?")[0];
  return nav.some((n) => n.id === id) ? (id as Page) : "dashboard";
}

function App() {
  const [me, setMe] = useState<Me | null>(null),
    [loading, setLoading] = useState(true),
    [bootError, setBootError] = useState(""),
    [revision, setRevision] = useState(0),
    [page, setPage] = useState<Page>(getPage),
    [sid, setSid] = useState<number | null>(null),
    [mobile, setMobile] = useState(false),
    [toast, setToast] = useState(""),
    [logoutError, setLogoutError] = useState("");
  useEffect(() => {
    api<Me>("/auth/me")
      .then(setMe)
      .catch((e) => {
        if (e.status !== 401) setBootError(e.message);
      })
      .finally(() => setLoading(false));
    const expired = () => setMe(null);
    window.addEventListener("session-expired", expired);
    return () => window.removeEventListener("session-expired", expired);
  }, []);
  useEffect(() => {
    const change = () => {
      setPage(getPage());
      const n = new URLSearchParams(location.hash.split("?")[1]).get("session");
      setSid(n && /^\d+$/.test(n) ? Number(n) : null);
      setMobile(false);
      window.scrollTo(0, 0);
    };
    window.addEventListener("hashchange", change);
    change();
    return () => window.removeEventListener("hashchange", change);
  }, []);
  useEffect(() => {
    if (toast) {
      const timer = setTimeout(() => setToast(""), 5000);
      return () => clearTimeout(timer);
    }
  }, [toast]);
  const refresh = useCallback(() => {
    setRevision((x) => x + 1);
    api<Me>("/auth/me")
      .then(setMe)
      .catch(() => {});
  }, []);
  function navigate(p: Page, sessionId?: number) {
    location.hash = p + (sessionId ? "?session=" + sessionId : "");
    setPage(p);
    setSid(sessionId || null);
    setMobile(false);
  }
  async function loggedIn() {
    try {
      setMe(await api<Me>("/auth/me"));
      setBootError("");
      setRevision((x) => x + 1);
    } catch (e) {
      setBootError((e as Error).message);
    }
  }
  async function logout() {
    try {
      await api("/auth/logout", "POST", {});
      setMe(null);
    } catch (e) {
      setLogoutError((e as Error).message);
    }
  }
  if (loading)
    return (
      <div className="boot">
        <Loading />
      </div>
    );
  if (!me) return <Login onLogin={loggedIn} bootError={bootError} />;
  const currentNav = nav.find((x) => x.id === page)!;
  return (
    <Context.Provider
      value={{ me, revision, refresh, notify: setToast, navigate }}
    >
      <div className="app-shell">
        {mobile && (
          <button
            className="nav-shade"
            onClick={() => setMobile(false)}
            aria-label="إغلاق القائمة"
          />
        )}
        <aside className={"sidebar " + (mobile ? "mobile-open" : "")}>
          <div className="brand">
            <div className="brand-mark">
              <Wallet size={25} />
            </div>
            <div>
              <b>
                الصندوق<span> / </span>
              </b>
              <small>
                نظام إدارة المبيعات
                <br />
                ومطابقة الصندوق
              </small>
            </div>
            <button
              className="icon-button mobile-only"
              onClick={() => setMobile(false)}
              aria-label="إغلاق القائمة"
            >
              <X size={19} />
            </button>
          </div>
          <div className="store-switch">
            <div className="store-icon">
              <WalletCards size={20} />
            </div>
            <div>
              <strong>{me.settings.store_name}</strong>
              <small>متجر واحد · صندوق واحد</small>
            </div>
            <span className="live-dot" />
          </div>
          <div className="nav-section-label">مساحة العمل</div>
          <nav>
            {nav
              .filter((n) => n.id !== "reports" || me.user.role === "admin")
              .map((n) => (
                <a
                  href={"#" + n.id}
                  key={n.id}
                  className={page === n.id ? "active" : ""}
                  onClick={() => navigate(n.id)}
                >
                  <n.icon size={19} />
                  <span>
                    {n.id === "settings" && me.user.role !== "admin"
                      ? "إعدادات الحساب"
                      : n.label}
                  </span>
                  {page === n.id && (
                    <ChevronLeft className="nav-chevron" size={16} />
                  )}
                </a>
              ))}
          </nav>
          <div className="sidebar-bottom">
            <div className="trust-note">
              <ShieldCheck size={20} />
              <div>
                <b>حساباتك، بكل وضوح</b>
                <small>قرارات أدق من سجلات موثّقة</small>
              </div>
            </div>
            <div className="profile">
              <div className="avatar">{me.user.full_name.slice(0, 1)}</div>
              <div>
                <strong>{me.user.full_name}</strong>
                <small>
                  {me.user.role === "admin" ? "مدير النظام" : "موظف"}
                </small>
              </div>
              <button
                className="icon-button"
                onClick={logout}
                aria-label="تسجيل الخروج"
                title="تسجيل الخروج"
              >
                <LogOut size={18} />
              </button>
            </div>
          </div>
        </aside>
        <main className="main">
          <header className="topbar">
            <div className="breadcrumb">
              <button
                className="icon-button mobile-only"
                onClick={() => setMobile(true)}
                aria-label="فتح القائمة"
              >
                <Menu size={21} />
              </button>
              <span>مساحة العمل</span>
              <ChevronLeft size={13} />
              <b>{currentNav.label}</b>
            </div>
            <div className="topbar-date">
              <span className="live-dot" /> {when(me.today)}{" "}
              <span className="header-divider" />{" "}
              <span>{me.settings.currency}</span>
            </div>
          </header>
          <div className="page-content">
            <ErrorBox message={logoutError} />
            {page === "dashboard" ? (
              <Dashboard />
            ) : page === "daily" ? (
              <Daily selectedId={sid} />
            ) : page === "history" ? (
              <HistoryPage />
            ) : page === "customers" ? (
              <Customers />
            ) : page === "movements" ? (
              <Movements />
            ) : page === "reports" ? (
              <Reports />
            ) : (
              <SettingsPage key={me.user.role} />
            )}
          </div>
          <footer className="footer">
            <span>نظام إدارة المبيعات ومطابقة الصندوق</span>
            <span>
              العملة: {me.settings.currency} · المنطقة الزمنية:{" "}
              {me.settings.timezone}
            </span>
          </footer>
        </main>
        {toast && (
          <div className="toast" role="status">
            <CheckCircle2 size={20} />
            {toast}
            <button
              className="icon-button"
              onClick={() => setToast("")}
              aria-label="إخفاء الإشعار"
            >
              <X size={16} />
            </button>
          </div>
        )}
      </div>
    </Context.Provider>
  );
}

function Login({
  onLogin,
  bootError,
}: {
  onLogin: () => void;
  bootError: string;
}) {
  const [username, setUsername] = useState(""),
    [password, setPassword] = useState(""),
    [show, setShow] = useState(false),
    m = useMutation();
  return (
    <div className="login">
      <section className="login-story">
        <div className="brand">
          <div className="brand-mark">
            <Wallet size={26} />
          </div>
          <b>الصندوق /</b>
        </div>
        <div className="login-copy">
          <div className="eyebrow">نظام إدارة المبيعات ومطابقة الصندوق</div>
          <h1>
            يومك المالي،
            <br />
            <span>بكل وضوح.</span>
          </h1>
          <p>
            من أول عملية بيع إلى آخر جرد.
            <br />
            مبيعاتك، ديون عملائك، وحركة الصندوق في مكان واحد.
          </p>
          <div className="login-features">
            <span>
              <Banknote size={18} /> متابعة المبيعات
            </span>
            <span>
              <Users size={18} /> حسابات العملاء
            </span>
            <span>
              <ShieldCheck size={18} /> مطابقة موثّقة
            </span>
          </div>
        </div>
        <small>Daily Sales & Cash Reconciliation System</small>
      </section>
      <section className="login-form">
        <div className="login-form-inner">
          <div className="soft-icon">
            <Wallet size={29} />
          </div>
          <h2>أهلًا بعودتك</h2>
          <p>سجّل الدخول لبدء إدارة يوم العمل.</p>
          <Form
            onSubmit={() =>
              m.run("/auth/login", "POST", { username, password }, onLogin)
            }
          >
            <Field label="اسم المستخدم">
              <input
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
                autoComplete="username"
                dir="ltr"
                maxLength={64}
              />
            </Field>
            <Field label="كلمة المرور">
              <div className="password-field">
                <input
                  type={show ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  autoComplete="current-password"
                  dir="ltr"
                  maxLength={256}
                />
                <button
                  type="button"
                  className="icon-button"
                  onClick={() => setShow((x) => !x)}
                  aria-label={show ? "إخفاء كلمة المرور" : "إظهار كلمة المرور"}
                >
                  {show ? <EyeOff size={18} /> : <Eye size={18} />}
                </button>
              </div>
            </Field>
            <ErrorBox message={m.error || bootError} />
            <button className="primary stretch" disabled={m.busy}>
              {m.busy ? "جارٍ تسجيل الدخول…" : "تسجيل الدخول"}{" "}
              <ChevronLeft size={18} />
            </button>
          </Form>
          <div className="login-help">
            <ShieldCheck size={16} />
            <span>
              الوصول للمستخدمين المصرح لهم فقط.
              <br />
              للتشغيل الأول، اتبع خطوات إنشاء المدير في دليل التشغيل.
            </span>
          </div>
        </div>
      </section>
    </div>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
