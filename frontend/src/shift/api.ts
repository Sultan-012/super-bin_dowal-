import {useEffect,useRef,useState} from 'react';
export class APIError extends Error{constructor(public status:number,message:string){super(message)}}
const csrf=()=>decodeURIComponent(document.cookie.split('; ').find(x=>x.startsWith('bin_doul_csrf='))?.slice('bin_doul_csrf='.length)||'');
export async function request<T>(path:string,method='GET',data?:unknown,key?:string):Promise<T>{
  let response:Response;
  try{response=await fetch('/api'+path,{method,credentials:'same-origin',headers:{'Content-Type':'application/json','X-CSRF-Token':csrf(),...(key?{'Idempotency-Key':key}:{})},body:data===undefined?undefined:JSON.stringify(data)})}
  catch{throw new APIError(0,'تعذر الاتصال. أعد المحاولة؛ سيستخدم الطلب المفتاح نفسه لمنع التكرار.')}
  const body=await response.json().catch(()=>null);
  if(!response.ok){if(response.status===401&&!['/auth/login','/auth/me'].includes(path))window.dispatchEvent(new Event('bin-doul-expired'));throw new APIError(response.status,body?.message||'تعذر إكمال العملية.')}
  return body as T;
}
export function useLoad<T>(path:string|null,revision=0){
  const [data,setData]=useState<T|null>(null),[error,setError]=useState(''),[loading,setLoading]=useState(!!path);
  useEffect(()=>{let active=true;setData(null);setError('');setLoading(!!path);if(path)request<T>(path).then(x=>{if(active)setData(x)}).catch(e=>{if(active)setError(e.message)}).finally(()=>{if(active)setLoading(false)});return()=>{active=false}},[path,revision]);
  return{data,error,loading};
}
export function useAction(){
  const [busy,setBusy]=useState(false),[error,setError]=useState(''),pending=useRef(false),attempt=useRef({fingerprint:'',key:''});
  async function run<T>(path:string,method:string,data:unknown,success:(result:T)=>void){
    if(pending.current)return;pending.current=true;setBusy(true);setError('');
    const fingerprint=JSON.stringify([path,method,data]);if(attempt.current.fingerprint!==fingerprint)attempt.current={fingerprint,key:crypto.randomUUID()};
    try{const result=await request<T>(path,method,data,attempt.current.key);attempt.current={fingerprint:'',key:''};success(result)}catch(e){setError((e as Error).message)}finally{pending.current=false;setBusy(false)}
  }
  return{run,busy,error,setError};
}
export async function upload(file:File,key:string){
  let response:Response;
  try{response=await fetch('/api/attachments',{method:'POST',credentials:'same-origin',headers:{'Content-Type':file.type||'application/octet-stream','X-Filename':encodeURIComponent(file.name),'X-CSRF-Token':csrf(),'Idempotency-Key':key},body:file})}
  catch{throw new Error('تعذر رفع المرفق. اختر الملف نفسه لإعادة المحاولة دون تكرار.')}
  const data=await response.json();if(!response.ok)throw new Error(data.message||'تعذر رفع المرفق.');return data as{id:string;filename:string};
}
export async function download(path:string,name:string){
  const response=await fetch('/api'+path,{credentials:'same-origin'});
  if(!response.ok){const data=await response.json().catch(()=>null);throw new Error(data?.message||'تعذر تصدير الملف.')}
  const url=URL.createObjectURL(await response.blob()),a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),10000);
}
