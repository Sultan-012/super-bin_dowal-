import {useRef,useState} from 'react';
import {CheckCheck,LockKeyhole,LogOut,Send,ShieldCheck,Wallet,LoaderCircle,RefreshCw,Moon,Sun} from 'lucide-react';
import {APIError,request} from './api';
import EntryForm,{emptyDraft,toInput} from './EntryForm';
import {useApp} from './context';
import type {Me} from './types';
import {dayLabel,ErrorBox,Form,Heading,Modal,Pill} from './ui';

function ThemeButton(){
  const {theme,toggleTheme}=useApp();
  const Icon=theme==='dark'?Sun:Moon;
  return <button type="button" className="secondary theme-toggle" onClick={toggleTheme} aria-label={theme==='dark'?'الوضع النهاري':'الوضع الليلي'}><Icon size={18}/><span>{theme==='dark'?'الوضع النهاري':'الوضع الليلي'}</span></button>;
}

export default function Employee({me,onLogout}:{me:Me;onLogout:()=>void}){
  const {theme}=useApp();
  const [draft,setDraft]=useState(()=>emptyDraft(me.today)),[hasSubmitted,setHasSubmitted]=useState(me.submitted_today),[mode,setMode]=useState<'form'|'sending'|'done'|'uncertain'>('form'),[confirm,setConfirm]=useState(false),[error,setError]=useState('');
  const pending=useRef<{data:ReturnType<typeof toInput>;key:string}|null>(null),sending=useRef(false);
  async function deliver(){
    if(sending.current||!pending.current)return;sending.current=true;setMode('sending');setConfirm(false);setError('');
    try{await request('/shifts','POST',pending.current.data,pending.current.key);pending.current=null;setDraft(emptyDraft(me.today));setHasSubmitted(true);setMode('done')}
    catch(e){const err=e as APIError;setError(err.message);setMode([400,409,422].includes(err.status)?'form':'uncertain')}
    finally{sending.current=false}
  }
  function prepare(){if(draft.entries.some(e=>e.uploading)){setError('انتظر اكتمال رفع جميع المرفقات.');return}setError('');pending.current={data:toInput(draft),key:crypto.randomUUID()};setConfirm(true)}
  function startNextShift(){if(sending.current||mode!=='done')return;pending.current=null;setDraft(emptyDraft(me.today));setError('');setConfirm(false);setMode('form')}
  return <div className="employee-app"><header className="employee-top"><div className="brand"><span className="brand-icon"><Wallet size={24}/></span><div><b>{me.store.store_name}</b><small>إغلاق الوردية المالية</small></div></div><div className="person"><ThemeButton/><span>{me.user.full_name}</span><Pill>{theme==='dark'?'الوضع الليلي':'الوضع النهاري'}</Pill><Pill>موظف · إدخال فقط</Pill><button type="button" className="icon-button" onClick={onLogout} aria-label="تسجيل الخروج"><LogOut size={19}/></button></div></header>
  {mode==='form'?<main className="employee-content"><Heading eyebrow="تسليم الوردية" title="إغلاقك اليومي، بخطوات واضحة" description="أدخل جميع البيانات المطلوبة ثم سلّمها للمدير." action={<Pill>مسودة غير مرسلة</Pill>}/><div className="meta"><span>{dayLabel(draft.business_date||me.today)}</span><span>{me.user.full_name}</span><Pill>ريال يمني</Pill></div><Form onSubmit={prepare}>{hasSubmitted&&<div className="alert info"><ShieldCheck size={18}/><span>سبق تسليم وردية من حسابك اليوم. إذا لم تتأكد من نتيجة طلب سابق، راجع المدير قبل إنشاء وردية أخرى. استخدم رقم سند إيداع جديدًا لكل وردية مستقلة.</span></div>}<fieldset disabled={draft.entries.some(e=>e.uploading)}><EntryForm draft={draft} setDraft={setDraft}/></fieldset><div className="alert info"><LockKeyhole size={20}/><span>بعد التسليم تُخفى البيانات. مراجعة الوردية واعتمادها متاحان للمدير فقط، ولا يُحسب عجز أو فائض دون جرد فعلي.</span></div><ErrorBox message={error}/><div className="form-footer"><span><ShieldCheck size={17}/> إدخال وتسليم فقط</span><button type="submit" className="primary" disabled={draft.entries.some(e=>e.uploading)}><Send size={18}/> تأكيد وتسليم الوردية</button></div></Form></main>:<main className="employee-content"><section className="submission-state" role="status"><span className="success-icon">{mode==='sending'?<LoaderCircle className="spin" size={30}/>:mode==='done'?<CheckCheck size={32}/>:<ShieldCheck size={30}/>}</span><h1>{mode==='done'?'تم تسليم الوردية':mode==='sending'?'جار تسليم الوردية…':'لم يصل تأكيد التسليم'}</h1><p>{mode==='done'?'وصلت الوردية للمدير. يمكنك بدء وردية جديدة مستقلة، حتى في التاريخ نفسه.':mode==='sending'?'انتظر التأكيد دون إغلاق الصفحة.':'أعد التحقق بالطلب نفسه دون إدخال البيانات مرة أخرى، أو راجع المدير.'}</p>{mode==='uncertain'&&<><ErrorBox message={error}/><button type="button" className="primary" onClick={()=>void deliver()}><RefreshCw size={17}/> إعادة التحقق من التسليم</button></>}{mode==='done'&&<button type="button" className="primary" onClick={startNextShift}><RefreshCw size={17}/> بدء وردية جديدة</button>}<button type="button" className="secondary" disabled={mode==='sending'} onClick={onLogout}><LogOut size={17}/> تسجيل الخروج</button></section></main>}
  {confirm&&<Modal title="تأكيد تسليم الوردية" onClose={()=>setConfirm(false)}><p>بعد الإرسال لا يمكنك مشاهدة البيانات أو تعديلها. هل أكملت بيانات الوردية والعمليات؟</p><div className="modal-actions"><button type="button" className="primary" onClick={()=>void deliver()}><Send size={17}/> تسليم الوردية الآن</button><button type="button" className="secondary" onClick={()=>setConfirm(false)}>العودة للمسودة</button></div></Modal>}
  <footer className="footer"><span>{me.store.store_name}</span><span>ريال يمني · {me.store.timezone}</span></footer></div>;
}
