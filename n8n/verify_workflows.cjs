const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const data=JSON.parse(fs.readFileSync(path.join(__dirname,'01_financial_notifications.json'),'utf8'));
const script=data.nodes.find(n=>n.name==='Prepare message').parameters.jsCode;
const message=new Function('$input',script)({first:()=>({json:{delivery:{kind:'off_device_sales',payload:{store:'سوبر ماركت بن دول',employee:'موظف',business_date:'2026-09-28',items:[{name:'صنف',item_code:'0001',quantity:1,amount:'9999999999999999.99'}]}}}})})[0].json;
assert.ok(message.text.includes('9,999,999,999,999,999.99'));
let expressions=0;
function walk(obj){if(typeof obj==='string'&&obj.startsWith('={{')&&obj.endsWith('}}')){const inner=obj.slice(3,-2);assert.ok(!inner.includes('}}'),'Nested braces must not prematurely close an n8n expression');new Function('$env','$','$json','$execution','return ('+inner+')');expressions++}else if(obj&&typeof obj==='object')Object.values(obj).forEach(walk)}
for(const filename of ['01_financial_notifications.json','02_monthly_employee_reports.json']){
 const workflow=JSON.parse(fs.readFileSync(path.join(__dirname,filename)));
 assert.equal(workflow.active,false);
 const names=new Set(workflow.nodes.map(n=>n.name));
 for(const[source,outputs]of Object.entries(workflow.connections)){
  assert.ok(names.has(source));
  for(const output of outputs.main)for(const target of output)assert.ok(names.has(target.node));
 }
 walk(workflow);
}
console.log('PASS: workflow JSON, all node links, '+expressions+' expressions, and exact large-money formatting. No provider was called.');
