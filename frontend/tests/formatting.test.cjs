const assert=require('node:assert/strict');
const fs=require('node:fs');
const os=require('node:os');
const path=require('node:path');
const esbuild=require('esbuild');
const temporary=fs.mkdtempSync(path.join(os.tmpdir(),'bin-doul-format-'));
try{
 const output=path.join(temporary,'ui.cjs');
 esbuild.buildSync({entryPoints:[path.join(__dirname,'../src/shift/ui.tsx')],outfile:output,bundle:true,platform:'node',format:'cjs',jsx:'automatic',logLevel:'silent'});
 const q=require(output);
 assert.equal(q.displayMoney('10000.50'),'10,000.50');
 assert.equal(q.displayMoney('١٠٠٠٠٫٥٠'),'10,000.50');
 assert.equal(q.cleanMoney('١٠٬٠٠٠٫٥٠'),'10000.50');
 assert.equal(q.fmt('-10000.50'),'−10,000.50');
 assert.equal(q.cents('-40.50'),-4050n);
 assert.equal(q.cents('0.10')+q.cents('0.20'),30n);
 assert.equal(q.fmt(null),'—');
 assert.ok(q.dayLabel('2026-09-28').includes('2026'));
 assert.equal(q.dayLabel('invalid'),'حدد تاريخًا صحيحًا');
 assert.equal(q.monthLabel('invalid'),'حدد شهرًا صحيحًا');
 console.log('PASS: 10 checks for Arabic input, separators, exact formatting, null counts and invalid dates.');
}finally{fs.rmSync(temporary,{recursive:true,force:true})}
