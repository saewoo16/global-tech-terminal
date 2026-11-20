const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const root=path.resolve(__dirname,'..');
const page=fs.readFileSync(path.join(root,'index.html'),'utf8'),script=page.match(/<script>\n([\s\S]*?)<\/script>/)[1];
const json=f=>JSON.parse(fs.readFileSync(path.join(root,'data',f),'utf8'));
const current=json('explorer-taiwan-open-close-latest.json'),previous=json('explorer-taiwan-open-close.json');
const TaiwanListings=[...new Set(json('companies.json').filter(c=>/^(TWSE|TPEX):/.test(c.symbol)).map(c=>c.symbol))].sort();
const calls=[],configs=[];
const context={URL,Date,console,current,previous,AbortController,setTimeout,clearTimeout,document:{readyState:'loading',getElementById:()=>({}),querySelectorAll:()=>[],addEventListener(){}},fetch:(url,config)=>{calls.push(url);configs.push(config);return context.fetchReply(url);}};
vm.createContext(context);vm.runInContext(script,context);
const run=code=>vm.runInContext(code,context),read=()=>run('readExplorerTaiwanCloses()');
const reply=data=>({ok:true,json:async()=>data});
function assertLatestPath(){assert.match(calls[0],/\/explorer-taiwan-open-close-latest\.json$/);assert.equal(configs.at(-calls.length).cache,'no-cache');assert(configs.at(-calls.length).signal);}
function assertFallbackPath(){assert.match(calls[1],/\/explorer-taiwan-open-close\.json\?v=/);}
(async()=>{
 assert.ok(current.sessionDate>previous.sessionDate);
 assert.equal(current.sessionDate,'2026-11-19');
 assert.equal(current.quotes['TWSE:2308'].close,1000);
 assert.equal(current.quotes['TWSE:2344'].close,98);
 assert.doesNotMatch(page,/tw-close-comparison|explorerOfficialCloseComparison|EXPLORER_TAIWAN_REFERENCE/);
 assert.deepEqual(Object.keys(current.quotes).sort(),TaiwanListings);
 assert.equal(Object.keys(current.quotes).length,current.sources.twse.matchingListings+current.sources.tpex.matchingListings);
 for(const [symbol,q] of Object.entries(current.quotes)){
  assert.equal(q.asOf,current.sessionDate);
  assert.strictEqual(run('explorerTaiwanClose('+JSON.stringify(symbol)+',"",current)').q,q);
 }
 assert.match(page,/readJson\('\.\/data\/financial_backfill_zlatest_20261116_kr_official\.json[^)]*\)\.then\(/);
 assert.match(page,/readExplorerTaiwanCloses\(\)\.then\(/);
 context.fetchReply=async()=>reply(current);
 assert.strictEqual(await read(),current);assert.equal(calls.length,1);assertLatestPath();
 console.log('PASS all listed Taiwan securities use independently sourced latest official close; legacy fixture unchanged');
 for(const bad of [{ok:false,status:404},reply({}),reply({...current,quotes:{...current.quotes,'TWSE:2408':{...current.quotes['TWSE:2408'],asOf:previous.sessionDate}}})]){
  calls.length=0;context.fetchReply=async url=>url.includes('-latest.json')?bad:reply(previous);
  assert.strictEqual(await read(),previous);assert.equal(calls.length,2);assertLatestPath();assertFallbackPath();
 }
 calls.length=0;context.fetchReply=async()=>{throw Error('simulated fetch unavailable');};
 assert.strictEqual(await read(),null);assert.equal(calls.length,2);assertLatestPath();assertFallbackPath();
 console.log('PASS unavailable or invalid latest uses verified legacy without mutating either dataset; dual failure is safe');
})().catch(e=>{console.error(e);process.exitCode=1;});
