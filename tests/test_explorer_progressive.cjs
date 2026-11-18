const assert=require('node:assert/strict'), fs=require('node:fs'), vm=require('node:vm'),path=require('node:path');
const html=fs.readFileSync(path.resolve(__dirname,'../index.html'),'utf8');
const script=html.match(/<script>\n([\s\S]*?)<\/script>/)[1];
const nodes=new Map(),calls=[],timers=new Map(); let timer=0;
const elem=id=>nodes.get(id)||nodes.set(id,{hidden:false,value:'',textContent:'',innerHTML:'',classList:{toggle(){}},append(){},scrollIntoView(){}}).get(id);
const ctx=vm.createContext({document:{readyState:'loading',getElementById:elem,addEventListener(){},querySelectorAll:()=>[],createElement:()=>({}),createTextNode:()=>({})},window:{innerWidth:1000},URL,AbortController,console:{error(){}},
 fetch(url,options){return new Promise(resolve=>calls.push({url,options,resolve}));},
 setTimeout(cb,ms){timers.set(++timer,{cb,ms});return timer;},clearTimeout(id){timers.delete(id);}
});
const run=s=>vm.runInContext(s,ctx), settle=()=>new Promise(setImmediate);
const reply=(r,data)=>r.resolve({ok:true,json:async()=>data});
(async()=>{
 vm.runInContext(script,ctx);
 const first=run('boot()');
 const companies=calls.find(r=>r.url.includes('companies.json')), market=calls.find(r=>r.url.includes('market.json'));
 assert.match(market.url,/market\.json\?v=20261115-company-pm$/);
 assert.equal(market.options.cache,'no-cache');
 let company=x=>({symbol:x,ticker:x,name:x,sector:'Tech',category:'Tech',country:'미국'});
 reply(companies,[company('FIRST'),company('SECOND')]);await settle();
 assert.equal(elem('count').textContent,2);
 assert.equal(run('chosen.symbol'),'FIRST');
 assert.match(elem('update').textContent,/기업 목록 표시 중 · 시세 불러오는 중/);
 run("select('SECOND')");
 [...timers.values()].find(t=>t.ms===20000).cb(); await first;
 assert.equal(market.options.signal.aborted,true);
 assert.equal(elem('explorer-retry').hidden,false);
 assert.match(elem('update').textContent,/시세 파일을 불러오지 못했습니다/);
 const again=elem('explorer-retry').onclick();await settle();
 assert.equal(calls.filter(r=>r.url.includes('companies.json')).length,1);
 const market2=calls.filter(r=>r.url===market.url).at(-1);
 reply(market2,{stocks:{FIRST:{},SECOND:{}},updated:'2026-11-18'});await again;
 assert.equal(elem('explorer-retry').hidden,true);
 assert.equal(run('chosen.symbol'),'SECOND');
 assert.match(elem('update').textContent,/2026-11-18 · 2개 종목/);
 assert.equal(calls.filter(r=>r.url.includes('financial_backfill')).length,1);
 console.log('PASS: pending market and optional files do not block company list; bounded market timeout, cache revalidation, retry and selection retention.');
})().catch(error=>{console.error(error);process.exitCode=1;});
