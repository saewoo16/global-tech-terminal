const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const root=path.resolve(__dirname,'..'),raw=fs.readFileSync(root+'/assets/macro.js','utf8'),html=fs.readFileSync(root+'/index.html','utf8');
const c={window:{},document:{readyState:'loading',addEventListener(){}},URL,Date,Set,Object,Number};
vm.createContext(c);vm.runInContext(raw,c);
const a=c.window.TerminalMacro,d=JSON.parse(fs.readFileSync(root+'/data/fedwatch.json','utf8'));
assert(a.validFedwatch(d));assert(!a.validFedwatch({...d,meetings:[{date:'2026-10-28',probabilities:[90,20,0,0]}]}));
assert.deepEqual(JSON.parse(JSON.stringify(a.direction([[375,400],[400,425]],[90,10],[375,400]))),{cut:0,hold:90,hike:10});
assert.deepEqual(JSON.parse(JSON.stringify(a.direction([[350,375],[375,400],[400,425]],[60,30,10],[375,400]))),{cut:60,hold:30,hike:10});
const output=a.fedwatchHTML(d), firstDirection=a.direction(d.columnsBps,d.meetings[0].probabilities,d.currentTargetBps);
for(const [label,key] of [['동결','hold'],['인상','hike'],['인하','cut']])assert(output.includes(label+' '+firstDirection[key].toFixed(2)+'%'));
for(const value of Object.values(d.nextMeetingComparison.hikeChangePp))assert(output.includes(value.toFixed(1)+'%p'));assert(output.includes('실시간 아님'));
assert(output.includes(d.meetings[0].probabilities[1].toFixed(2)+'%'));assert(output.includes('각 회의 한 번의 인상 확률이 아닙니다'));assert(output.includes('자동 실시간 갱신되지 않습니다'));
assert.equal(a.safeURL('javascript:alert(1)'),'#');
const q=a.quoteHTML({value:103.44,precision:2,quoteLabel:'<x>',unit:'USD/배럴',sourceUrl:'javascript:x',asOf:'2026-10-23',status:'stale'},'WTI_FUTURES');
assert(q.includes('103.44'));assert(q.includes('&lt;x&gt;'));assert(q.includes('서로 다른 상품'));assert(q.includes('이전 검증 수치'));assert(!q.includes('javascript:'));
assert(html.indexOf('id="fedwatch-panel"')<html.indexOf('id="rates-grid"'));
for(const id of ['UST10Y','WTI_FUTURES','BRENT_FUTURES','DXY','USDJPY','USDKRW'])assert(html.includes('data-macro-quote="'+id+'"'));
assert(html.includes('data-series="DXY"'));assert(!html.includes('data-series="DTWEXBGS"'));assert(html.includes('data-series="M1SL"'));assert(html.includes('data-series="M2SL"'));
assert(!html.includes('quikstrike'));assert(!raw.includes('quikstrike'));
console.log('PASS macro source safety, instrument distinction, verified CME distribution, correct cut/hold/hike and same-precision historical deltas');

assert(raw.includes("q.sourceName!=='FRED'"));

const ambiguous=a.fedwatchHTML({...d,providerAsOf:null,providerAsOfLabel:'1 11 2026 01:45:01 CT'});
assert(ambiguous.includes('1 11 2026 01:45:01 CT'));assert(ambiguous.includes('UTC 오프셋 미확인'));

// The supplier may add or remove zero-probability target ranges between snapshots.
for(const columnCount of [2,3,4,5]){
 const columns=Array.from({length:columnCount},(_,i)=>[375+25*i,400+25*i]);
 const probabilities=Array.from({length:columnCount},(_,i)=>i===0?100:0);
 const sample={...d,columnsBps:columns,meetings:[{date:'2026-12-09',probabilities}]};
 assert(a.validFedwatch(sample));
 const rendered=a.fedwatchHTML({...sample,nextMeetingComparison:null,conditionalComparisons:null});
 assert.equal((rendered.match(/<th>/g)||[]).length,columnCount+1);
 assert(!a.validFedwatch({...sample,meetings:[{date:'2026-12-09',probabilities:probabilities.slice(1)}]}));
}
console.log('PASS changing CME source column counts without invented probability cells');

const official=JSON.parse(fs.readFileSync(root+'/data/macro-official-latest.json','utf8'));
assert(a.validOfficial(official));
const policy=a.officialPolicyHTML(official);
assert(policy.includes(official.session));assert(policy.includes('3.75–4.00%'));
for(const n of ['4.80%','5.10%','5.46%'])assert(policy.includes(n),n);
assert(policy.includes('CME 확률은 이곳에 재게시하지 않습니다'));
assert(!policy.includes('<table'));
const mapped=Object.fromEntries(official.rows.map(r=>[r.id,r]));
for(const id of ['WTI_FUTURES','BRENT_FUTURES','DXY']){
 assert(!a.officialRow(mapped[id]).includes('<strong>'));
 const rows=official.rows.map(r=>r.id===id?{...r,value:0.01}:r);
 assert(!a.validOfficial({...official,rows}));
}
assert(a.officialRow(mapped.USDJPY).includes('관측일 2026-11-13'));
assert(a.officialRow(mapped.M1SL).includes('관측월 2026-09'));
assert(a.officialRow(mapped.USD_BROAD).includes('ICE DXY와 다른 지표'));
assert(!a.validOfficial({...official,rows:official.rows.map(r=>r.id==='UST10Y'?{...r,asOf:'2099-01-01'}:r)}));
assert(!a.validOfficial({...official,rows:official.rows.map(r=>r.id==='UST10Y'?{...r,sourceUrl:'https://home.treasury.gov@attacker.example/'}:r)}));
const targets=Object.fromEntries(['USDJPY','DXY','WTI_FUTURES','UST10Y'].map(id=>[id,{dataset:{macroQuote:id},innerHTML:''}]));
const ratePanel={innerHTML:''}, fetches=[];
c.document.querySelectorAll=(selector)=>selector==='[data-macro-quote]'?Object.values(targets):[];
c.document.getElementById=(id)=>id==='fedwatch-content'?ratePanel:null;
c.window.location={hash:'#rates'};
c.fetch=async url=>{fetches.push(url);return {ok:true,json:async()=>official};};
(async()=>{
 await a.load();
 assert.deepEqual(fetches,['./data/macro-official-latest.json']);
 assert(ratePanel.innerHTML.includes('재게시하지 않습니다'));
 assert(targets.USDJPY.innerHTML.includes('159.93'));
 assert(targets.DXY.innerHTML.includes('122.6503'));
 assert(!targets.WTI_FUTURES.innerHTML.includes('<strong>'));
 a.renderOfficial(null);
 assert(ratePanel.innerHTML.includes('공식 수치를 불러오지 못했습니다'));
 assert(!targets.USDJPY.innerHTML.includes('159.93'));
 console.log('PASS official-only macro tab fetch, real observation dates, link-only instruments and no stale fallback');
})().catch(e=>{console.error(e); process.exitCode=1;});
