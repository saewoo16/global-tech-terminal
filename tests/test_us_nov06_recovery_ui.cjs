const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const root=path.resolve(__dirname,'..'),code=fs.readFileSync(root+'/assets/us-analysis.js','utf8'),data=JSON.parse(fs.readFileSync(root+'/data/us_analysis.json','utf8'));
const context={URL,Date,Number,String,Array,Set,Math,console,window:{location:{hash:'#us'},addEventListener(){}},document:{readyState:'loading',addEventListener(){},getElementById(){return null},querySelectorAll(){return[]},querySelector(){return null}}};
vm.createContext(context);
vm.runInContext(code.replace("if(document.readyState==='loading')","window.recoveryApi={earnings,earningsMetrics,esc};if(document.readyState==='loading')"),context);
const api=context.window.recoveryApi,entry=data.entries.find(e=>e.date==='2026-11-06'),html=api.earnings(entry);
assert(entry);
for(const row of entry.earnings.rows){
 assert(html.includes(row.ticker));
 assert(Array.isArray(row.displayCallHighlights));
 for(const text of row.displayCallHighlights)assert(html.includes(api.esc(text)),row.ticker+' actual call text must render');
 assert(html.includes(row.callSupplement.displayTime));
 assert.deepEqual(Array.from(api.earningsMetrics(row),m=>m.label),['매출','매출총이익','매출총이익률','영업이익률','EPS']);
}
assert.equal((html.match(/컨퍼런스콜 · 경영진 설명 · 후속 보완/g)||[]).length,6);
assert(!html.includes('undefined'));
console.log('PASS November6 six earnings, rendered call supplements, metrics and actual supplement times');
