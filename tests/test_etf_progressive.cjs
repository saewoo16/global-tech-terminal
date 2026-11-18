'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const root=path.resolve(__dirname,'..');
(async()=>{
for(const [asset,data,website,count,industry,theme] of [
 ['korean-etf','korean_etf_charts','','39',15,24],
 ['overseas-etf','overseas_etf_charts','us-','38',30,8]
]){
 const orig=fs.readFileSync(root+'/assets/'+asset+'.js','utf8');
 const store=JSON.parse(fs.readFileSync(root+'/data/'+data+'.json','utf8'));
 const inject=orig.replace("if(document.readyState==='loading')","window.__test={load,filtered,countsLabel,setGroup:g=>group=g};if(document.readyState==='loading')");
 assert.notEqual(inject,orig);
 const ids=new Map(),el=id=>{if(!ids.has(id))ids.set(id,{textContent:'',innerHTML:'',querySelectorAll(){return []},querySelector(){return {}},replaceChildren(){}});return ids.get(id);};
 let closeResolve,fetches=[],fail=false;
 const ctx={URL,Date,Number,String,Math,Array,AbortController,setTimeout,clearTimeout,console:{error(){}},window:{location:{hash:'#other'}},document:{readyState:'loading',addEventListener(){},getElementById:el},
  fetch(url,options){fetches.push(url);assert.equal(options.cache,'no-cache');assert(options.signal instanceof AbortSignal);
   if(url.includes(data))return fail?Promise.reject(Error('offline')):Promise.resolve({ok:true,json:async()=>store});
   assert(url.includes(website?'us-analysis-latest':'korea-close-overlay'));return new Promise(r=>{closeResolve=r;});}};
 vm.runInNewContext(inject,ctx);
 const api=ctx.window.__test,list=el(website+'etf-list'),detail=el(website+'etf-detail'),status=el(website+'etf-updated');
 await api.load();
 assert.equal((list.innerHTML.match(/data-etf="/g)||[]).length,Number(count));
 assert.match(detail.innerHTML,/class="etf-plot"/);
 assert.match(el(website+'etf-plot').innerHTML,/<svg/);
 assert.equal(api.countsLabel(),'업종 '+industry+'개 · 테마 '+theme+'개');
 assert(status.textContent.includes('2026-11-13'));
 for(const [g,n] of [['industry',industry],['theme',theme]]){api.setGroup(g);assert.equal(api.filtered().length,n);assert(api.filtered().every(f=>f.group===g));}
 api.setGroup('all');
 assert(closeResolve);assert(fetches[0].includes(data));
 const market=website?{entry:{date:'2026-11-18',sessionStatus:'closed',sessionVerification:{exchangeDate:'2026-11-18'}}}:JSON.parse(fs.readFileSync(root+'/data/korea-close-overlay.json','utf8'));
 closeResolve({ok:true,json:async()=>market});await new Promise(r=>setImmediate(r));
 assert(status.textContent.includes('2026-11-18'));assert(status.textContent.includes('0/'+count));
 assert(status.textContent.includes('2026-11-13'));
 fail=true;const before=detail.innerHTML;await api.load();assert.match(status.innerHTML,/다시 불러오기/);assert.equal(detail.innerHTML,before);assert.equal(typeof el(website+'etf-retry').onclick,'function');
}
console.log('PASS 39 domestic and 38 overseas archive charts appear independently, groups match October, and failed refresh preserves the chart with a retry.');
})().catch(e=>{console.error(e);process.exitCode=1;});
