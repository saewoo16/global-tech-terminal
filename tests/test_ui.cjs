const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const root=require('node:path').resolve(__dirname,'..'),html=fs.readFileSync(root+'/index.html','utf8'),script=html.match(/<script>\n([\s\S]*?)<\/script>/)[1];
const elements=new Map(),events=new Map();
function element(id){if(!elements.has(id))elements.set(id,{id,innerHTML:'',textContent:'',hidden:false,value:'',classList:{toggle(){}},append(...nodes){this.textContent+=nodes.map(n=>n.textContent||'').join('')},scrollIntoView(){}});return elements.get(id)}
class Chart{constructor(canvas,options){this.options=options;Chart.latest=this}destroy(){this.destroyed=true}}
const context={URL,Map,Set,Date,Number,String,Array,Math,console,Chart,window:{Chart,innerWidth:1200},fetch:()=>{throw new Error('Fetch must wait for DOMContentLoaded')},document:{readyState:'loading',getElementById:element,querySelectorAll:()=>[],addEventListener:(name,callback)=>events.set(name,callback),createElement:tag=>({tag,textContent:''}),createTextNode:text=>({textContent:text})}};
vm.createContext(context);vm.runInContext(script,context);let count=0;function test(name,fn){fn();count++;console.log('PASS',name)}function run(code){return vm.runInContext(code,context)}
test('optional Chart.js loads asynchronously while first-party UI can initialize',()=>{
 assert(events.has('DOMContentLoaded'));
 assert.match(html,/<script id="explorer-chart-library"[^>]+src="https:\/\/cdn\.jsdelivr\.net\/[^"]+" async><\/script>/);
 assert.doesNotMatch(html,/<script[^>]+src="https:\/\/[^"]+"[^>]+defer/);
});
test('rejects non-web citation protocols and credentials',()=>{for(const url of ['javascript:alert(1)','data:text/html,<script>','file:///etc/passwd','https://user:pass@example.com','//example.com'])assert.equal(run(`safeUrl(${JSON.stringify(url)})`),'');assert.equal(run("safeUrl('https://example.com/report?a=1&b=2')"),'https://example.com/report?a=1&b=2')});
test('strict numeric and calendar validation',()=>{assert.equal(run("numeric(' ')"),false);assert.equal(run('numeric(null)'),false);assert.equal(run("dateOnly('2026-02-30')"),'');assert.equal(run("dateOnly('2024-02-29T00:00:00Z')"),'2024-02-29')});
test('sorts and deduplicates valid quotes without mutating raw data',()=>assert.equal(run("JSON.stringify(validPrices({prices:[['2020-01-03',4],['2020-01-01',2],['2020-01-03',5],['2020-02-30',7],['',9],['2020-01-02',null],['2020-01-04',-1]]}))"),'[["2020-01-01",2],["2020-01-03",5]]'));
run("chosen={symbol:'TEST',ticker:'TEST',name:'Test',sector:'Tech',category:'Test',country:'미국'};COMPANIES=[chosen];MARKET={stocks:{TEST:{prices:[['2020-01-02',10],['2020-01-03',11]],priceCurrency:'USD'}}};range='3M';render()");
test('3-month chart anchors to stale latest quote, not wall clock',()=>{assert.equal(element('chart').hidden,false);assert.equal(element('chartempty').hidden,true);assert.equal(Chart.latest.options.data.labels.join(','),'2020-01-02,2020-01-03');assert.match(element('chartnote').textContent,/2020-01-03/);assert.match(element('chartnote').textContent,/일 경과/)});
test('CDN absent leaves a dated native chart; late availability can restore interactivity',()=>{
 context.window.Chart=undefined;run('renderChart()');
 assert.equal(element('chart').hidden,true);assert.equal(element('chartempty').hidden,false);
 assert.match(element('chartempty').innerHTML,/<polyline/);
 assert.match(element('chartempty').innerHTML,/2020-01-02 → 2020-01-03/);
 assert.match(element('chartstat').textContent,/10%/);
 context.window.Chart=Chart;run('renderChart()');
 assert.equal(element('chart').hidden,false);assert.equal(element('chartempty').hidden,true);
});
test('all four performance cards retained with truthful missing history',()=>{const cards=element('performance').innerHTML;assert.equal((cards.match(/class="perfcard"/g)||[]).length,4);assert.match(cards,/>1일</);assert.match(cards,/>1주</);assert.match(cards,/>1개월</);assert.match(cards,/>1년</);assert.match(cards,/\+10.00%/);assert.match(cards,/기준 시세 부족/)});
run("renderFinancials({quarters:[{date:'2026-06-30',revenue:100,operatingIncome:null,sourceUrl:'https://example.com/report?a=1&b=2',sourceType:'filing',verifiedAt:'2026-10-17'}],reportingCurrency:'EUR',finSource:'Published quarterly revenue; operating profit only H1/FY (not disclosed quarterly)',financialUpdated:'2026-10-13T12:00:00Z',updated:'2026-10-16T22:00:00Z'})");
test('financial timestamp never falls back to quote updated timestamp',()=>{assert.match(element('finmsg').textContent,/실적 수집 2026-10-13/);assert.doesNotMatch(element('finmsg').textContent,/2026-10-16/)});
test('undisclosed operating profit explained rather than guessed',()=>{assert.match(element('quarters').innerHTML,/미공시/);assert.match(element('finmsg').textContent,/EBITDA·세전이익 등 다른 지표로 대체하지 않습니다/);assert.doesNotMatch(element('quarters').innerHTML,/0.0%/)});
test('quarter citation has safe external link and row-specific verification date',()=>{assert.match(element('quarters').innerHTML,/href="https:\/\/example.com\/report\?a=1&amp;b=2"/);assert.match(element('quarters').innerHTML,/noopener noreferrer/);assert.match(element('quarters').innerHTML,/확인 2026-10-17/)});
run("renderFinancials({quarters:[{date:'2026-06-30',revenue:100,operatingIncome:0}],financialUpdated:'2026-10-16',financialVerifiedAt:'2026-10-13'})");
test('verification date takes precedence without claiming all rows checked',()=>{assert.match(element('finmsg').textContent,/최근 출처 확인 2026-10-13 \(분기별 확인일 참조\)/);assert.doesNotMatch(element('finmsg').textContent,/2026-10-16/)});
test('zero operating income is valid, not missing',()=>{assert.match(element('quarters').innerHTML,/>0%<\/td>/);assert.doesNotMatch(element('quarters').innerHTML,/영업이익 데이터를 확보하지 못했습니다/)});
run("renderFinancials({updated:'2026-10-16',quarters:[{date:'2026-06-30',revenue:100,operatingIncome:10}]})");
test('unknown financial timestamp stays unknown',()=>{assert.match(element('finmsg').textContent,/실적 수집일 미확인/);assert.doesNotMatch(element('finmsg').textContent,/2026-10-16/)});
run("renderFinancials({financialStatus:'missing',financialNote:'공급사에서 분기 데이터를 제공하지 않습니다.'})");
test('financial missing state uses supplied Korean note',()=>assert.match(element('quarters').innerHTML,/공급사에서 분기 데이터를 제공하지 않습니다/));
run("MARKET.stocks.TEST={priceStatus:'missing',priceNote:'거래소 코드 변경으로 시세 확인이 필요합니다.'};renderChart()");
test('missing chart displays supplied reason and external action',()=>{assert.equal(element('chart').hidden,true);assert.equal(element('chartempty').hidden,false);assert.match(element('chartempty').innerHTML,/거래소 코드 변경/);assert.match(element('chartempty').innerHTML,/TradingView 원본 보기/)});
run("MARKET.stocks.TEST={prices:[['2020-01-03',11]]};range='ALL';renderChart()");
test('single quote has specific insufficiency explanation',()=>assert.match(element('chartempty').innerHTML,/유효한 시세가 1개/));
run("MARKET.stocks.TEST={prices:[['2020-01-02',10],['2020-01-03',11]]};window.Chart=null;renderChart()");
test('library block renders the native chart instead of a missing-data message',()=>assert.match(element('chartempty').innerHTML,/<polyline/));run('window.Chart=Chart');
run("renderFinancials({quarters:[{date:'<img src=x onerror=alert(1)>',revenue:12,operatingIncome:2,sourceUrl:'javascript:alert(1)',source:'<svg onload=alert(1)>'}],finSource:'<script>alert(1)</script>'})");
test('untrusted financial data is escaped and invalid link omitted',()=>{assert.doesNotMatch(element('quarters').innerHTML,/<img|<svg|javascript:/);assert.match(element('quarters').innerHTML,/&lt;img/);assert.match(element('quarters').innerHTML,/개별 링크 미확인/)});
run("chosen.name='<img src=x>';chosen.ticker='X\" onclick=\"alert(1)';chosen.category='<svg>';listing();render()");
test('company names and attributes escaped',()=>{assert.doesNotMatch(element('stocks').innerHTML,/<img|<svg/);assert.match(element('stocks').innerHTML,/&lt;img/);assert.match(element('pills').innerHTML,/&quot;/)});
const companies=JSON.parse(fs.readFileSync(root+'/data/companies.json')),market=JSON.parse(fs.readFileSync(root+'/data/market.json'));context.realCompanies=companies;context.realMarket=market;run('COMPANIES=realCompanies;MARKET=realMarket');
test('every real catalog symbol renders without an exception',()=>{for(const symbol of [...new Set(companies.map(r=>r.symbol))]){run(`chosen=COMPANIES.find(r=>r.symbol===${JSON.stringify(symbol)});render()`);assert.equal((element('performance').innerHTML.match(/class="perfcard"/g)||[]).length,4)}});
test('hidden states cannot be overridden by placeholder display rule',()=>assert.match(html,/\[hidden\]\{display:none!important\}/));
run("chosen=COMPANIES.find(r=>r.symbol==='HKEX:1888');render()");
test('semiannual figures display separately without invented quarters',()=>{assert.equal(element('reportedperiods').hidden,false);assert.match(element('reportedperiods').innerHTML,/별도 공시: 반기/);assert.match(element('reportedperiods').innerHTML,/2026-01-01 ~ 2026-06-30/);assert.match(element('reportedperiods').innerHTML,/14,903.8/);assert.doesNotMatch(element('quarters').innerHTML,/14,903/)});
run("chosen=COMPANIES.find(r=>r.symbol==='NYSE:DD');render()");
test('issuer undisclosed operating income is explicit',()=>{assert.match(element('quarters').innerHTML,/미공시/);assert.match(element('finmsg').textContent,/연결 GAAP 영업이익 소계/)});
console.log('\n'+count+' focused UI checks passed; '+new Set(companies.map(r=>r.symbol)).size+' catalog symbols rendered.');

run("chosen.business='Atlas 데이터 플랫폼';render()");
test('optional company business description is visible without changing other companies',()=>{assert.equal(element('business').textContent,'Atlas 데이터 플랫폼');assert.equal(element('business').hidden,false);run("delete chosen.business;render()");assert.equal(element('business').hidden,true)});
run("chosen={symbol:'TEST',ticker:'TEST',name:'Test',sector:'Tech',category:'Test',country:'미국'};COMPANIES=[chosen];MARKET={fx:1345.74,stocks:{TEST:{marketCapUSD:1000000,marketCapUpdated:'2026-11-02T22:30:48+00:00',prices:[['2026-11-04',10]],priceCurrency:'USD'}}};render()");
test('cap observation never becomes certified latest-session cap or FX',()=>{assert.match(element('capinfo').innerHTML,/공급자 관측 2026-11-02/);assert.match(element('capinfo').innerHTML,/종가 기준 미확인/);assert.match(element('capinfo').innerHTML,/환율 기준일 미확인/);assert.doesNotMatch(element('capinfo').innerHTML,/2026-11-04/)});
run("MARKET.stocks.TEST.marketCapAsOf='2026-11-03';MARKET.fxAsOf='2026-11-02';render()");
test('certified cap and FX dates remain independently displayed',()=>{assert.match(element('capinfo').innerHTML,/시가총액 기준 2026-11-03/);assert.match(element('capinfo').innerHTML,/환율 기준 2026-11-02/);assert.doesNotMatch(element('capinfo').innerHTML,/종가 기준 미확인|환율 기준일 미확인/)});

const legalFilingOverlay=JSON.parse(fs.readFileSync(root+'/data/financial_backfill_zlatest_20261116_kr_official.json'));
context.legalFilingOverlay=legalFilingOverlay;
test('verified 14-issuer DART overlay updates only quarters, without transmitting new market blob',()=>{
  const seededStocks={...market.stocks};
  for(const [symbol,record] of Object.entries(legalFilingOverlay.companies)){
    const existing=market.stocks[symbol];
    const q=record.quarters[0];
    // Pin an older financial baseline even after future issuers publish newer quarters.
    seededStocks[symbol]={...existing,reportingCurrency:'KRW',quarters:[
      {...q,observedAt:'2026-11-01T00:00:00Z',revenue:1,operatingIncome:0},
      ...['2026-06-30','2026-03-31','2025-12-31'].map(date=>({date,revenue:1,operatingIncome:0}))
    ]};
  }
  context.seededMarket={...market,stocks:seededStocks};
  const overlay=run('mergeOfficialFilingOverlay(seededMarket,legalFilingOverlay)');
  assert.equal(Object.keys(legalFilingOverlay.companies).length,14);
  for(const [symbol,record] of Object.entries(legalFilingOverlay.companies)){
    const before=seededStocks[symbol],after=overlay.stocks[symbol],q=record.quarters[0];
    assert.deepEqual(after.quarters[0],q);
    assert.equal(after.quarters.length,4);
    for(const key of Object.keys(before).filter(k=>k!=='quarters'&&!k.startsWith('fin')))assert.strictEqual(after[key],before[key],symbol+' '+key);
    for(const prior of before.quarters.filter(x=>x.date!==q.date))if(after.quarters.some(x=>x.date===prior.date))assert.equal(after.quarters.find(x=>x.date===prior.date),prior);
  }
  for(const [symbol,base] of Object.entries(market.stocks))if(!legalFilingOverlay.companies[symbol])assert.equal(overlay.stocks[symbol],base);
  for(const key of Object.keys(market).filter(k=>k!=='stocks'))assert.equal(overlay[key],market[key]);
  assert.equal(run('mergeOfficialFilingOverlay(realMarket,null)'),market);
});
test('optional filing overlay ignores malformed or untrusted data and never replaces newer filings',()=>{
  const key='KRX:005930',r=legalFilingOverlay.companies[key],q=r.quarters[0];
  const bad={...r,quarters:[{...q,revenue:null},{...q,sourceUrl:'https://dart.fss.or.kr.bad.example/report'},{...q,preliminary:true}]};
  context.badOverlay={companies:{[key]:bad}};
  assert.equal(run('mergeOfficialFilingOverlay(realMarket,badOverlay)'),market);
  const futureRevision={...q,observedAt:'2026-11-17T10:00:00Z',revenue:q.revenue+1};
  const seeded=context.seededMarket;
  context.revisedMarket={...seeded,stocks:{...seeded.stocks,[key]:{...seeded.stocks[key],quarters:[futureRevision,...seeded.stocks[key].quarters.slice(1)]}}};
  assert.equal(run('mergeOfficialFilingOverlay(revisedMarket,legalFilingOverlay)').stocks[key].quarters[0],futureRevision);
});

const taiwanClose=JSON.parse(fs.readFileSync(root+'/data/explorer-taiwan-open-close.json'));
context.taiwanClose=taiwanClose;
test('official Taiwan close covers all 32 listed Explorer securities on one dated session',()=>{
  assert.equal(taiwanClose.sessionDate,'2026-11-16');
  const symbols=[...new Set(companies.filter(x=>/^(TWSE|TPEX):/.test(x.symbol)).map(x=>x.symbol))].sort();
  assert.deepEqual(Object.keys(taiwanClose.quotes).sort(),symbols);
  assert.equal(symbols.filter(x=>x.startsWith('TWSE:')).length,30);
  assert.equal(symbols.filter(x=>x.startsWith('TPEX:')).length,2);
  for(const symbol of symbols){
    const q=taiwanClose.quotes[symbol];
    assert.ok(q.close>0);
    assert.equal(q.currency,'TWD');
    assert.equal(q.asOf,'2026-11-16');
    assert.equal(q.basis,'regular_close_unadjusted');
    assert.equal(run('explorerTaiwanClose('+JSON.stringify(symbol)+', "2026-11-13", taiwanClose)').q,q);
  }
  assert.equal(taiwanClose.quotes['TWSE:2408'].close,340);
  assert.equal(taiwanClose.quotes['TPEX:8299'].close,1515);
});
test('official Taiwan raw close is shown separately with license attribution and no performance changes',()=>{
  run("COMPANIES=realCompanies;MARKET=realMarket;chosen=COMPANIES.find(r=>r.symbol==='TWSE:2408');EXPLORER_TAIWAN_CLOSES=null;render()");
  const oldPerformance=element('performance').innerHTML, oldChart=Chart.latest.options.data.labels.join(',');
  run('EXPLORER_TAIWAN_CLOSES=taiwanClose;render()');
  assert.equal(element('latest-close-label').textContent,'거래소 정규장 종가 · 비조정');
  assert.equal(element('last').textContent,'340 TWD');
  assert.match(element('priceinfo').textContent,/2026-11-16 대만 거래소 정규장 종가 · 차트·수익률은 조정종가 이력 2026-11-16 기준/);
  assert.match(element('priceinfo').textContent,/Securities and Futures Bureau.*2026.*Stock daily transaction information.*Open Government Data License, version 1\.0/);
  assert.equal(element('performance').innerHTML,oldPerformance);
  assert.equal(Chart.latest.options.data.labels.join(','),oldChart);
  run("chosen=COMPANIES.find(r=>r.symbol==='KRX:009150');render()");
  assert.equal(element('latest-close-label').textContent,'최근 조정종가');
  assert.doesNotMatch(element('priceinfo').textContent,/대만 공표 종가/);
});
test('invalid, missing or older quote overlay cannot replace the adjusted-close display',()=>{
  assert.equal(run("explorerTaiwanClose('TWSE:2408','2026-11-17',taiwanClose)"),null);
  assert.equal(run("explorerTaiwanClose('TWSE:2408','2026-11-13',null)"),null);
  context.badTaiwan={...taiwanClose,quotes:{'TWSE:2408':{...taiwanClose.quotes['TWSE:2408'],close:'999'}}};
  assert.equal(run("explorerTaiwanClose('TWSE:2408','2026-11-13',badTaiwan)"),null);
  context.badTaiwan={...taiwanClose,sources:{twse:{...taiwanClose.sources.twse,datasetUrl:'javascript:alert(1)'}}};
  assert.equal(run("explorerTaiwanClose('TWSE:2408','2026-11-13',badTaiwan)"),null);
});
