import {useEffect,useRef} from 'react';
import type {ReactNode,FormEvent} from 'react';
import {LoaderCircle,X} from 'lucide-react';
import type {Kind} from './types';
export const normal=(value:string)=>value.replace(/[٠-٩]/g,d=>String('٠١٢٣٤٥٦٧٨٩'.indexOf(d))).replace(/[۰-۹]/g,d=>String('۰۱۲۳۴۵۶۷۸۹'.indexOf(d))).replace(/٫/g,'.').replace(/٬/g,',');
export const cleanMoney=(v:string)=>normal(v).replace(/,/g,'').trim();
export function displayMoney(v:string){const t=normal(v),p=t.replace(/,/g,'');if(!/^\d*(\.\d{0,2})?$/.test(p))return t;const [a,b]=p.split('.');return a.replace(/\B(?=(\d{3})+(?!\d))/g,',')+(b===undefined?'':'.'+b)}
export const cents=(v:string|null|undefined)=>{if(!v)return 0n;const text=cleanMoney(v),negative=text.startsWith('-'),[whole,fraction='']=text.replace(/^-/,'').split('.');const value=BigInt(whole||'0')*100n+BigInt(fraction.padEnd(2,'0'));return negative?-value:value};
export function fmt(v:string|number|null|undefined){if(v===null||v===undefined)return '—';const raw=String(v),negative=raw.startsWith('-'),[a,b='']=raw.replace(/^-/,'').split('.');return(negative?'−':'')+a.replace(/\B(?=(\d{3})+(?!\d))/g,',')+'.'+b.padEnd(2,'0')}
export const dayLabel=(v:string)=>{const value=new Date(v.slice(0,10)+'T12:00:00Z');return Number.isNaN(value.getTime())?'حدد تاريخًا صحيحًا':new Intl.DateTimeFormat('ar-YE-u-ca-gregory-nu-latn',{day:'numeric',month:'long',year:'numeric',timeZone:'UTC'}).format(value)};
export const monthLabel=(v:string)=>{const value=new Date(v+'-01T12:00:00Z');return Number.isNaN(value.getTime())?'حدد شهرًا صحيحًا':new Intl.DateTimeFormat('ar-YE-u-ca-gregory-nu-latn',{month:'long',year:'numeric',timeZone:'UTC'}).format(value)};
export const kindLabel:Record<Kind,string>={purchase:'فاتورة مشتريات',off_device:'صنف خارج الجهاز',bank:'تحويل بنكي'};
export const purposeLabel={current_shift:'تحويل بنكي للوردية',customer_account:'تسديد قديم (أرشيف)'};
export const statusLabel={pending:'بانتظار اعتماد المدير',confirmed:'معتمدة'};
export const Amount=({value}:{value:string|number|null|undefined})=><span className="number" dir="ltr">{fmt(value)}</span>;
export const Pill=({children,tone=''}:{children:ReactNode;tone?:string})=><span className={'pill '+tone}>{children}</span>;
export const ErrorBox=({message}:{message:string})=>message?<div className="alert error" role="alert">{message}</div>:null;
export const Loading=()=> <div className="loading" role="status"><LoaderCircle className="spin" size={20}/> جار تحميل البيانات…</div>;
export const Empty=({children}:{children:ReactNode})=><div className="empty">{children}</div>;
export function Field({label,name,value,onChange,required=false,type='text',hint='',maxLength=150,disabled=false}:{label:string;name?:string;value:string;onChange?:(v:string)=>void;required?:boolean;type?:string;hint?:string;maxLength?:number;disabled?:boolean}){return <label className="field"><span>{label}{required&&<small className="required"> *</small>}</span><input name={name} aria-label={label} type={type} value={value} onChange={e=>onChange?.(e.target.value)} required={required} readOnly={!onChange} disabled={disabled} maxLength={maxLength} autoComplete={type==='password'?'new-password':'off'}/>{hint&&<small>{hint}</small>}</label>}
export function MoneyField({label,value,onChange,required=true,hint='',disabled=false}:{label:string;value:string;onChange:(v:string)=>void;required?:boolean;hint?:string;disabled?:boolean}){
  const input=useRef<HTMLInputElement>(null);
  return <label className="field"><span>{label}{required&&<small className="required"> *</small>}</span><input ref={input} aria-label={label} type="text" inputMode="decimal" dir="ltr" data-money value={displayMoney(value)} required={required} maxLength={30} autoComplete="off" disabled={disabled} placeholder="0.00" onChange={event=>{const control=event.target,raw=normal(control.value),position=(control.selectionStart??raw.length),logical=raw.slice(0,position).replace(/,/g,'').length;const next=displayMoney(raw);onChange(next);requestAnimationFrame(()=>{if(document.activeElement===input.current){let count=0,target=0;for(;target<next.length&&count<logical;target++)if(next[target]!==',')count++;input.current?.setSelectionRange(target,target)}})}}/>{hint&&<small>{hint}</small>}</label>
}
export function Panel({title,subtitle,action,children}:{title:string;subtitle?:string;action?:ReactNode;children:ReactNode}){return <section className="panel"><header className="panel-head"><div><h2>{title}</h2>{subtitle&&<p>{subtitle}</p>}</div>{action}</header>{children}</section>}
export function Heading({eyebrow,title,description,action}:{eyebrow:string;title:string;description?:string;action?:ReactNode}){return <div className="heading"><div><span className="eyebrow">{eyebrow}</span><h1>{title}</h1>{description&&<p>{description}</p>}</div>{action}</div>}
export function Modal({title,children,onClose}:{title:string;children:ReactNode;onClose:()=>void}){
  const ref=useRef<HTMLDialogElement>(null),close=useRef(onClose);close.current=onClose;
  useEffect(()=>{const d=ref.current;d?.showModal();return()=>d?.close()},[]);
  return <dialog ref={ref} className="modal" onCancel={event=>{event.preventDefault();close.current()}} aria-label={title}><header className="modal-head"><h2>{title}</h2><button className="icon-button" type="button" aria-label="إغلاق النافذة" onClick={onClose}><X size={20}/></button></header>{children}</dialog>
}
export function Form({onSubmit,children}:{onSubmit:(e:FormEvent<HTMLFormElement>)=>void;children:ReactNode}){return <form autoComplete="off" onSubmit={event=>{event.preventDefault();onSubmit(event)}}>{children}</form>}
