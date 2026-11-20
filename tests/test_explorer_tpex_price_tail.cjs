const assert=require('node:assert/strict'), fs=require('node:fs'), path=require('node:path'), vm=require('node:vm');
const root=path.resolve(__dirname,'..');
const json=f=>JSON.parse(fs.readFileSync(path.join(root,'data',f),'utf8'));
const tail=json('explorer-tpex-price-tail.json'), current=json('explorer-taiwan-open-close-latest.json');
// Pin the audited anchor so rolling the live archive forward never breaks this regression test.
const anchor=values=>({
  priceCurrency:'TWD', priceStatus:'complete',
  priceSessionBasis:'Completed regular-session adjusted close, independently cross-checked',
  lastPriceDate:'2026-11-16', close:values[2],
  prices:['2026-11-12','2026-11-13','2026-11-16'].map((d,i)=>[d,values[i]])
});
const market={stocks:{'TPEX:6488':anchor([622,630,577]),'TPEX:8299':anchor([1635,1640,1515]),'TWSE:2344':anchor([127.5,125,113])}};
const page=fs.readFileSync(path.join(root,'index.html'),'utf8');
const nodes=new Map(), node=id=>nodes.get(id)||nodes.set(id,{hidden:false,textContent:'',innerHTML:'',append(){},onclick:null}).get(id);
const ctx=vm.createContext({market,tail,current,structuredClone,console,URL,Date,window:{},document:{readyState:'loading',getElementById:node,querySelectorAll:()=>[],createElement:()=>({}),createTextNode:x=>x,addEventListener(){}}});
vm.runInContext(page.match(/<script>\n([\s\S]*?)<\/script>/)[1],ctx);
const run=code=>vm.runInContext(code,ctx);
for(const [symbol,expected] of Object.entries({'TPEX:6488':[546,544,490],'TPEX:8299':[1535,1520,1455]})){
  ctx.sym=symbol;
  const original=JSON.stringify(market.stocks[symbol]);
  const out=run('explorerTpexBridge(sym,market.stocks[sym],undefined,tail)');
  assert.deepEqual(Array.from(out.prices.slice(-3),p=>p[1]),expected);
  assert.deepEqual(Array.from(out.prices.slice(-3),p=>p[0]),['2026-11-17','2026-11-18','2026-11-19']);
  assert.equal(JSON.stringify(market.stocks[symbol]),original);
  for(const code of [
    "d.prices.at(-1)[1]+=1",
    "d.close+=1",
    "d.lastPriceDate='2026-11-19'",
    "d.prices.push(['2026-11-20',450]);d.lastPriceDate='2026-11-20';d.close=450",
    "d.priceCurrency='USD'",
    "d.priceSessionBasis='regular raw'",
    "d.priceStatus='partial'",
    "t.sourcesByDate['2026-11-17'].rawUrl='https://example.com/'",
    "t.sourcesByDate['2026-11-19'].sha256='bad-hash'",
    "t.verification.corporateActions.matchedEvents.push({symbol:sym})",
    "t.verification.priceCrosscheck.officialPriceMoves[sym][0]+=1",
    "t.quotes[sym][2][0]='2026-11-19'",
    "t.quotes[sym][3][0]='2026-11-20'",
    "t.quotes[sym][2][1]=0"
  ]){
    assert.equal(run('{const t=structuredClone(tail),d=structuredClone(market.stocks[sym]);'+code+'; explorerTpexBridge(sym,d,undefined,t)}'),null, code);
  }
}
assert.equal(run("explorerTpexBridge('TWSE:2344',market.stocks['TWSE:2344'],undefined,tail)"),null);
assert.equal(run("explorerTpexBridge('TPEX:9999',market.stocks['TPEX:6488'],undefined,tail)"),null);
run("MARKET=market;EXPLORER_TPEX_TAIL=tail;const nextScalar=structuredClone(current);nextScalar.sessionDate='2026-11-20';nextScalar.quotes['TPEX:6488'].asOf=nextScalar.sessionDate;nextScalar.quotes['TPEX:6488'].close=450;EXPLORER_TAIWAN_CLOSES=nextScalar;chosen={symbol:'TPEX:6488'};renderChart();renderPerformance();renderExplorerLatestClose(chosen,data(chosen),validPrices(data(chosen)))");
assert.match(node('chartstat').textContent,/2026-11-19/);
assert.match(node('chartnote').textContent,/TPEx/);
assert.match(node('chartempty').innerHTML,/2026-11-19/);
assert.match(node('performance').innerHTML,/2026-11-16/);
assert.doesNotMatch(node('performance').innerHTML,/2026-11-19/);
assert.match(node('last').textContent,/450 TWD/);
assert.match(node('priceinfo').textContent,/2026-11-20.*차트 2026-11-19.*수익률 .*2026-11-16/);
run("window.Chart=class { constructor(_node,config){this.config=config;} destroy(){} };renderChart()");
assert.equal(run('chart.config.data.labels.at(-1)'),'2026-11-19');
assert.equal(run('chart.config.data.datasets[0].data.at(-1)'),490);
run("EXPLORER_TPEX_TAIL=null;renderChart()");
assert.equal(run('chart.config.data.labels.at(-1)'),'2026-11-16');
run("EXPLORER_TPEX_TAIL=tail;chosen={symbol:'TWSE:2344'};renderChart();renderPerformance();");
assert.match(node('chartstat').textContent,/2026-11-16/);
assert.doesNotMatch(node('chartnote').textContent,/TPEx/);
console.log('PASS: exact-anchor/source/action/movement/session guards; only two TPEx charts end Nov 19, prior returns and separate latest scalar preserved, fails closed on mismatches.');
