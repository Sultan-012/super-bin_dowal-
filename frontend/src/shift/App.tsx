import {useCallback,useEffect,useState} from 'react';
import {BellRing,CalendarRange,ClipboardList,Eye,EyeOff,LayoutDashboard,LogOut,Menu,Moon,Settings,ShieldCheck,Sun,UserRound,Wallet,X} from 'lucide-react';
import {APIError,request,useAction} from './api';
import {Context,type ThemeMode} from './context';
import Dashboard,{ShiftHistory} from './Dashboard';
import ShiftDetail from './Detail';
import Employee from './Employee';
import {NotificationsPage,SettingsPage,UsersPage} from './Manage';
import type {Me,Page} from './types';
import {dayLabel,Empty,ErrorBox,Form,Loading} from './ui';
import './styles.css';

const nav:{page:Page;label:string;icon:typeof Wallet}[]=[
  {page:'dashboard',label:'نظرة عامة',icon:LayoutDashboard},
  {page:'shifts',label:'سجل الورديات',icon:ClipboardList},
  {page:'archive',label:'الأرشيف الشهري',icon:CalendarRange},
  {page:'notifications',label:'الإشعارات والتقارير',icon:BellRing},
  {page:'users',label:'المستخدمون',icon:UserRound},
  {page:'settings',label:'الإعدادات والتدقيق',icon:Settings},
];

function route(){
  const [path,query]=location.hash.slice(1).split('?'),params=new URLSearchParams(query);
  return{
    page:(nav.some(n=>n.page===path)||path==='detail'?path:'dashboard') as Page,
    id:params.get('id')&&/^\d+$/.test(params.get('id')!)?Number(params.get('id')):null,
  };
}

function ThemeButton({theme,toggleTheme,compact=false}:{theme:ThemeMode;toggleTheme:()=>void;compact?:boolean}){
  const next=theme==='dark'?'الوضع النهاري':'الوضع الليلي';
  const Icon=theme==='dark'?Sun:Moon;
  return <button type="button" className={compact?'icon-button theme-toggle':'secondary theme-toggle'} onClick={toggleTheme} aria-label={next} title={next}><Icon size={18}/>{!compact&&<span>{next}</span>}</button>;
}

function Login({onLogin,error,theme,toggleTheme}:{onLogin:()=>void;error:string;theme:ThemeMode;toggleTheme:()=>void}){
  const [username,setUsername]=useState(''),[password,setPassword]=useState(''),[showPassword,setShowPassword]=useState(false),action=useAction();
  return <div className="login-page"><section className="login-story"><div className="login-story-top"><div className="brand"><span className="brand-icon"><Wallet size={27}/></span><div><b>سوبر ماركت بن دول</b><small>إدارة الورديات المالية</small></div></div><ThemeButton theme={theme} toggleTheme={toggleTheme}/></div><div><span className="eyebrow">تسليم واضح، واعتماد موثق</span><h1>كل وردية.<br/>بكل تفاصيلها.</h1><p>إدخال منظم للموظف، ومراجعة دقيقة للمدير.<br/>مبيعات وفواتير وتحويلات بعملة الريال اليمني.</p></div><small><ShieldCheck size={18}/> صلاحيات محفوظة وسجل لكل مراجعة</small></section><section className="login-form"><div className="login-form-head"><span className="login-symbol"><ShieldCheck size={26}/></span><ThemeButton theme={theme} toggleTheme={toggleTheme} compact/></div><h2>أهلًا بك في بن دول</h2><p>سجّل الدخول بحساب الموظف أو المدير.</p><Form onSubmit={()=>void action.run('/auth/login','POST',{username,password},()=>{setPassword('');onLogin()})}><fieldset disabled={action.busy}><label className="field"><span>اسم المستخدم</span><input aria-label="اسم المستخدم" value={username} onChange={e=>setUsername(e.target.value)} autoComplete="username" maxLength={64} required/></label><label className="field"><span>كلمة المرور</span><div className="password-box"><input type={showPassword?'text':'password'} aria-label="كلمة المرور" value={password} onChange={e=>setPassword(e.target.value)} autoComplete="current-password" maxLength={128} required/><button type="button" className="icon-button inline-password-toggle" aria-label={showPassword?'إخفاء كلمة المرور':'إظهار كلمة المرور'} onClick={()=>setShowPassword(v=>!v)}>{showPassword?<EyeOff size={18}/>:<Eye size={18}/>}</button></div><small>{showPassword?'كلمة المرور ظاهرة الآن':'يمكنك إظهار كلمة المرور أو إخفاؤها.'}</small></label><ErrorBox message={error||action.error}/><button type="submit" className="primary full-width">{action.busy?'جار تسجيل الدخول…':'تسجيل الدخول'}</button></fieldset></Form><small>نظام تسليم الورديات واعتماد المدير</small></section></div>;
}

function Admin({me,navigate,page,id,onLogout,theme,toggleTheme}:{me:Me;navigate:(p:Page,id?:number)=>void;page:Page;id:number|null;onLogout:()=>void;theme:ThemeMode;toggleTheme:()=>void}){
  const current=nav.find(n=>n.page===(page==='detail'?'shifts':page))!;
  return <div className="app-shell"><aside className="sidebar"><div className="brand"><span className="brand-icon"><Wallet size={24}/></span><div><b>{me.store.store_name}</b><small>إغلاق الوردية المالية</small></div></div><div className="store-note">المتجر الرئيسي <small>سجل ورديات · ريال يمني</small></div><div className="nav-caption">الإدارة المالية</div><nav aria-label="أقسام المدير">{nav.map(n=><button key={n.page} type="button" onClick={()=>navigate(n.page)} aria-current={current.page===n.page?'page':undefined}><n.icon size={18}/><span>{n.label}</span></button>)}</nav><label className="mobile-nav"><span className="sr-only">قسم المدير</span><select aria-label="قسم المدير" value={current.page} onChange={e=>navigate(e.target.value as Page)}>{nav.map(n=><option value={n.page} key={n.page}>{n.label}</option>)}</select></label><div className="sidebar-user"><span className="avatar">{me.user.full_name.slice(0,1)}</span><div>{me.user.full_name}<small>مدير النظام</small></div><button type="button" aria-label="تسجيل الخروج" className="icon-button" onClick={onLogout}><LogOut size={18}/></button></div></aside><main className="admin-main"><header className="topbar"><div>الإدارة <span> / </span><b>{page==='detail'?'مشاهدة الوردية':current.label}</b></div><div className="topbar-meta"><button type="button" className="mobile-menu text-button" onClick={()=>navigate('dashboard')}><Menu size={16}/> الرئيسية</button><span>{dayLabel(me.today)}</span><ThemeButton theme={theme} toggleTheme={toggleTheme}/><button type="button" className="mobile-logout text-button" onClick={onLogout}><LogOut size={16}/> خروج</button></div></header><div className="admin-content">{page==='dashboard'||page==='archive'?<Dashboard kind={page}/>:page==='shifts'?<ShiftHistory/>:page==='notifications'?<NotificationsPage/>:page==='users'?<UsersPage/>:page==='settings'?<SettingsPage/>:id?<ShiftDetail id={id}/>:<Empty>اختر وردية من سجل الورديات.</Empty>}</div><footer className="footer"><span>{me.store.store_name} · نظام إغلاق الورديات</span><span>ريال يمني · {me.store.timezone}</span></footer></main></div>;
}

export default function App(){
  const [me,setMe]=useState<Me|null>(null),[loading,setLoading]=useState(true),[error,setError]=useState(''),[revision,setRevision]=useState(0),[locationState,setLocationState]=useState(route),[toast,setToast]=useState(''),[theme,setTheme]=useState<ThemeMode>(()=>{try{return localStorage.getItem('bin-doul-theme')==='dark'?'dark':'light'}catch{return'light'}});
  const loadMe=useCallback(async()=>{try{setMe(await request<Me>('/auth/me'));setError('')}catch(e){if((e as APIError).status!==401)setError((e as Error).message);else setMe(null)}finally{setLoading(false)}},[]);
  useEffect(()=>{void loadMe();const expire=()=>{setMe(null);setToast('');setError('انتهت الجلسة. سجّل الدخول مجددًا.')};const change=()=>{setLocationState(route());window.scrollTo(0,0)};window.addEventListener('hashchange',change);window.addEventListener('bin-doul-expired',expire);return()=>{window.removeEventListener('hashchange',change);window.removeEventListener('bin-doul-expired',expire)}},[loadMe]);
  useEffect(()=>{document.documentElement.dataset.theme=theme;document.body.dataset.theme=theme;try{localStorage.setItem('bin-doul-theme',theme)}catch{/* Theme storage is optional; transactions stay in PostgreSQL. */}},[theme]);
  useEffect(()=>{if(!toast)return;const timer=setTimeout(()=>setToast(''),6500);return()=>clearTimeout(timer)},[toast]);
  function navigate(page:Page,id?:number){location.hash=page+(id?'?id='+id:'');setLocationState({page,id:id||null});window.scrollTo(0,0)}
  const refresh=useCallback(()=>{setRevision(x=>x+1);void loadMe()},[loadMe]);
  async function logout(){try{await request('/auth/logout','POST',{},crypto.randomUUID());setMe(null);setToast('');setError('')}catch(e){setToast((e as Error).message)}}
  const toggleTheme=()=>setTheme(t=>t==='dark'?'light':'dark');
  if(loading)return <div className="boot"><Loading/></div>;
  if(!me)return <Login error={error} theme={theme} toggleTheme={toggleTheme} onLogin={()=>{navigate('dashboard');void loadMe()}}/>;
  return <><Context.Provider value={{me,revision,refresh,notify:setToast,navigate,theme,toggleTheme}}>{me.user.role==='employee'?<Employee me={me} onLogout={()=>void logout()}/>:<Admin me={me} navigate={navigate} page={locationState.page} id={locationState.id} onLogout={()=>void logout()} theme={theme} toggleTheme={toggleTheme}/>}</Context.Provider>{toast&&<div className="toast" role="status"><span>{toast}</span><button type="button" className="icon-button" aria-label="إغلاق التنبيه" onClick={()=>setToast('')}><X size={17}/></button></div>}</>;
}
