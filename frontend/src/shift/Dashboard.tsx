import {useEffect,useMemo,useState} from 'react';
import {BarChart3,CheckCheck,Download,Eye,ShieldCheck,TrendingDown,TrendingUp} from 'lucide-react';
import {download,request,useAction,useLoad} from './api';
import {useApp} from './context';
import type {Report,Shift,User} from './types';
import {Amount,cents,dayLabel,Empty,ErrorBox,Form,Heading,Loading,Modal,Panel,Pill,monthLabel} from './ui';

type TrendPoint={month:string;label:string;total_sales:string;shortage:string|null;surplus:string|null;net_difference:string|null;cash_count_sessions:number};

// Floating point is used only for bar widths; every displayed money value is
// the exact decimal string computed by the backend.
const plotMoney=(value:string|null)=>Number(cents(value))/100;
const validMonth=(value:string)=>/^[0-9]{4}-(0[1-9]|1[0-2])$/.test(value)&&!value.startsWith('0000-')&&value!=='9999-12';
function shortMonthLabel(value:string){
  const date=new Date(value+'-01T12:00:00Z');
  return new Intl.DateTimeFormat('ar-YE-u-ca-gregory-nu-latn',{month:'short',year:'2-digit',timeZone:'UTC'}).format(date);
}
function useMonthlyAnalytics(month:string,revision:number,employeeId:string){
  const [data,setData]=useState<TrendPoint[]|null>(null),[error,setError]=useState(''),[loading,setLoading]=useState(true);
  useEffect(()=>{
    let active=true;
    setData(null);setError('');setLoading(validMonth(month));
    if(!validMonth(month)){setError('حدد شهرًا صحيحًا لعرض التحليل.');return()=>{active=false}}
    request<{months:Omit<TrendPoint,'label'>[]}>('/reports/analytics?month='+month+(employeeId==='all'?'':'&employee_id='+employeeId))
      .then(result=>{if(active)setData(result.months.map(row=>({...row,label:shortMonthLabel(row.month)})))})
      .catch(e=>{if(active)setError((e as Error).message)})
      .finally(()=>{if(active)setLoading(false)});
    return()=>{active=false};
  },[month,revision,employeeId]);
  return{data,error,loading};
}

function ShiftRows({records,onConfirm}:{records:Shift[];onConfirm?:(shift:Shift)=>void}){
  const {navigate}=useApp();
  if(!records.length)return <Empty>لا توجد ورديات تطابق الفترة المحددة.</Empty>;
  return <>
    <div className="table-wrap shift-desktop"><table><thead><tr><th>الوردية وتاريخها</th><th>الموظف</th><th>إجمالي المبيعات</th><th>الإيداع</th><th>الحالة</th><th>إجراء</th></tr></thead><tbody>
      {records.map(s=><tr key={s.id}><td><button type="button" className="text-button" onClick={()=>navigate('detail',s.id)}>#{s.id} · {dayLabel(s.business_date)}</button><small>سند #{s.deposit_number}</small></td><td>{s.employee}</td><td><Amount value={s.totals.total_sales}/></td><td><Amount value={s.totals.deposit_amount}/></td><td><Pill tone={s.approved?'balanced':'pending'}>{s.approved?'معتمدة':'بانتظار الاعتماد'}</Pill></td><td><div className="actions"><button type="button" className="secondary" onClick={()=>navigate('detail',s.id)}><Eye size={16}/> عرض</button>{s.legacy_accounting&&!s.approved&&<small>سجل محاسبي قديم يحتاج مراجعة</small>}{onConfirm&&!s.approved&&!s.legacy_accounting&&<button type="button" className="primary" onClick={()=>onConfirm(s)}><CheckCheck size={17}/> مطابقة</button>}</div></td></tr>)}
    </tbody></table></div>
    <div className="shift-cards">{records.map(s=><article className="shift-card" key={s.id}><header><h3>الوردية #{s.id}</h3><Pill tone={s.approved?'balanced':'pending'}>{s.approved?'معتمدة':'بانتظار الاعتماد'}</Pill></header><small>{dayLabel(s.business_date)} · {s.employee}</small><div className="mini-row"><span>المبيعات الإجمالية</span><Amount value={s.totals.total_sales}/></div><div className="mini-row"><span>الإيداع</span><Amount value={s.totals.deposit_amount}/></div><div className="actions"><button type="button" className="secondary" onClick={()=>navigate('detail',s.id)}><Eye size={17}/> التفاصيل</button>{s.legacy_accounting&&!s.approved&&<small>سجل محاسبي قديم يحتاج مراجعة</small>}{onConfirm&&!s.approved&&!s.legacy_accounting&&<button type="button" className="primary" onClick={()=>onConfirm(s)}><CheckCheck size={17}/> مطابقة</button>}</div></article>)}</div>
  </>;
}

function ConfirmDialog({shift,onClose,onSaved}:{shift:Shift;onClose:()=>void;onSaved:()=>void}){
  const [checked,setChecked]=useState(false),[note,setNote]=useState(''),action=useAction();
  function confirm(){void action.run('/shifts/'+shift.id+'/confirm','POST',{expected_version:shift.current_version,confirmed:true,note},()=>{onSaved();onClose()})}
  return <Modal title={'تأكيد مطابقة الوردية #'+shift.id} onClose={onClose}>
    <p>هل راجعت بيانات الوردية والمرفقات والإيداع وتريد اعتمادها إداريًا؟</p>
    <div className="summary-grid"><div className="mini-row"><span>الموظف</span><b>{shift.employee}</b></div><div className="mini-row"><span>إجمالي المبيعات</span><Amount value={shift.totals.total_sales}/></div><div className="mini-row"><span>قيمة الإيداع</span><Amount value={shift.totals.deposit_amount}/></div><div className="mini-row"><span>رقم السند</span><b>{shift.deposit_number}</b></div></div>
    <div className="alert info"><ShieldCheck size={18}/><span>هذا اعتماد إداري للبيانات المسجلة، وليس إثباتًا لتوازن الصندوق؛ لا تُحسب قيمة العجز أو الفائض لعدم إدخال مبيعات الشبكة والنقد المتبقي.</span></div>
    <Form onSubmit={confirm}><fieldset disabled={action.busy}>
      <label className="field"><span>ملاحظة المدير (اختيارية)</span><textarea rows={2} maxLength={1000} value={note} onChange={e=>setNote(e.target.value)}/></label>
      <label className="check-label"><input type="checkbox" required checked={checked} onChange={e=>setChecked(e.target.checked)}/> راجعت المعلومات وأؤكد اعتماد هذه الوردية.</label>
      <ErrorBox message={action.error}/>
      <div className="modal-actions"><button type="submit" className="primary" disabled={!checked||action.busy}><CheckCheck size={18}/> {action.busy?'جار الاعتماد…':'تأكيد الاعتماد'}</button><button type="button" className="secondary" onClick={onClose}>إلغاء</button></div>
    </fieldset></Form>
  </Modal>;
}

function SalesChart({rows}:{rows:TrendPoint[]}){
  const largest=rows.reduce((best,row)=>cents(row.total_sales)>cents(best)?row.total_sales:best,'0.00');
  const smallest=rows.reduce((best,row)=>cents(row.total_sales)<cents(best)?row.total_sales:best,rows[0]?.total_sales||'0.00');
  const scale=Math.max(plotMoney(largest),1);
  return <Panel title="إجمالي المبيعات الشهرية" subtitle="آخر 6 أشهر" action={<BarChart3 size={19}/> }>
    <div className="chart-unit">القيم بالريال اليمني</div>
    <div className="chart">{rows.map(row=><div className="chart-row" key={row.month}><span>{row.label}</span><div className="chart-track"><i style={{width:(plotMoney(row.total_sales)/scale*100).toFixed(1)+'%'}}/></div><Amount value={row.total_sales}/></div>)}</div>
    <div className="chart-axis"><span>أقل قيمة: <Amount value={smallest}/></span><span>أعلى قيمة: <Amount value={largest}/></span></div>
  </Panel>;
}
function VarianceChart({rows}:{rows:TrendPoint[]}){
  const max=Math.max(...rows.map(row=>Math.max(plotMoney(row.shortage),plotMoney(row.surplus))),1);
  return <Panel title="إجمالي العجز والفائض" subtitle="جرد نقدي تاريخي معتمد فقط" action={<TrendingDown size={19}/> }>
    <div className="chart-legend"><span><i className="shortage"/> العجز</span><span><i/> الفائض</span></div>
    <div className="chart">{rows.map(row=><div className="chart-row variance-row" key={row.month}><span>{row.label}</span><div className="diverge"><span><i style={{width:(plotMoney(row.shortage)/max*100).toFixed(1)+'%'}}/></span><span><i style={{width:(plotMoney(row.surplus)/max*100).toFixed(1)+'%'}}/></span></div><div className="chart-diff-values">{row.cash_count_sessions?<><span className="number negative">−<Amount value={row.shortage}/></span><span className="number positive">+<Amount value={row.surplus}/></span></>:<small>لا يوجد جرد</small>}</div></div>)}</div>
  </Panel>;
}
function DifferenceChart({rows}:{rows:TrendPoint[]}){
  const max=Math.max(...rows.map(row=>Math.abs(plotMoney(row.net_difference))),1);
  return <Panel title="الفرق بين العجز والفائض" subtitle="الفائض ناقص العجز التاريخيين" action={<TrendingUp size={19}/> }>
    <div className="chart">{rows.map(row=><div className="chart-row" key={row.month}><span>{row.label}</span><div className="chart-track net-track"><i className={cents(row.net_difference)>=0n?'net-positive':'net-negative'} style={{width:(Math.abs(plotMoney(row.net_difference))/max*100).toFixed(1)+'%'}}/></div>{row.cash_count_sessions?<Amount value={row.net_difference}/>:<small>لا يوجد جرد</small>}</div>)}</div>
    <div className="chart-legend"><span><i className="shortage"/> قيمة سالبة = العجز أعلى</span><span><i/> قيمة موجبة = الفائض أعلى</span></div>
  </Panel>;
}

export default function Dashboard({kind}:{kind:'dashboard'|'archive'}){
  const {me,revision,navigate,notify}=useApp();
  const [month,setMonth]=useState(me.today.slice(0,7));
  const [employeeId,setEmployeeId]=useState('all');
  const users=useLoad<User[]>('/users',revision);
  const employeeFilter=employeeId==='all'?'':'&employee_id='+employeeId;
  const reports=useLoad<Report>(validMonth(month)?'/reports?month='+month+employeeFilter:null,revision);
  const analytics=useMonthlyAnalytics(month,revision,employeeId);
  const data=reports.data;
  const selectedTrend=useMemo(()=>analytics.data?.find(row=>row.month===month)||null,[analytics.data,month]);
  async function exportFile(ext:'pdf'|'csv'){
    try{await download('/reports/export.'+ext+'?month='+month+employeeFilter,'bin-doul-'+month+'.'+ext)}catch(e){notify((e as Error).message)}
  }
  return <>
    <Heading eyebrow={kind==='archive'?'الأرشيف':'الإدارة'} title={kind==='archive'?'الأرشيف الشهري':'نظرة عامة على الورديات'} description="مبيعات شهرية لكل موظف ورسوم للعجز والفائض التاريخيين فقط؛ الاعتمادات الجديدة لا تُحسب لها فروقات نقدية." action={<div className="actions"><button type="button" className="secondary" disabled={!data} onClick={()=>void exportFile('pdf')}><Download size={17}/> PDF</button><button type="button" className="secondary" disabled={!data} onClick={()=>void exportFile('csv')}>CSV</button></div>}/>
    <Panel title="اختر الفترة والموظف"><div className="fields"><label className="field"><span>الشهر</span><input type="month" aria-label="شهر الأرشيف" value={month} onChange={e=>setMonth(e.target.value)}/></label><label className="field"><span>الموظف</span><select aria-label="فلترة حسب الموظف" value={employeeId} onChange={e=>setEmployeeId(e.target.value)}><option value="all">جميع الموظفين</option>{users.data?.map(u=><option value={String(u.id)} key={u.id}>{u.full_name}</option>)}</select></label></div><small className="field-hint">تُحدّث الإحصاءات والرسوم حسب الموظف والشهر المحددين.</small></Panel>
    <ErrorBox message={reports.error||analytics.error||users.error}/>{(reports.loading||analytics.loading)&&<Loading/>}
    {data&&<>
      <div className="stats">
        <article className="stat featured"><small>إجمالي المبيعات</small><strong><Amount value={data.totals.total_sales}/></strong><small>{monthLabel(month)}</small></article>
        <article className="stat"><small>الورديات المستلمة</small><strong>{data.totals.count}</strong></article>
        <article className="stat"><small>الورديات المعتمدة</small><strong>{data.totals.approved}</strong></article>
        <article className="stat"><small>بانتظار اعتماد المدير</small><strong>{data.totals.pending}</strong></article>
      </div>
      {selectedTrend&&<div className="stats analytics-stats"><article className="stat"><small>العجز التاريخي للشهر</small><strong className="negative"><Amount value={selectedTrend.shortage}/></strong><p>{selectedTrend.cash_count_sessions?'من لقطات الجرد المعتمدة':'لم يسجل جرد نقدي في هذا الشهر'}</p></article><article className="stat"><small>الفائض التاريخي للشهر</small><strong className="positive"><Amount value={selectedTrend.surplus}/></strong><p>{selectedTrend.cash_count_sessions?'من لقطات الجرد المعتمدة':'لم يسجل جرد نقدي في هذا الشهر'}</p></article><article className="stat"><small>الفرق بين العجز والفائض</small><strong className={selectedTrend.net_difference===null?'':cents(selectedTrend.net_difference)>0n?'positive':cents(selectedTrend.net_difference)<0n?'negative':''}><Amount value={selectedTrend.net_difference}/></strong><p>{selectedTrend.net_difference===null?'الجرد غير متوفر لحساب الفرق':cents(selectedTrend.net_difference)>0n?'الفائض التاريخي أعلى':cents(selectedTrend.net_difference)<0n?'العجز التاريخي أعلى':'العجز والفائض التاريخيان متساويان'}</p></article></div>}
      {analytics.data&&<div className="dashboard-grid"><SalesChart rows={analytics.data}/><VarianceChart rows={analytics.data}/><DifferenceChart rows={analytics.data}/></div>}
      <Panel title={kind==='archive'?'ورديات هذا الشهر':'الورديات الأخيرة'} action={kind==='dashboard'?<button type="button" className="text-button" onClick={()=>navigate('shifts')}>فتح سجل الورديات</button>:undefined}><ShiftRows records={kind==='dashboard'?data.shifts.slice(0,7):data.shifts}/></Panel>
      <small className="report-time">تنبيه: العجز والفائض في هذه الرسوم يقتصران على القيم المحاسبية القديمة المحفوظة. نموذج التسليم الحالي لا يحسب فروقات نقدية للورديات الجديدة دون بيانات الشبكة والجرد؛ تظهر علامة — عند غياب الجرد، ولا تعني توازن الصندوق.</small>
    </>}
  </>;
}

export function ShiftHistory(){
  const {revision,me,refresh,notify}=useApp();
  const [month,setMonth]=useState(me.today.slice(0,7)),[all,setAll]=useState(true),[status,setStatus]=useState('all'),[q,setQ]=useState(''),[confirming,setConfirming]=useState<Shift|null>(null);
  const query=new URLSearchParams({status,q});if(!all)query.set('month',month);
  const {data,error,loading}=useLoad<Shift[]>('/shifts?'+query.toString(),revision);
  return <>
    <Heading eyebrow="إدارة الورديات" title="سجل الورديات" description="اضغط مطابقة بجانب الوردية، ثم راجع البيانات واضغط تأكيد الاعتماد. لا حاجة لإدخال مبيعات الشبكة أو النقد المتبقي."/>
    <Panel title="البحث والتصفية"><div className="filter-fields history-filters">
      <label>البحث<input aria-label="البحث في الورديات" placeholder="الموظف أو رقم الوردية أو السند" value={q} onChange={e=>setQ(e.target.value)}/></label>
      <label>الشهر<input type="month" aria-label="شهر سجل الورديات" value={month} disabled={all} onChange={e=>setMonth(e.target.value)}/></label>
      <label>الحالة<select aria-label="حالة الاعتماد" value={status} onChange={e=>setStatus(e.target.value)}><option value="all">كل الحالات</option><option value="pending">بانتظار الاعتماد</option><option value="confirmed">معتمدة</option></select></label>
      <label className="check-label"><input type="checkbox" checked={all} onChange={e=>setAll(e.target.checked)}/> كل الفترات</label>
    </div><ErrorBox message={error}/>{loading?<Loading/>:data&&<ShiftRows records={data} onConfirm={setConfirming}/>}</Panel>
    {confirming&&<ConfirmDialog shift={confirming} onClose={()=>setConfirming(null)} onSaved={()=>{refresh();notify('تم اعتماد الوردية إداريًا، دون حساب فرق النقد.')}}/>}
  </>;
}
