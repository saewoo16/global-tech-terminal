const assert=require('node:assert/strict'), fs=require('node:fs'), vm=require('node:vm'), path=require('node:path');
const read=p=>fs.readFileSync(path.join(__dirname,'..',p),'utf8'), json=p=>JSON.parse(read(p));
const html=read('index.html'), inline=Array.from(html.matchAll(/<script>([\s\S]*?)<\/script>/g)).at(-1)[1];
const c={console,URL,document:{readyState:'loading',addEventListener(){},getElementById(){return {}},querySelectorAll(){return []}}};
vm.createContext(c);
vm.runInContext(inline,c);
const prior=json('data/explorer-taiwan-open-close.json'),latest=json('data/explorer-taiwan-open-close-latest.json');
for(const symbol of Object.keys(latest.quotes)){
 const b=c.explorerOfficialCloseComparison(symbol,prior,latest);
 assert.match(b,/role="img"/);assert.match(b,/2026-11-16/);assert.match(b,/2026-11-18/);
 assert.doesNotMatch(b,/2026-11-17/);assert.equal(c.explorerOfficialCloseComparison(symbol,prior,prior),'');
}
assert.equal(c.explorerOfficialCloseComparison('NASDAQ:NVDA',prior,latest),'');
assert.equal(c.explorerOfficialCloseComparison('TWSE:2408',null,latest),'');
const common={console,URL,window:{},document:{readyState:'loading',addEventListener(){},getElementById(){return {}},querySelectorAll(){return []}}};
vm.createContext(common);
vm.runInContext(read('assets/korea.js').replace('  function dailyFlowSummary()', '  window.flowCards=dailyFlowSummary;\n  function dailyFlowSummary()'),common);
const kr=json('data/korea-close-overlay.json').entry;
const renderFlow=entry=>{common.window.TerminalBriefingData={entries:[entry]};return common.window.flowCards();};
const out=renderFlow(kr);
assert.equal((out.match(/<article/g)||[]).length,2);
assert.doesNotMatch(out,/<svg|role="img"/);
assert.match(out,/KOSPI.*-3,300/);assert.match(out,/KOSDAQ.*1,800/);assert.match(out,/잠정/);
for(const obs of [null,{...kr.reportedCloseFlow,roundedEok:{KOSPI:{foreign:'<script>'}}},{...kr.reportedCloseFlow,date:'2026-11-17'}]){
 const invalid=renderFlow({...kr,reportedCloseFlow:obs});
 assert.match(invalid,/확인하지 못했습니다/);assert.doesNotMatch(invalid,/<article|<script>/);
}
vm.runInContext(read('assets/korean-etf.js').replace('function recentComparison(f)', 'window.etfNote=recentComparison;\nfunction recentComparison(f)'),common);
for(const [id,pct,close] of [['091160','+2.46%','89,755'],['0148J0','+9.97%','7,610'],['0177X0','+9.94%','7,795'],['466920','-0.57%','17,395']]){
 const card=common.window.etfNote({code:id,daily:[{date:'2026-11-13'}]});
 assert.ok(card.includes(pct)&&card.includes(close),id);
 assert.match(card,/2026-11-18 정규장 일봉/);
 const body=card.match(/<rect x="59" y="([0-9.]+)" width="24" height="([0-9.]+)"/);
 assert.ok(body&&Number(body[1])>=12&&Number(body[1])+Number(body[2])<=104,id+' candle body stays in the dated session range');
 assert.equal(common.window.etfNote({code:id,daily:[{date:'2026-11-18'}]}),'');
}
assert.equal(common.window.etfNote({code:'069500'}),'');
console.log('PASS current report: six scoped provisional flow values in dated cards, 32 Taiwan two-observation charts, four dated Korean ETF candles, no stale replacement.');
