import {useEffect,useState} from 'react';
import {ArrowRight,ClipboardList,Download,Eye,History,LockKeyhole,Save,SquarePen} from 'lucide-react';
import {download,useAction,useLoad} from './api';
import {useApp} from './context';
import EntryForm,{emptyDraft,toInput} from './EntryForm';
import type {Detail,Draft,Entry,Kind} from './types';
import {Amount,dayLabel,Empty,ErrorBox,Form,Heading,Loading,Panel,Pill,purposeLabel} from './ui';

function EntryRows({entries}:{entries:Entry[]}){
  if(!entries.length)return <Empty>لا توجد عمليات في هذا القسم.</Empty>;
  return <div className="invoice-items">{entries.map(entry=><article key={entry.id} className="invoice-item">
    <header><h3>{entry.name}</h3><Amount value={entry.amount}/></header>
    <div className="invoice-item-details">
      {entry.invoice_number&&<div><span>رقم الفاتورة</span><b dir="ltr">{entry.invoice_number}</b></div>}
      {entry.kind==='off_device'&&<><div><span>رقم الصنف</span><b>{entry.item_code}</b></div><div><span>العدد</span><b>{entry.quantity}</b></div></>}
      {entry.kind==='bank'&&<><div><span>نوع التحويل</span><b>{entry.purpose?purposeLabel[entry.purpose]: 'تحويل بنكي'}</b></div><div><span>رقم الحوالة</span><b>{entry.reference}</b></div></>}
    </div>
    {entry.description&&<p className="preserve-text">{entry.description}</p>}
    {entry.attachment_id&&<div className="actions"><a className="secondary" href={'/api/attachments/'+entry.attachment_id} download><Download size={16}/> {entry.attachment?.filename||'تحميل المرفق'}</a></div>}
  </article>)}</div>;
}

export default function ShiftDetail({id}:{id:number}){
  const {revision,refresh,navigate,notify}=useApp();
  const [version,setVersion]=useState<number|null>(null),[tab,setTab]=useState<'details'|'history'>('details'),[editing,setEditing]=useState(false),[draft,setDraft]=useState<Draft>(()=>emptyDraft('')),[reason,setReason]=useState('');
  const action=useAction();
  useEffect(()=>{setVersion(null);setTab('details');setEditing(false);setDraft(emptyDraft(''))},[id]);
  const {data,error,loading}=useLoad<Detail>('/shifts/'+id+(version?'?version='+version:''),revision);
  if(loading)return <Loading/>;if(error)return <ErrorBox message={error}/>;if(!data)return null;
  const historic=data.version.number!==data.shift.current_version;
  const oldLedger=data.entries.some(e=>e.kind==='debt'||(e.kind==='bank'&&e.purpose==='customer_account'));
  const oldCashApproval=data.has_legacy_cash;
  const canEdit=!historic&&!oldLedger&&!oldCashApproval;
  function startEdit(){
    const rows=data!.entries.filter((e):e is Entry & {kind:Kind}=>e.kind!=='debt').map(e=>({...e,quantity:e.quantity===null?'':String(e.quantity),invoice_total:'',purpose:e.kind==='bank'?'current_shift' as const:null,attachment_name:e.attachment?.filename}));
    setDraft({business_date:data!.version.business_date,deposit_date:data!.version.deposit_date,deposit_number:data!.version.deposit_number,deposit_amount:data!.version.deposit_amount,device_sales:data!.version.device_sales,notes:data!.version.notes,entries:rows});
    setReason('');setEditing(true);
  }
  function saveEdit(){void action.run('/shifts/'+id,'PUT',{...toInput(draft),expected_version:data!.shift.current_version,reason},()=>{setEditing(false);setVersion(null);refresh();notify('تم حفظ نسخة تصحيح جديدة. اعتمدها من سجل الورديات.')})}
  return <>
    <Heading eyebrow={editing?'تصحيح إداري موثق':'عرض وردية محفوظة'} title={'الوردية #'+id} description={data.employee+' · '+dayLabel(data.version.business_date)} action={<div className="actions"><button type="button" className="secondary" onClick={()=>navigate('shifts')}><ArrowRight size={16}/> سجل الورديات</button>{!editing&&canEdit&&<button type="button" className="secondary" onClick={startEdit}><SquarePen size={16}/> تعديل</button>}{!editing&&<button type="button" className="secondary" onClick={()=>void download('/shifts/'+id+'/export.pdf','shift-'+id+'.pdf').catch(e=>notify(e.message))}><Download size={16}/> PDF</button>}</div>}/>
    <div className="meta"><span>تاريخ الصندوق: {dayLabel(data.version.business_date)}</span><span>تاريخ السند: {dayLabel(data.version.deposit_date)}</span><span>رقم السند: <b>{data.version.deposit_number}</b></span><Pill tone={data.approved?'balanced':'pending'}>{data.approved?'معتمدة':'بانتظار اعتماد المدير'}</Pill></div>
    {historic&&<div className="alert info"><History size={18}/> هذه نسخة قديمة للقراءة فقط. <button type="button" className="text-button" onClick={()=>{setVersion(null);setTab('details')}}>آخر نسخة</button></div>}
    {!canEdit&&!historic&&<div className="alert info"><LockKeyhole size={17}/> هذه الوردية تحتوي بيانات محاسبية قديمة؛ عرضها محفوظ، ولا يمكن تعديلها بالنموذج المبسّط دون مراجعة محاسبية.</div>}
    {editing?<Form onSubmit={saveEdit}><fieldset disabled={action.busy}><EntryForm draft={draft} setDraft={setDraft} busy={action.busy}/><Panel title="توثيق سبب التصحيح"><label className="field"><span>سبب التصحيح *</span><textarea required minLength={3} maxLength={1000} value={reason} onChange={e=>setReason(e.target.value)} rows={2}/></label><ErrorBox message={action.error}/><div className="modal-actions"><button type="submit" className="primary" disabled={draft.entries.some(e=>e.uploading)}><Save size={17}/> حفظ التصحيح</button><button type="button" className="secondary" onClick={()=>setEditing(false)}>إلغاء</button></div></Panel></fieldset></Form>:<>
      <div className="tabs" role="tablist"><button type="button" role="tab" aria-selected={tab==='details'} onClick={()=>setTab('details')}><ClipboardList size={16}/> التفاصيل</button><button type="button" role="tab" aria-selected={tab==='history'} onClick={()=>setTab('history')}><History size={16}/> سجل النسخ</button></div>
      {tab==='history'?<Panel title="سجل التعديلات"><div className="timeline">{data.versions.map(v=><article key={v.number}><h3>نسخة {v.number}</h3><small>{dayLabel(v.created_at)}</small><p>{v.reason}</p><button type="button" className="text-button" onClick={()=>{setVersion(v.number);setTab('details')}}><Eye size={16}/> عرض النسخة</button></article>)}</div></Panel>:<div className="detail-layout"><div>
        <Panel title="ملخص الوردية"><div className="summary-grid">{[['إجمالي مبيعات الجهاز',data.version.device_sales],['مبلغ الإيداع',data.version.deposit_amount],['مبيعات خارج الجهاز',data.totals.outside_sales],['المشتريات',data.totals.purchases],['التحويلات البنكية',data.totals.shift_bank]].map(([label,value])=><div className="mini-row" key={label}><span>{label}</span><Amount value={value}/></div>)}</div></Panel>
        {(['purchase','off_device','bank'] as Kind[]).map(kind=><Panel key={kind} title={{purchase:'فواتير المشتريات',off_device:'الأصناف خارج الجهاز',bank:'التحويلات البنكية'}[kind]}><EntryRows entries={data.entries.filter(e=>e.kind===kind)}/></Panel>)}
        <Panel title="ملاحظة الموظف"><p className="preserve-text">{data.version.notes||'لا توجد ملاحظة.'}</p></Panel>
      </div><aside><Panel title="حالة مراجعة المدير"><Pill tone={data.approved?'balanced':'pending'}>{data.approved?'تم اعتماد الوردية':'بانتظار الاعتماد'}</Pill><p className="field-hint">الاعتماد الجديد إداري فقط، ولا يعني مطابقة النقد الفعلي أو احتساب العجز والفائض.</p>{data.approval&&<><small>تاريخ الاعتماد: {dayLabel(data.approval.approved_at)}</small><p>{data.approval.note||'لا توجد ملاحظة.'}</p></>}{!data.approved&&<button type="button" className="primary full-width" onClick={()=>navigate('shifts')}>الانتقال للسجل للاعتماد</button>}</Panel></aside></div>}
    </>}
  </>;
}
