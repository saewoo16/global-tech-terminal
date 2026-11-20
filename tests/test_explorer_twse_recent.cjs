const assert=require('node:assert/strict'), fs=require('node:fs'), path=require('node:path'),vm=require('node:vm');
const root=path.resolve(__dirname,'..'), json=f=>JSON.parse(fs.readFileSync(path.join(root,'data',f),'utf8'));
const recent=json('explorer-twse-recent-cash.json'), scalar=json('explorer-taiwan-open-close-latest.json');
const page=fs.readFileSync(path.join(root,'index.html'),'utf8'), nodes=new Map();
const node=id=>nodes.get(id)||nodes.set(id,{hidden:true,innerHTML:'',textContent:'',append(){}}).get(id);
const ctx=vm.createContext({recent,structuredClone,URL,console,Date,window:{},document:{readyState:'loading',getElementById:node,querySelectorAll:()=>[],createElement:()=>({}),createTextNode:x=>x,addEventListener(){}}});
vm.runInContext(page.match(/<script>\n([\s\S]*?)<\/script>/)[1],ctx);
const call=code=>vm.runInContext(code,ctx);
const expected=Object.keys(scalar.quotes).filter(s=>s.startsWith('TWSE:')).sort();
assert.equal(expected.length,30);
assert.deepEqual(Object.keys(recent.quotes).sort(),expected);
for (const sym of expected){
  ctx.sym=sym;
  const q=call('explorerTwseRecent(sym,recent)');
  assert(q);
  assert.equal(q.latestBar.close,scalar.quotes[sym].close);
  assert.equal(q.latestBar.date,'2026-11-20');
}
for(const mutation of [
  "d.quotes['TWSE:2308'].closes[0][0]='2026-11-17'",
  "d.quotes['TWSE:2308'].latestBar.high=1",
  "d.quotes['TWSE:2308'].latestBar.volume=-1",
  "d.quotes['TWSE:2308'].latestBar.close+=1",
  "d.sourcesByDate['2026-11-19'].licenseUrl='https://example.com'",
  "d.latestOhlcvEvidence.sha256='bad'"
])assert.equal(call("{const d=structuredClone(recent);"+mutation+";explorerTwseRecent('TWSE:2308',d)}"),null);
assert.equal(call("explorerTwseRecent('TPEX:8299',recent)"),null);
assert.equal(call("explorerTwseRecent('TWSE:9999',recent)"),null);
call("EXPLORER_TWSE_RECENT=recent;renderExplorerTwseRecent({symbol:'TWSE:2308'})");
assert.equal(node('explorer-twse-recent').hidden,false);
assert.match(node('explorer-twse-recent').innerHTML,/11-18.*11-19.*11-20.*11\/20 시가.*고가.*저가.*종가.*위 장기 조정종가 차트와 연결하지/);
call("renderExplorerTwseRecent({symbol:'NASDAQ:AAPL'})");
assert.equal(node('explorer-twse-recent').hidden,true);
assert.equal(node('explorer-twse-recent').innerHTML,'');
console.log('PASS: exact 30 dated TWSE OHLCV and close comparison, attribution, chart range and venue isolation.');
