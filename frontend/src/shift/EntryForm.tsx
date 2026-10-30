import {useRef} from 'react';
import type {Dispatch,SetStateAction} from 'react';
import {FileCheck2,FileUp,Plus,Trash2} from 'lucide-react';
import {upload} from './api';
import type {Draft,EntryDraft,Kind} from './types';
import {cleanMoney,ErrorBox,Field,MoneyField,normal,Panel} from './ui';

export const emptyDraft=(today:string):Draft=>({business_date:today,deposit_date:today,deposit_number:'',deposit_amount:'',device_sales:'',notes:'',entries:[]});
export const newEntry=(kind:Kind):EntryDraft=>({line_key:crypto.randomUUID(),kind,name:'',amount:'',reference:'',description:'',item_code:'',quantity:'',invoice_number:'',invoice_total:'',purpose:kind==='bank'?'current_shift':null,attachment_id:null});
export function toInput(draft:Draft){return {...draft,deposit_amount:cleanMoney(draft.deposit_amount),device_sales:cleanMoney(draft.device_sales),entries:draft.entries.map(e=>({line_key:e.line_key,kind:e.kind,name:e.name.trim(),amount:cleanMoney(e.amount),reference:e.kind==='bank'?e.reference.trim():'',description:e.kind==='purchase'?e.description.trim():'',item_code:e.kind==='off_device'?e.item_code.trim():'',quantity:e.kind==='off_device'?Number(normal(e.quantity)):null,invoice_number:e.kind==='purchase'||e.kind==='bank'?e.invoice_number.trim():'',invoice_total:null,purpose:e.kind==='bank'?'current_shift':null,attachment_id:e.kind==='purchase'||e.kind==='bank'?e.attachment_id:null}))}}

function AttachmentField({entry,patch,disabled}:{entry:EntryDraft;patch:(value:Partial<EntryDraft>)=>void;disabled:boolean}){
  const keys=useRef(new Map<string,string>());
  async function choose(file:File|undefined){if(!file)return;if(file.size>5*1024*1024){patch({upload_error:'حجم المرفق يجب ألا يتجاوز 5 ميجابايت.'});return}patch({uploading:true,upload_error:''});try{const hash=await crypto.subtle.digest('SHA-256',await file.arrayBuffer());const fingerprint=file.name+Array.from(new Uint8Array(hash)).map(x=>x.toString(16).padStart(2,'0')).join('');let key=keys.current.get(fingerprint);if(!key){key=crypto.randomUUID();keys.current.set(fingerprint,key)}const result=await upload(file,key);patch({attachment_id:result.id,attachment_name:result.filename,uploading:false})}catch(error){patch({upload_error:(error as Error).message,uploading:false})}}
  return <div className="field full"><span>إرفاق ملف (اختياري)</span><div className="upload-box">{entry.attachment_id?<FileCheck2 size={21}/>:<FileUp size={21}/>}<div><label className="upload-label">{entry.uploading?'جار رفع الملف…':entry.attachment_name||'اختر صورة أو PDF للمستند'}<input type="file" aria-label="مرفق العملية (اختياري)" accept="application/pdf,image/png,image/jpeg" disabled={disabled||entry.uploading} onChange={e=>{const file=e.target.files?.[0];e.target.value='';void choose(file)}}/></label><small>PDF / PNG / JPG · حد أقصى 5 ميجابايت</small></div>{entry.attachment_id&&<button type="button" className="text-button danger-text" disabled={disabled||entry.uploading} onClick={()=>patch({attachment_id:null,attachment_name:undefined,upload_error:''})}>إزالة المرفق</button>}</div><ErrorBox message={entry.upload_error||''}/></div>
}

export default function EntryForm({draft,setDraft,busy=false}:{draft:Draft;setDraft:Dispatch<SetStateAction<Draft>>;busy?:boolean}){
  const update=(key:keyof Draft,value:string)=>setDraft(old=>({...old,[key]:value}));
  const patch=(key:string,value:Partial<EntryDraft>)=>setDraft(old=>({...old,entries:old.entries.map(e=>e.line_key===key?{...e,...value}:e)}));
  const remove=(key:string)=>setDraft(old=>({...old,entries:old.entries.filter(e=>e.line_key!==key)}));
  const add=(kind:Kind)=>setDraft(old=>({...old,entries:[...old.entries,newEntry(kind)]}));
  const titles:Record<Kind,string>={purchase:'فواتير المشتريات',off_device:'أصناف مبيعة خارج الجهاز',bank:'التحويلات البنكية'};
  const notes:Record<Kind,string>={purchase:'اسم المورد وقيمة الشراء والتفاصيل مطلوبة؛ رقم الفاتورة والمرفق اختياريان.',off_device:'اسم الصنف ورقمه وعدده وقيمة البيع.',bank:'اسم صاحب التحويل ورقم مرجع الحوالة وقيمتها. رقم الفاتورة والمرفق اختياريان.'};
  return <>
    <Panel title="بيانات الصندوق والإيداع" subtitle="هذه بيانات جهاز المحاسبة وسند الإيداع؛ لا يطلب هذا النموذج مبيعات الشبكة أو النقد المتبقي.">
      <div className="fields">
        <MoneyField label="قيمة الصندوق · إجمالي مبيعات الجهاز" value={draft.device_sales} onChange={v=>update('device_sales',v)} disabled={busy}/>
        <MoneyField label="قيمة إيداع الصندوق" value={draft.deposit_amount} onChange={v=>update('deposit_amount',v)} disabled={busy}/>
        <Field label="تاريخ الصندوق في جهاز المحاسبة" value={draft.business_date} type="date" required onChange={v=>update('business_date',v)} disabled={busy}/>
        <Field label="تاريخ سند الإيداع" value={draft.deposit_date} type="date" required onChange={v=>update('deposit_date',v)} disabled={busy}/>
        <Field label="رقم سند الإيداع" value={draft.deposit_number} required maxLength={100} onChange={v=>update('deposit_number',v)} disabled={busy}/>
      </div>
    </Panel>
    {(['purchase','off_device','bank'] as Kind[]).map((kind,index)=>{
      const rows=draft.entries.filter(e=>e.kind===kind);
      return <Panel key={kind} title={titles[kind]} subtitle={notes[kind]} action={<span className="step">0{index+2}</span>}>
        <div className="entry-list">{rows.map((entry,i)=><div className="entry" key={entry.line_key}>
          <header><span>{kind==='purchase'?'فاتورة':kind==='off_device'?'صنف':'تحويل'} {i+1}</span><button type="button" className="icon-button danger-text" aria-label={`حذف ${titles[kind]} ${i+1}`} onClick={()=>remove(entry.line_key)} disabled={busy||entry.uploading}><Trash2 size={17}/></button></header>
          <div className="fields">
            <Field label={kind==='purchase'?'اسم المورد':kind==='off_device'?'اسم الصنف':'اسم صاحب التحويل'} value={entry.name} required onChange={name=>patch(entry.line_key,{name})} disabled={busy}/>
            <MoneyField label={kind==='off_device'?'إجمالي قيمة البيع':kind==='bank'?'قيمة الحوالة':'قيمة فاتورة الشراء'} value={entry.amount} onChange={amount=>patch(entry.line_key,{amount})} disabled={busy}/>
            {kind==='off_device'&&<><Field label="رقم الصنف" value={entry.item_code} required onChange={item_code=>patch(entry.line_key,{item_code})} disabled={busy}/><Field label="عدد الصنف" value={entry.quantity} required onChange={quantity=>patch(entry.line_key,{quantity:normal(quantity)})} disabled={busy}/></>}
            {kind!=='off_device'&&<Field label="رقم الفاتورة (اختياري)" value={entry.invoice_number} maxLength={100} onChange={invoice_number=>patch(entry.line_key,{invoice_number})} disabled={busy}/>}
            {kind==='purchase'&&<label className="field full"><span>أسماء المشتريات وتفاصيل الفاتورة *</span><textarea aria-label="تفاصيل فاتورة الشراء" value={entry.description} required maxLength={2000} rows={2} disabled={busy} onChange={event=>patch(entry.line_key,{description:event.target.value})}/></label>}
            {(kind==='purchase'||kind==='bank')&&<AttachmentField entry={entry} patch={value=>patch(entry.line_key,value)} disabled={busy}/>}
            {kind==='bank'&&<Field label="رقم الحوالة أو الإيداع البنكي" value={entry.reference} required maxLength={100} onChange={reference=>patch(entry.line_key,{reference})} disabled={busy}/>}
          </div>
        </div>)}</div>
        <button type="button" className="text-button add-row" disabled={busy||rows.length>=50} onClick={()=>add(kind)}><Plus size={17}/> {kind==='purchase'?'إضافة فاتورة شراء':kind==='off_device'?'إضافة صنف':'إضافة تحويل بنكي'}</button>
        {!rows.length&&<small className="section-empty">لا توجد عمليات مضافة في هذا القسم.</small>}
      </Panel>
    })}
    <Panel title="ملاحظة الوردية"><label className="field"><span>ملاحظة الوردية (اختياري)</span><textarea aria-label="ملاحظة الوردية" rows={3} maxLength={2000} value={draft.notes} disabled={busy} onChange={event=>update('notes',event.target.value)}/></label></Panel>
  </>
}
