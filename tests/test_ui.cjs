const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const root=require('node:path').resolve(__dirname,'..'),html=fs.readFileSync(root+'/index.html','utf8'),script=html.match(/<script>\n([\s\S]*?)<\/script>/)[1];
const elements=new Map(),events=new Map();
function element(id){if(!elements.has(id))elements.set(id,{id,innerHTML:'',textContent:'',hidden:false,value:'',classList:{toggle(){}},append(...nodes){this.textContent+=nodes.map(n=>n.textContent||'').join('')},scrollIntoView(){}});return elements.get(id)}
class Chart{constructor(canvas,options){this.options=options;Chart.latest=this}destroy(){this.destroyed=true}}
const context={URL,Map,Set,Date,Number,String,Array,Math,console,Chart,window:{Chart,innerWidth:1200},fetch:()=>{throw new Error('Fetch must wait for DOMContentLoaded')},document:{readyState:'loading',getElementById:element,querySelectorAll:()=>[],addEventListener:(name,callback)=>events.set(name,callback),createElement:tag=>({tag,textContent:''}),createTextNode:text=>({textContent:text})}};
vm.createContext(context);vm.runInContext(script,context);let count=0;function test(name,fn){fn();count++;console.log('PASS',name)}function run(code){return vm.runInContext(code,context)}
test('initializes only after deferred Chart.js execution',()=>assert(events.has('DOMContentLoaded')));
test('rejects non-web citation protocols and credentials',()=>{for(const url of ['javascript:alert(1)','data:text/html,<script>','file:///etc/passwd','https://user:pass@example.com','//example.com'])assert.equal(run(`safeUrl(${JSON.stringify(url)})`),'');assert.equal(run("safeUrl('https://example.com/report?a=1&b=2')"),'https://example.com/report?a=1&b=2')});
test('strict numeric and calendar validation',()=>{assert.equal(run("numeric(' ')"),false);assert.equal(run('numeric(null)'),false);assert.equal(run("dateOnly('2026-02-30')"),'');assert.equal(run("dateOnly('2024-02-29T00:00:00Z')"),'2024-02-29')});
test('sorts and deduplicates valid quotes without mutating raw data',()=>assert.equal(run("JSON.stringify(validPrices({prices:[['2020-01-03',4],['2020-01-01',2],['2020-01-03',5],['2020-02-30',7],['',9],['2020-01-02',null],['2020-01-04',-1]]}))"),'[["2020-01-01",2],["2020-01-03",5]]'));
run("chosen={symbol:'TEST',ticker:'TEST',name:'Test',sector:'Tech',category:'Test',country:'미국'};COMPANIES=[chosen];MARKET={stocks:{TEST:{prices:[['2020-01-02',10],['2020-01-03',11]],priceCurrency:'USD'}}};range='3M';render()");
test('3-month chart anchors to stale latest quote, not wall clock',()=>{assert.equal(element('chart').hidden,false);assert.equal(element('chartempty').hidden,true);assert.equal(Chart.latest.options.data.labels.join(','),'2020-01-02,2020-01-03');assert.match(element('chartnote').textContent,/2020-01-03/);assert.match(element('chartnote').textContent,/일 경과/)});
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
test('library loading failure distinct from missing price data',()=>assert.match(element('chartempty').innerHTML,/차트 라이브러리를 불러오지 못했습니다/));run('window.Chart=Chart');
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
