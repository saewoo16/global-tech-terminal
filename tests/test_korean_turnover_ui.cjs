const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const root=path.resolve(__dirname,'..'),read=file=>fs.readFileSync(path.join(root,file),'utf8');
const raw=read('assets/korea.js');
const ctx={URL,Date,Number,String,Array,Set,Map,Math,console,window:{addEventListener(){}},document:{readyState:'loading',addEventListener(){}}};vm.createContext(ctx);
vm.runInContext(raw.replace('  if(document.readyState',`  window.api={marketTurnoverSection,dailyFlowSummary,flowSection,rangeRows,chartModel,setData:v=>payload=v};\n  if(document.readyState`),ctx);
const api=ctx.window.api;
const rows=[{date:'2025-10-29',turnover:100},{date:'2026-04-29',turnover:200},{date:'2026-07-29',turnover:300},{date:'2026-09-29',turnover:null},{date:'2026-10-29',turnover:400}];
assert.equal(api.rangeRows(rows,'1M').length,2);assert.equal(api.rangeRows(rows,'3M').length,3);assert.equal(api.rangeRows(rows,'6M').length,4);assert.equal(api.rangeRows(rows,'1Y').length,5);
assert.equal(api.rangeRows([{date:'2026-02-28'},{date:'2026-03-31'}],'1M').length,2);
assert.equal((api.chartModel(rows,['turnover'],'1Y',false).paths[0].path.match(/M/g)||[]).length,2);
// The legacy source series is retained as raw data, never used in the regular-close panel.
const legacy=JSON.parse(read('tests/fixtures/korean_turnover_20261029.json'));
assert.equal(legacy.marketTurnover.markets.KOSPI.rows.at(-1).date,'2026-10-28');
assert.equal(legacy.marketTurnover.markets.KOSPI.currentObservation.date,'2026-10-29');
assert.equal(legacy.marketTurnover.markets.KOSPI.currentObservation.turnover,249071.42);
assert.equal(legacy.marketTurnover.nxtObservation.turnover,134205);
const latest=JSON.parse(read('data/korea-market.json'));
for(const m of ['KOSPI','KOSDAQ']) {
  const history=latest.marketTurnover.markets[m].integratedHistory;
  if(history){
    assert(history.rows.length>0);
    assert.equal(history.rows.at(-1).date,history.coverage.end);
    for(const range of ['1M','3M','6M','1Y'])assert.equal(api.chartModel(history.rows,['turnover'],range,false).paths.length,1);
  }
}
const entry={
  market:'KR',date:'2027-01-04',sources:[{id:'a',title:'첫 출처 <A>',url:'https://example.com/a'},{id:'b',title:'두 번째 출처',url:'https://example.com/b'}],
  regularClosingTurnover:{date:'2027-01-04',scope:'krx-regular-market-close',observedAt:'2027-01-04T07:00:00Z',status:'reported-approximate',unit:'조원',markets:{KOSPI:16.1,KOSDAQ:5.1},sourceIds:['a','b']},
  reportedCloseFlow:{date:'2027-01-04',scope:'krx-market-close-reports',observedAt:'2027-01-04T07:00:00Z',status:'reported-provisional',summary:'테스트 문구 <예시>',sourceIds:['a','b']}
};
api.setData(latest);
const set=entries=>{ctx.window.TerminalBriefingData={entries};};
set([entry]);
const panel=api.marketTurnoverSection(),flow=api.dailyFlowSummary(),charts=api.flowSection();
for(const token of ['KRX 정규장','NXT 및 시간외 제외','2027-01-04','약 16.1조원','약 5.1조원','첫 출처 &lt;A&gt;','https://example.com/a'])assert(panel.includes(token),token);
for(const token of ['data-kr-chart','data-turnover-history','data-turnover-comparison','2026-10-29','NaN'])assert(!panel.includes(token),token);
assert(flow.includes('2027-01-04'));assert(flow.includes('테스트 문구 &lt;예시&gt;'));assert(flow.includes('잠정'));assert(!charts.includes('2027-01-04'));
assert(raw.includes('marketTurnoverSection()+dailyFlowSummary()'));
const missing=()=>{const html=api.marketTurnoverSection();assert(html.includes('최신 KRX 정규장 거래대금은 아직 확인되지'));assert(!html.includes('16.1'));assert(!html.includes('data-kr-chart'));};
api.setData(legacy);
for(const extra of [{scope:'krx-nxt'},{date:'2027-01-01'},{markets:{KOSPI:'16.1',KOSDAQ:5.1}},{sourceIds:['a','a']},{sourceIds:['a','unknown']}]){
  set([{...entry,regularClosingTurnover:{...entry.regularClosingTurnover,...extra}}]);missing();
}
set([entry,{market:'KR',date:'2027-01-05'}]);missing();assert(!api.dailyFlowSummary().includes('2027-01-04'));
set([{...entry,sources:[entry.sources[0],{...entry.sources[1],url:'javascript:alert(1)'}]}]);missing();
set([]);missing();
console.log('PASS KRX regular-market close only, source/date/scope validation, provisional flow separate, missing never uses legacy turnover; retained legacy raw data and chart math');
