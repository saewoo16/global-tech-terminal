const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const root=path.resolve(__dirname,'..');
const data=JSON.parse(fs.readFileSync(root+'/data/us_analysis.json','utf8'));
const entry=data.entries.find(e=>e.date==='2026-10-28');
const code=fs.readFileSync(root+'/assets/us-analysis.js','utf8').replace("if(document.readyState==='loading')","window.audit={earningsMetrics};if(document.readyState==='loading')");
const ctx={URL,Date,Number,String,Array,Set,Math,console,window:{addEventListener(){},location:{hash:'#us'}},document:{readyState:'loading',addEventListener(){}}};
vm.createContext(ctx);vm.runInContext(code,ctx);
let comparisons=0;
for(const row of entry.earnings.rows){
 const metrics=ctx.window.audit.earningsMetrics(row);
 assert.equal(JSON.stringify(metrics.map(m=>m.label)),JSON.stringify(['매출','매출총이익','매출총이익률','영업이익률','EPS']),row.ticker);
 const eps=metrics.find(m=>m.label==='EPS');
 if(eps.raw?.consensusComparable){assert.equal(typeof eps.raw.value,'number');assert.equal(typeof eps.raw.consensusValue,'number');assert(eps.basis);comparisons++;}
 const raw=Object.fromEntries(row.metrics.map(m=>[m.label,m]));
 const opm=metrics.find(m=>m.label==='영업이익률');
 if(raw['영업이익'].raw.value===null)assert.equal(opm.raw.value,null,row.ticker+' unknown OP must not become zero OPM');
}
assert(comparisons>0);
console.log(`PASS Oct28 ${entry.earnings.rows.length} cards preserve five displayed metrics and ${comparisons} verified EPS comparisons`);
