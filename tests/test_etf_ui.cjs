const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const root=path.resolve(__dirname,'..'),raw=fs.readFileSync(root+'/assets/korean-etf.js','utf8'),html=fs.readFileSync(root+'/index.html','utf8');
const ctx={URL,Date,Number,String,Math,Array,console,document:{readyState:'loading',addEventListener(){}},window:{}};vm.createContext(ctx);vm.runInContext(raw.replace('window.TerminalETF={returns,series,safeURL,representatives,representativeSources}','window.TerminalETF={returns,series,safeURL,representatives,representativeSources,selectionSources,detail,setSelected:s=>selected=s,esc,dailyReturn,listReturn,filtered,setData:p=>payload=p,setSort:s=>sort=s,setPeriod:p=>period=p}'),ctx);const a=ctx.window.TerminalETF;
assert(html.includes('id="etf-tab"'));assert(html.includes('국내 업종별/테마별 차트'));assert(html.includes('id="etf-panel"'));
assert.equal(a.safeURL('javascript:alert(1)'),'#');assert.equal(a.safeURL('https://example.com/a'),'https://example.com/a');assert.equal(a.esc('<script>'),'&lt;script&gt;');
const f={daily:[{date:'2026-07-20',open:90,high:110,low:80,close:100},{date:'2026-09-18',close:120},{date:'2026-10-20',close:132}],intraday:{date:'2026-10-20',points:[{time:'09:00',price:130},{time:'09:03',price:132}]}};
assert(Math.abs(a.returns(f)-10)<1e-8);assert.equal(a.returns({daily:[]}),null);a.setPeriod('day');assert.equal(a.series(f).length,2);assert.equal(a.series(f)[0].label,'09:00');assert.equal(a.series({daily:f.daily}).length,0,'Never resample daily data to fake intraday');a.setPeriod('3');assert.equal(a.series(f).length,3);
assert(raw.includes("{cache:'no-store'}"));assert(raw.includes('p.high'));assert(raw.includes('p.low'));assert(raw.includes('onpointermove'));assert(raw.includes('무')||raw.includes('수집된 실제 장중'));
console.log('PASS ETF navigation, OHLC/intraday separation, calendar ranges, real price returns, source URL/XSS safety, cache refresh, pointer inspection');

assert(!raw.includes("<small>${esc(f.name)} · ${esc(f.code)}</small>"));assert(!raw.includes("<h3>${esc(f.name)} <small"));assert(raw.includes("종목코드 ${esc(f.code)}"));const representative={representatives:{label:"ETF 내 시총 상위",members:[{name:"삼성전기"},{name:"대덕전자"},{name:"<script>"}]}};assert(a.representatives(representative).includes("삼성전기 / 대덕전자 / &lt;script&gt;"));assert(a.representatives(representative).includes("ETF 내 시총 상위"));assert.equal(a.representatives({}),"");

const sample={funds:[{code:'low',category:'Low',daily:[{date:'2026-09-20',close:50},{date:'2026-10-21',close:100},{date:'2026-10-22',close:90}]},{code:'high',category:'High',daily:[{date:'2026-09-20',close:200},{date:'2026-10-21',close:100},{date:'2026-10-22',close:120}]},{code:'missing',category:'Missing',daily:[]}]};
a.setData(sample);const before=JSON.stringify(sample);assert.equal(a.filtered()[0].code,'high');assert.equal(a.filtered().at(-1).code,'missing');assert(Math.abs(a.listReturn(sample.funds[1])-20)<1e-8);a.setSort('month');assert.equal(a.filtered()[0].code,'low');assert(Math.abs(a.listReturn(sample.funds[1])+40)<1e-8);a.setSort('day');assert.equal(a.filtered()[0].code,'high');assert.equal(JSON.stringify(sample),before);assert.equal(a.dailyReturn({daily:[{close:0},{close:100}]}),null);assert.equal(a.dailyReturn({daily:[{close:100}]}),null);assert.equal(a.dailyReturn({daily:[{close:100},{close:null}]}),null);assert(raw.includes("$('etf-sort').value=sort"));assert(html.indexOf('<option value="day">1일 수익률순')<html.indexOf('<option value="month">1달 수익률순'));
console.log('PASS ETF daily default, global numerical sort, missing last, month opt-in, original data preserved and reload default synchronized');

// The added fund shares the existing global return sort and keeps dated caveats folded.
const actual=JSON.parse(fs.readFileSync(root+'/data/korean_etf_charts.json','utf8'));
const dc=actual.funds.find(f=>f.code==='0222F0');assert(dc,'Domestic data-center ETF is present');
a.setData(actual);a.setSort('day');const ordered=a.filtered();assert.equal(ordered.length,actual.funds.length);assert.equal(ordered.filter(f=>f.code==='0222F0').length,1);
for(let i=1;i<ordered.length;i++)assert((a.dailyReturn(ordered[i-1])??-Infinity)>=(a.dailyReturn(ordered[i])??-Infinity),'All ETF themes retain global daily-return ordering');
a.setPeriod('12');assert(a.series(dc).every(p=>p.date>=dc.listedAt),'Never invent prelisting candles');
a.setPeriod('day');assert.equal(a.series(dc).length,dc.intraday.points.length,'Never fill sparse intraday observations');
assert.equal(a.selectionSources({}),'');
const malicious=a.selectionSources({selectionEvidence:{disclosure:'<script>alert(1)</script>',officialSourceUrl:'javascript:alert(1)',officialAum:{sourceUrl:'https://db-asset.com/funds/41900/details'}}});
assert(malicious.includes('&lt;script&gt;'));assert(!malicious.includes('<script>'));assert(malicious.includes('href="#"'));
const nodes={};ctx.document.getElementById=id=>nodes[id]||(nodes[id]={innerHTML:'',textContent:'',querySelectorAll:()=>[],querySelector:()=>({})});
a.setSelected('0222F0');a.setPeriod('3');a.detail();const detail=nodes['etf-detail'].innerHTML;
const folded=detail.indexOf('<details class="etf-sources">'),disclosure=detail.indexOf('<p class="etf-selection-disclosure">');
assert(folded>=0&&disclosure>folded);assert(disclosure<detail.indexOf('</details>'));
assert(!detail.slice(0,folded).includes('저거래량'));assert(detail.slice(folded).includes('저거래량'));
assert(detail.includes('시가총액 · 억원'));assert(detail.slice(folded).includes('2026-10-21'));assert(detail.slice(folded).includes('같은 날 AUM은 미확인'));
assert(detail.includes('https://db-asset.com/fund/download/13442'));assert(detail.includes('https://db-asset.com/funds/41900/details'));
console.log('PASS domestic data-center selection, global daily sort, real short/sparse series, folded liquidity/AUM disclosure and escaped source links');

assert(html.includes('<option value="week">1주일 수익률순'));assert(!html.includes('<option value="aum">'));assert(!html.includes('<option value="name">'));
a.setSort('week');assert.equal(a.filtered().at(-1)?.code===undefined,false);const weekly={funds:[{code:'up',category:'Up',daily:[{date:'2026-10-16',close:100},{date:'2026-10-22',close:200},{date:'2026-10-23',close:150}]},{code:'down',category:'Down',daily:[{date:'2026-10-16',close:200},{date:'2026-10-22',close:100},{date:'2026-10-23',close:120}]},{code:'none',category:'None',daily:[]}]};a.setData(weekly);assert.equal(a.filtered()[0].code,'up');assert.equal(a.filtered().at(-1).code,'none');assert.equal(a.listReturn(weekly.funds[0]),50);a.setSort('day');assert.equal(a.filtered()[0].code,'down');
console.log('PASS domestic daily/weekly/monthly only and displayed selected-period return');

assert.equal(a.returns({daily:[{date:'2026-02-27',close:100},{date:'2026-03-03',close:200},{date:'2026-03-31',close:110}]}).toFixed(2),'10.00');
