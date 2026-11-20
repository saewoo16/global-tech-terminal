const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const root=path.resolve(__dirname,'..'),raw=fs.readFileSync(root+'/assets/overseas-etf.js','utf8'),html=fs.readFileSync(root+'/index.html','utf8');
const ctx={URL,Date,Number,String,Math,Array,console,document:{readyState:'loading',addEventListener(){}},window:{}};vm.createContext(ctx);vm.runInContext(raw.replace('window.TerminalOverseasETF={returns,series,safeURL,representatives,representativeSources,aggregateCandles,displayCandles,candleLabel,candleStatus}','window.TerminalOverseasETF={returns,series,safeURL,representatives,representativeSources,selectionSources,detail,setSelected:s=>selected=s,esc,dailyReturn,listReturn,filtered,sessionOf,freshness,statusLabel,widgetSymbol,widgetProviderLink,providerPanel,mountProviderPanel,setData:p=>payload=p,setSort:s=>sort=s,setPeriod:p=>period=p,setCandle:x=>candleKind=x}'),ctx);const a=ctx.window.TerminalOverseasETF;
assert(html.includes('id="overseas-etf-tab"'));assert(html.includes('해외 업종별/테마별 차트'));assert(html.includes('id="overseas-etf-panel"'));
assert.equal(a.safeURL('javascript:alert(1)'),'#');assert.equal(a.safeURL('https://example.com/a'),'https://example.com/a');assert.equal(a.esc('<script>'),'&lt;script&gt;');
const f={daily:[{date:'2026-07-20',open:90,high:110,low:80,close:100},{date:'2026-09-18',open:115,high:125,low:114,close:120},{date:'2026-10-20',open:125,high:134,low:124,close:132}],intraday:{date:'2026-10-20',points:[{time:'09:00',price:130},{time:'09:03',price:132}]}};
assert(Math.abs(a.returns(f)-10)<1e-8);assert.equal(a.returns({daily:[]}),null);assert.equal(a.series(f).length,3);assert.equal(a.series(f)[0].date,'2026-07-20');
assert(raw.includes("{cache:'no-store'}"));assert(raw.includes('p.high'));assert(raw.includes('p.low'));assert(raw.includes('onpointermove'));assert(raw.includes('거래일 종가가 있는 일봉만 표시'));
console.log('PASS ETF navigation, OHLC/intraday separation, calendar ranges, real price returns, source URL/XSS safety, cache refresh, pointer inspection');

const sample={funds:[{code:'low',category:'Low',daily:[{date:'2026-09-20',close:50},{date:'2026-10-21',close:100},{date:'2026-10-22',close:90}]},{code:'high',category:'High',daily:[{date:'2026-09-20',close:200},{date:'2026-10-21',close:100},{date:'2026-10-22',close:120}]},{code:'missing',category:'Missing',daily:[]}]};
a.setData(sample);const before=JSON.stringify(sample);assert.equal(a.filtered()[0].code,'high');assert.equal(a.filtered().at(-1).code,'missing');assert(Math.abs(a.listReturn(sample.funds[1])-20)<1e-8);a.setSort('month');assert.equal(a.filtered()[0].code,'low');assert(Math.abs(a.listReturn(sample.funds[1])+40)<1e-8);a.setSort('day');assert.equal(a.filtered()[0].code,'high');assert.equal(JSON.stringify(sample),before);assert.equal(a.dailyReturn({daily:[{close:0},{close:100}]}),null);assert.equal(a.dailyReturn({daily:[{close:100}]}),null);assert.equal(a.dailyReturn({daily:[{close:100},{close:null}]}),null);assert(raw.includes("$('us-etf-sort').value=sort"));assert(html.indexOf('<option value="day">1일 수익률순')<html.indexOf('<option value="month">1달 수익률순'));
console.log('PASS ETF daily default, global numerical sort, missing last, month opt-in, original data preserved and reload default synchronized');


assert(html.includes('<option value="week">1주일 수익률순'));assert(!html.includes('<option value="aum">'));assert(!html.includes('<option value="name">'));
const wf={funds:[{code:'week',category:'Week',daily:[{date:'2026-10-16',close:100},{date:'2026-10-22',close:200},{date:'2026-10-23',close:150}]},{code:'day',category:'Day',daily:[{date:'2026-10-16',close:200},{date:'2026-10-22',close:100},{date:'2026-10-23',close:120}]},{code:'missing',category:'Missing',daily:[]}]};a.setData(wf);a.setSort('week');assert.equal(a.filtered()[0].code,'week');assert.equal(a.listReturn(wf.funds[0]),50);assert.equal(a.filtered().at(-1).code,'missing');a.setSort('day');assert.equal(a.filtered()[0].code,'day');
assert(raw.includes('(ET)'));assert(raw.includes('USD'));assert(!raw.includes('KRX'));assert(!raw.includes('aumKRW'));assert(raw.includes("'#overseas-etf'"));assert(raw.includes('편입비중 상위 3종목'));
assert.equal(a.representatives({holdings:{status:'unverified',top5:[{name:'unverified'}]}}),'');const weighted={holdings:{status:'verified',asOf:'2026-10-22',top5:[{name:'fourth',weightPct:1},{name:'<unsafe>',weightPct:4},{name:'third',weightPct:2},{name:'second',weightPct:3}]}};const unchanged=JSON.stringify(weighted);assert.equal(a.representatives(weighted),'<span class="etf-representatives">(&lt;unsafe&gt; / second / third)</span>');assert.equal(JSON.stringify(weighted),unchanged);assert(a.representativeSources(weighted).includes('2026-10-22'));
console.log('PASS overseas isolated navigation, USD/ET display, weekly sorting, dated source holdings');

assert.equal(a.returns({daily:[{date:'2026-02-27',close:100},{date:'2026-03-03',close:200},{date:'2026-03-31',close:110}]}).toFixed(2),'10.00');

assert.equal(a.representatives({holdings:{status:"verified",top5:[{name:"Apple",marketCapUSD:1e12}]}}),'');
assert.equal(a.representatives({holdings:{status:"verified",top5:[{name:"A",weightPct:3},{name:"B",weightPct:2},{name:"C",weightPct:null}]}}),'');
const snapshot=JSON.parse(fs.readFileSync(root+'/data/overseas_etf_charts.json','utf8'));
for(const fund of snapshot.funds){const reps=a.representatives(fund);assert(reps.startsWith('<span class="etf-representatives">('));assert.equal(reps.split(' / ').length,3);const sorted=[...fund.holdings.top5].sort((a,b)=>b.weightPct-a.weightPct).slice(0,3);for(const h of sorted)assert(reps.includes(a.esc(h.name||h.ticker)));}
console.log('PASS all 38 overseas ETFs render exactly three actual-weight-ranked holdings; missing weights never fall back to market cap');
assert(raw.includes("${esc(f.code)} (${esc(f.name)})"));

const verified={entry:{date:'2026-11-17',sessionStatus:'closed',sessionVerification:{exchangeDate:'2026-11-17'}}};
assert.equal(a.sessionOf(verified),'2026-11-17');
assert.equal(a.sessionOf({entry:{...verified.entry,sessionStatus:'open'}}),null);
assert.equal(a.sessionOf({entry:{...verified.entry,sessionVerification:{exchangeDate:'2026-11-16'}}}),null);
assert.deepEqual({...a.freshness(snapshot.funds,a.sessionOf(verified))},{target:'2026-11-17',latest:'2026-11-13',count:38,current:0});
assert(a.statusLabel(snapshot.funds,a.sessionOf(verified)).includes('0/38'));
assert(a.statusLabel(snapshot.funds,null).includes('대조 미확인'));
assert(a.statusLabel(snapshot.funds,'2026-11-13').includes('38/38'));
assert.doesNotMatch(html,/us-etf-close-note-20261117/);
console.log('PASS closed-session provenance, actual per-fund staleness, historical label and direct issuer link');

const approved=new Set(snapshot.funds.map(f=>a.widgetSymbol(f.code)));
assert.equal(approved.size,38);
assert.equal(a.widgetSymbol('XLK'),'AMEX:XLK'); assert.equal(a.widgetSymbol('SMH'),'NASDAQ:SMH'); assert.equal(a.widgetSymbol('IGV'),'CBOE:IGV');
assert.equal(a.widgetProviderLink(a.widgetSymbol('UNKNOWN')),null);

for(const f of snapshot.funds){
 const part=a.providerPanel(f),cboe=a.widgetSymbol(f.code).startsWith('CBOE:');
 assert.match(part,cboe?/Quotelinks ETF 캔들/:/TradingView ETF 캔들/);
 assert.match(part,cboe?/정규장 종가 기반/:/Cboe One 지연 시세/);
 assert.match(part,/최신 표시일은 차트에서 확인/);
 assert.match(part,/id="us-etf-widget-view"/);
 assert.doesNotMatch(part,/data-us-etf-external-interval=|<button/);
 assert.doesNotMatch(part,/<iframe|<script|s3\.tradingview/);
}
assert.equal(a.providerPanel({code:'<script>'}),'');
const host=fs.readFileSync(root+'/assets/overseas-etf-widget.html','utf8');
const script=fs.readFileSync(root+'/assets/overseas-etf-widget.js','utf8');
assert(host.includes('Content-Security-Policy'));
assert(!host.includes('allow-same-origin'));
assert.match(host,/connect-src https:\/\/www\.quotelinks\.com/);
const mk=()=>({children:[],dataset:{},hidden:true,append(...c){this.children.push(...c);}});
function widget(query){
 const e={tv:mk(),credit:mk(),chart:mk(),note:mk(),ql:mk()};
 const doc={getElementById:id=>e[id],createElement:tag=>({...mk(),tag})};
 vm.runInNewContext(script,{URLSearchParams,location:{search:query},document:doc});
 return e;
}
for(const unit of ['D','W','M']){
 const e=widget('?symbol=AMEX%3AXLK&interval='+unit);
 assert.equal(e.tv.children.length,1);
 assert.equal(e.tv.children[0].src,'https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js');
 const settings=JSON.parse(e.tv.children[0].textContent);
 assert.equal(settings.interval,unit);assert.equal(settings.style,'1');
 assert.equal(settings.allow_symbol_change,false);assert.equal(settings.timezone,'America/New_York');
 assert.equal(e.credit.children[0].href,'https://www.tradingview.com/symbols/AMEX-XLK/');
}
assert.equal(JSON.parse(widget('?symbol=NASDAQ%3ASMH&interval=bad').tv.children[0].textContent).interval,'D');
for(const code of ['IGV','IYT','ITA']){
 const e=widget('?symbol=CBOE%3A'+code);
 assert.equal(e.tv.children.length,0);
 assert.equal(e.ql.children[0].dataset.symbol,code);
 assert.equal(e.ql.children[0].dataset.type,'candles');
 assert.equal(e.ql.children[0].children[0].href,'https://www.quotelinks.com/etfs/'+code.toLowerCase()+'.html');
 assert.equal(e.ql.children[0].children[2].href,'https://www.quotelinks.com/');
 assert.equal(e.ql.children[1].src,'https://www.quotelinks.com/widgets/stockchart.js');
}
const bad=widget('?symbol=AMEX%3AUNKWN');
assert.equal(bad.tv.children.length+bad.ql.children.length,0);
console.log('PASS all 38 external symbols, tab-isolated D/W/M Advanced Chart, Quotelinks end-of-day fallback, and no unknown symbols');

const mounted=[];
const widgetTarget={textContent:'',replaceChildren(...nodes){mounted.push(nodes);}};
ctx.document.getElementById=id=>id==='us-etf-widget-view'?widgetTarget:null;
ctx.document.createElement=tag=>({tag,style:{},setAttribute(key,val){this[key]=val;}});
ctx.window.location={hash:'#explorer'};
a.mountProviderPanel({code:'XLK'});assert.equal(mounted.length,0);
ctx.window.location.hash='#overseas-etf';
a.setPeriod('3');
for(const [kind,v] of [['daily','D'],['weekly','W'],['monthly','M']]){
 a.setCandle(kind);a.mountProviderPanel({code:'XLK'});
 const last=mounted.at(-1)[0],url=new URL(last.src,'https://local.test');
 assert.equal(last.tag,'iframe');assert.equal(url.origin,'https://local.test');
 assert.equal(url.searchParams.get('symbol'),'AMEX:XLK');
 assert.equal(url.searchParams.get('interval'),v);
 assert.equal(last.referrerpolicy,'no-referrer');assert.doesNotMatch(last.sandbox,/allow-same-origin|forms|top-navigation/);
}
a.mountProviderPanel({code:'IGV'});
assert.match(mounted.at(-1)[0].src,/symbol=CBOE%3AIGV/);
const count=mounted.length;a.mountProviderPanel({code:'UNKNOWN'});assert.equal(mounted.length,count);
a.setPeriod('day');a.mountProviderPanel({code:'XLK'});assert.equal(mounted.length,count);
assert.match(widgetTarget.textContent,/보관 장중/);
assert.match(raw,/마지막 실제 종가/);
assert.doesNotMatch(raw,/data-etf-period|data-etf-candle/);
assert.ok(raw.indexOf('id="us-etf-plot"')<raw.indexOf('1달 수익률</small>'));
assert.ok(raw.indexOf('ETF 정보·시세 출처</summary>')<raw.indexOf('${issuerSessionNote(f)}'));
console.log('PASS automatic tab-scoped vendor mounting, D/W/M mapping, isolation, native dated fallback, no automatic intraday vendor.');
