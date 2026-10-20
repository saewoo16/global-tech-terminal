const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const root=path.resolve(__dirname,'..'),archive=JSON.parse(fs.readFileSync(root+'/data/briefings.json'));
const entry=archive.entries.find(e=>e.market==='KR'&&e.date==='2026-10-20');
const ctx={URL,Date,Number,String,Array,Set,Map,Math,window:{addEventListener(){}},document:{readyState:'loading',addEventListener(){}}};
vm.createContext(ctx);vm.runInContext(fs.readFileSync(root+'/assets/korea.js','utf8').replace('  if(document.readyState','  window.news=unusualMoverNews;\n  if(document.readyState'),ctx);
let count=0;
for(const row of entry.movers.rows){
 const rendered=ctx.window.news(row,entry);
 if(row.news){assert.equal(row.news.date,entry.date);assert.equal(row.news.kind,'reported-context');assert(row.news.text.length<=160);assert(rendered.includes('관련 뉴스'));assert(rendered.includes('출처 ↗'));assert(row.news.sourceIds.every(id=>entry.sources.some(s=>s.id===id)));count++;}
 else assert.equal(rendered,'');
}
assert.equal(count,4);assert.equal(ctx.window.news(entry.movers.rows.find(r=>r.code==='204320'),entry),'');
for(const news of [null,{text:'',date:entry.date,sourceIds:[]},{text:'test',date:'invalid',sourceIds:['unusual-soil-news-1020']},{text:'test',date:entry.date,sourceIds:['missing']}])assert.equal(ctx.window.news({news},entry),'');
const escaped=ctx.window.news({news:{text:'<script>alert(1)</script>',date:entry.date,sourceIds:['unusual-soil-news-1020']}},entry);assert(!escaped.includes('<script>'));assert(escaped.includes('&lt;script&gt;'));
const bad={sources:[{id:'unsafe',url:'javascript:alert(1)'}]};assert.equal(ctx.window.news({news:{text:'test',date:entry.date,sourceIds:['unsafe']}},bad),'');
console.log('PASS: 4 dated source-linked news notes; absent/unverified notes omitted; HTML and URL safety');
