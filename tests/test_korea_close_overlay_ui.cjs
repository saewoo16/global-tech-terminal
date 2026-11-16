/* The current close note is optional and must never rewrite or replace the base archive. */
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const root=path.resolve(__dirname,'..'),read=f=>fs.readFileSync(path.join(root,f),'utf8');
const archive=JSON.parse(read('data/briefings.json')),overlay=JSON.parse(read('data/korea-close-overlay.json'));
const korea=JSON.parse(read('data/korea-market.json')),etf=JSON.parse(read('data/korean_etf_charts.json'));
const snapshot=JSON.stringify({archive,korea,etf}),elements=new Map();
const el=id=>{if(!elements.has(id))elements.set(id,{innerHTML:''});return elements.get(id);};
let base=archive,supplement=overlay;
const ctx={URL,console:{error(){}},window:{addEventListener(){}},document:{readyState:'loading',addEventListener(){},getElementById:el},fetch:async(url,options)=>{
  assert.equal(options.cache,'no-store');
  if(url.includes('/briefings.json'))return {ok:true,json:async()=>base};
  assert(url.includes('/korea-close-overlay.json'));
  if(supplement==='throws')throw Error('offline');
  return {ok:supplement!==null,json:async()=>supplement};
}};
vm.createContext(ctx);
vm.runInContext(read('assets/briefing.js').replace('  if(document.readyState', '  window.overlayTest={load,closeOverlay};\n  if(document.readyState'),ctx);
vm.runInContext(read('assets/korea.js').replace('  if(document.readyState', '  window.koreaTest={closeSection,freshnessSection,earningsSection,setData:v=>payload=v};\n  if(document.readyState'),ctx);
(async()=>{
  const o=ctx.window.overlayTest,k=ctx.window.koreaTest;
  await o.load();k.setData(korea);
  assert.equal(ctx.window.TerminalBriefingData.entries.length,archive.entries.length+1);
  assert.deepEqual(JSON.parse(JSON.stringify(ctx.window.TerminalBriefingData.entries.slice(0,-1))),archive.entries);
  const entry=overlay.entry,close=k.closeSection(),fresh=k.freshnessSection();
  assert(close.includes('KOREA MARKET CLOSE · '+entry.date));
  assert(close.includes('오늘은 양 시장 종가와 마감 해설만 반영'));
  assert(fresh.includes('최신 시황 <strong>'+entry.date+'</strong>'));
  assert(fresh.includes('시장 수급 <strong>'+korea.asOf+'</strong>'));
  assert(fresh.includes('히트맵 <strong>'+korea.heatmaps.asOf+'</strong>'));
  assert.equal(k.earningsSection(),'');
  assert.deepEqual(entry.indices.map(x=>x.name),['KOSPI','KOSDAQ']);
  assert(etf.funds.every(f=>f.daily.at(-1).date===etf.asOf));
  const mutate=[
    x=>x.kind='wrong-kind',x=>x.entry.status='complete',x=>x.entry.market='US',
    x=>x.entry.date='2026-02-30',x=>x.entry.indices[0].close=0,
    x=>x.entry.indices[1].change=0,x=>x.entry.indices[1].sourceIds=['missing'],
    x=>x.entry.sources[0].url='javascript:alert(1)',x=>x.entry.flows.rows.push({foreign:0}),
    x=>x.entry.sectors.asOf=x.entry.date,x=>x.entry.movers={rows:[{name:'Unverified'}]},
  ];
  for(const m of mutate){const bad=structuredClone(overlay);m(bad);assert.strictEqual(o.closeOverlay(archive.entries,bad),archive.entries);}
  for(const missing of [null,'throws',archive]){supplement=missing;await o.load();assert(!ctx.window.TerminalBriefingData.failed);assert.equal(ctx.window.TerminalBriefingData.entries.length,archive.entries.length);}
  supplement=overlay;
  const full={...entry,status:'complete',scope:'full',title:'Newer full archive'};
  for(const day of [entry.date,'2099-01-01']){
    base={schemaVersion:1,entries:[{...full,date:day},...archive.entries]};
    await o.load();
    assert.equal(ctx.window.TerminalBriefingData.entries.length,base.entries.length);
    assert(k.closeSection().includes('Newer full archive'));
  }
  assert.equal(JSON.stringify({archive,korea,etf}),snapshot);
  console.log('PASS current close-only overlay render, archive precedence, stale panel dates, offline fallback and invalid content rejection');
})().catch(e=>{console.error(e);process.exitCode=1});
