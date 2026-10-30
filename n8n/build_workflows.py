"""Generate importable, inactive n8n workflows. No credentials or recipients."""
import json
from pathlib import Path

HERE=Path(__file__).parent
API_CRED={'httpHeaderAuth':{'id':'','name':'Bin Doul API'}}
WA_CRED={'httpHeaderAuth':{'id':'','name':'WhatsApp Cloud Bearer'}}
SMTP_CRED={'smtp':{'id':'','name':'Bin Doul SMTP'}}
nodes=[]
connections={}


def node(name,type,parameters,x,y,version=1,credentials=None,**extra):
    value={'id':name.lower().replace(' ','-'),'name':name,'type':type,'typeVersion':version,
           'position':[x,y],'parameters':parameters,**extra}
    if credentials:value['credentials']=credentials
    nodes.append(value)
    return value


def link(source,target,index=0):
    outputs=connections.setdefault(source,{'main':[]})['main']
    while len(outputs)<=index:outputs.append([])
    outputs[index].append({'node':target,'type':'main','index':0})


def request_node(name,path,x,y,method='POST',body=None,file=False,credentials=API_CRED,errors=False):
    parameters={'method':method,'url':"={{ $env.BIN_DOUL_API_URL + '"+path+"' }}",
                'authentication':'genericCredentialType','genericAuthType':'httpHeaderAuth',
                'sendHeaders':True,'headerParameters':{'parameters':[{'name':'Idempotency-Key','value':"={{ 'n8n-'+$execution.id+'-"+name.lower().replace(' ','-')+"' }}"}]},
                'options':{'timeout':20000}}
    if body is not None:parameters.update(sendBody=True,specifyBody='json',jsonBody=body)
    if file:parameters['options']['response']={'response':{'responseFormat':'file','outputPropertyName':'report'}}
    extra={'retryOnFail':False}
    if errors:extra['onError']='continueErrorOutput'
    return node(name,'n8n-nodes-base.httpRequest',parameters,x,y,4.2,credentials,**extra)


def condition(name,left,right,x,y):
    return node(name,'n8n-nodes-base.if',{'conditions':{'options':{'caseSensitive':True,'typeValidation':'strict','version':2},
         'conditions':[{'id':name+'-condition','leftValue':left,'rightValue':right,
         'operator':{'type':'string','operation':'equals'}}],'combinator':'and'}},x,y,2.2)


node('Poll outbox','n8n-nodes-base.scheduleTrigger',{'rule':{'interval':[{'field':'minutes','minutesInterval':1}]}},0,0,1.2)
request_node('Claim notification','/api/integrations/outbox/claim',220,0)
condition('Has a delivery',"={{ $json.delivery ? 'yes' : 'no' }}",'yes',440,0)
message_code="""const d=$input.first().json.delivery;
const p=d.payload;
const format=v=>{const [whole,fraction='']=String(v).split('.');return whole.replace(/\\B(?=(\\d{3})+(?!\\d))/g,',')+'.'+fraction.padEnd(2,'0');};
let subject='',text='';
if(d.kind==='off_device_sales'){
 subject='أصناف خارج الجهاز | '+p.store+' | '+p.business_date;
 text='الموظف: '+p.employee+'\\nتاريخ الصندوق: '+p.business_date+'\\n'+p.items.map(i=>i.name+' | رقم '+i.item_code+' | عدد '+i.quantity+' | قيمة '+format(i.amount)+' ريال يمني').join('\\n');
}else if(d.kind==='cash_shortage'){
 subject='عجز معتمد في الوردية #'+p.shift_id+' | '+p.store;
 text='الموظف: '+p.employee+'\\nتاريخ الصندوق: '+p.business_date+'\\nالعجز: '+format(p.shortage)+' ريال يمني\\nالنقد المتوقع: '+format(p.expected_cash)+'\\nالنقد الموثق: '+format(p.actual_cash)+'\\nملاحظة الاعتماد: '+p.note;
}else{
 subject='التقرير الشهري | '+p.employee+' | '+p.month;
 text='تقرير مستقل للموظف '+p.employee+' عن شهر '+p.month+' بحسب تاريخ الصندوق في جهاز المحاسبة.\\nالمرفق لقطة محفوظة من قاعدة البيانات وقت تجهيز التقرير.';
}
return [{json:{delivery:d,subject,text,whatsapp_summary:(subject+' — '+text.replace(/\\n/g,' | ')).slice(0,1000)}}];"""
node('Prepare message','n8n-nodes-base.code',{'jsCode':message_code},660,0,2)
condition('Email channel',"={{ $json.delivery.channel }}",'email',880,0)
condition('Email monthly report',"={{ $json.delivery.kind }}",'monthly_report',1100,-220)
request_node('Email report PDF',"/api/integrations/events/' + $('Claim notification').first().json.delivery.event_id + '/report.pdf",1320,-400,method='GET',file=True,errors=True)


def email(name,x,y,attachment=False):
    node(name,'n8n-nodes-base.emailSend',{
      'fromEmail':'={{ $env.BIN_DOUL_FROM_EMAIL }}','toEmail':'={{ $env.BIN_DOUL_MANAGER_EMAIL }}',
      'subject':"={{ $('Prepare message').first().json.subject }}",'emailFormat':'text',
      'text':"={{ $('Prepare message').first().json.text }}",
      'options':{'appendAttribution':False,**({'attachments':'report'} if attachment else {})}},x,y,2.1,SMTP_CRED,
      retryOnFail=False,onError='continueErrorOutput')


email('Send monthly email',1540,-400,True)
email('Send alert email',1320,-140)
condition('WhatsApp monthly report',"={{ $json.delivery.kind }}",'monthly_report',1100,260)
request_node('WhatsApp report PDF',"/api/integrations/events/' + $('Claim notification').first().json.delivery.event_id + '/report.pdf",1320,180,method='GET',file=True,errors=True)
graph="={{ 'https://graph.facebook.com/' + $env.BIN_DOUL_WHATSAPP_GRAPH_VERSION + '/' + $env.BIN_DOUL_WHATSAPP_PHONE_ID }}"
node('Upload WhatsApp PDF','n8n-nodes-base.httpRequest',{'method':'POST','url':graph[:-3]+" + '/media' }}",
     'authentication':'genericCredentialType','genericAuthType':'httpHeaderAuth','sendBody':True,
     'contentType':'multipart-form-data','bodyParameters':{'parameters':[
       {'name':'messaging_product','value':'whatsapp'},
       {'parameterType':'formBinaryData','name':'file','inputDataFieldName':'report'}]},
     'options':{'timeout':30000}},1540,180,4.2,WA_CRED,retryOnFail=False,onError='continueErrorOutput')
monthly_body="""={{ {messaging_product:'whatsapp',to:$env.BIN_DOUL_MANAGER_WHATSAPP,type:'template',template:{name:$env.BIN_DOUL_WHATSAPP_MONTHLY_TEMPLATE,language:{code:$env.BIN_DOUL_WHATSAPP_LANGUAGE||'ar'},components:[{type:'header',parameters:[{type:'document',document:{id:$json.id,filename:'employee-'+$('Claim notification').first().json.delivery.payload.employee_id+'-'+$('Claim notification').first().json.delivery.payload.month+'.pdf'}}]},{type:'body',parameters:[{type:'text',text:$('Claim notification').first().json.delivery.payload.store},{type:'text',text:$('Claim notification').first().json.delivery.payload.employee},{type:'text',text:$('Claim notification').first().json.delivery.payload.month}]}]}} }}"""
alert_body="""={{ {messaging_product:'whatsapp',to:$env.BIN_DOUL_MANAGER_WHATSAPP,type:'template',template:{name:$env.BIN_DOUL_WHATSAPP_ALERT_TEMPLATE,language:{code:$env.BIN_DOUL_WHATSAPP_LANGUAGE||'ar'},components:[{type:'body',parameters:[{type:'text',text:$('Claim notification').first().json.delivery.payload.store},{type:'text',text:$('Prepare message').first().json.whatsapp_summary}]}]}} }}"""


def whatsapp(name,body,x,y):
    # n8n's template tokenizer closes an expression at the first adjacent }}.
    # Separate nested object braces inside the expression before its final tag.
    body='={{ ('+body[3:-2].replace('}}','} }')+') }}'
    node(name,'n8n-nodes-base.httpRequest',{'method':'POST','url':graph[:-3]+" + '/messages' }}",
          'authentication':'genericCredentialType','genericAuthType':'httpHeaderAuth','sendBody':True,
          'specifyBody':'json','jsonBody':body,'options':{'timeout':30000}},x,y,4.2,WA_CRED,
          retryOnFail=False,onError='continueErrorOutput')


whatsapp('Send WhatsApp monthly',monthly_body,1760,180)
whatsapp('Send WhatsApp alert',alert_body,1320,480)
sent_body="""={{ {lease_token:$('Claim notification').first().json.delivery.lease_token,outcome:'sent',provider_reference:String($json.messageId||$json.messages?.[0]?.id||'').slice(0,200)} }}"""
uncertain_body="""={{ {lease_token:$('Claim notification').first().json.delivery.lease_token,outcome:'uncertain',detail:'n8n provider step did not confirm delivery. Inspect execution '+$execution.id+' before retrying.'} }}"""
request_node('Confirm sent',"/api/integrations/deliveries/' + $('Claim notification').first().json.delivery.id + '/result",1980,-80,body=sent_body)
request_node('Mark uncertain',"/api/integrations/deliveries/' + $('Claim notification').first().json.delivery.id + '/result",1980,480,body=uncertain_body)
for a,b in [('Poll outbox','Claim notification'),('Claim notification','Has a delivery'),('Has a delivery','Prepare message'),('Prepare message','Email channel'),('Email channel','Email monthly report'),('Email monthly report','Email report PDF'),('Email report PDF','Send monthly email'),('WhatsApp monthly report','WhatsApp report PDF'),('WhatsApp report PDF','Upload WhatsApp PDF'),('Upload WhatsApp PDF','Send WhatsApp monthly')]:link(a,b)
link('Email channel','WhatsApp monthly report',1)
link('Email monthly report','Send alert email',1)
link('WhatsApp monthly report','Send WhatsApp alert',1)
for name in ['Send monthly email','Send alert email','Send WhatsApp monthly','Send WhatsApp alert']:
    link(name,'Confirm sent');link(name,'Mark uncertain',1)
for name in ['Email report PDF','WhatsApp report PDF','Upload WhatsApp PDF']:link(name,'Mark uncertain',1)

workflow={'name':'Bin Doul | Financial notifications (inactive)','active':False,'nodes':nodes,'connections':connections,
          'settings':{'executionOrder':'v1','timezone':'Asia/Aden','executionTimeout':540},'pinData':{},'tags':[]}
(HERE/'01_financial_notifications.json').write_text(json.dumps(workflow,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
nodes=[];connections={}
node('First day each month','n8n-nodes-base.scheduleTrigger',{'rule':{'interval':[{'field':'cronExpression','expression':'0 0 6 1 * *'}]}},0,0,1.2)
request_node('Prepare previous month','/api/integrations/monthly-reports',240,0)
link('First day each month','Prepare previous month')
workflow={'name':'Bin Doul | Monthly reports (inactive)','active':False,'nodes':nodes,'connections':connections,
          'settings':{'executionOrder':'v1','timezone':'Asia/Aden'},'pinData':{},'tags':[]}
(HERE/'02_monthly_employee_reports.json').write_text(json.dumps(workflow,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('Generated two inactive n8n workflows; no messages sent.')
