const assert=require('node:assert/strict'), fs=require('node:fs'), vm=require('node:vm'), path=require('node:path');
const read=p=>fs.readFileSync(path.join(__dirname,'..',p),'utf8'), json=p=>JSON.parse(read(p));
const html=read('index.html'), inline=Array.from(html.matchAll(/<script>([\s\S]*?)<\/script>/g)).at(-1)[1];
const c={console,URL,document:{readyState:'loading',addEventListener(){},getElementById(){return {}},querySelectorAll(){return []}}};
vm.createContext(c);
vm.runInContext(inline,c);
assert.doesNotMatch(html,/tw-close-comparison|explorerOfficialCloseComparison|대만 거래소 공식 종가 비교/);
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
assert.doesNotMatch(html,/data-etf-today=|etf-today-note/);
assert.doesNotMatch(read('assets/korean-etf.js'),/recentComparison|거래소 일봉 ·/);
console.log('PASS current report: six scoped provisional flow values, no disconnected Taiwan point comparison, and no domestic ETF standalone candles.');
