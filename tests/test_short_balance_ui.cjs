const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const html=fs.readFileSync('index.html','utf8'),raw=fs.readFileSync('assets/short-balance.js','utf8');
const listeners={},elements={};const el=id=>elements[id]||(elements[id]={innerHTML:''});
let response={schemaVersion:1,metric:'net-short-outstanding-balance',unit:'KRW',investorSplit:'unavailable',status:'unavailable',rows:[],sources:[]},requests=0;
const c={URL,BigInt,Date,Number,Set,console:{error(){}},fetch:async(url,opts)=>{requests++;assert.equal(opts.cache,'no-store');assert.match(url,/ts=/);return {ok:true,json:async()=>response}},document:{readyState:'loading',getElementById:el,addEventListener:(n,f)=>listeners[n]=f},window:{location:{hash:'#short'},addEventListener:(n,f)=>listeners[n]=f}};
vm.createContext(c);vm.runInContext(raw,c);const a=c.window.TerminalShortBalance;
assert(html.includes('id="short-tab"'));assert(html.includes('id="short-panel"'));assert.match(html,/short-balance.js\?v=20261110-short20/);
assert.equal(a.money('123456789012345678'),'1,234,567,890.12');assert.equal(a.money(null),'—');
const r={code:'000001',name:'<unsafe>',market:'KOSPI',balanceKRW:'150000000',marketCapKRW:'1000000000',ratioPct:'15.00',history:[{date:'2026-09-28',balanceKRW:'100000000'},{date:'2026-10-21',balanceKRW:'200000000'},{date:'2026-10-28',balanceKRW:'150000000'}]};
assert.equal(a.delta(r,7,'2026-10-28').value,-25);assert.equal(a.delta(r,30,'2026-10-28').value,50);assert.equal(a.delta(r,30,'2026-10-28').date,'2026-09-28');assert.equal(a.delta({...r,history:[]},7,'2026-10-28').value,null);assert.equal(a.delta({...r,history:[{date:'2026-10-21',balanceKRW:'0'}]},7,'2026-10-28').value,null);
assert(a.compare({...r,balanceKRW:'9007199254740993'},{...r,balanceKRW:'9007199254740992'},'amount')<0);assert(a.compare({...r,balanceKRW:'100',marketCapKRW:'101'},{...r,balanceKRW:'100',marketCapKRW:'102'},'ratio')<0);
assert.match(a.spark(r,'2026-10-28'),/&lt;unsafe&gt;/);assert.match(a.spark(r,'2026-10-28'),/3개 실제 관측/);assert(!a.spark({...r,history:[]},'2026-10-28').includes('<svg'));
const p={schemaVersion:1,metric:'net-short-outstanding-balance',unit:'KRW',investorSplit:'unavailable',status:'verified',asOf:'2026-10-28',observedAt:'2026-11-01T07:00:00Z',coverage:{complete:true,count:1,markets:['KOSPI','KOSDAQ']},rows:[r],sources:[]};assert(a.valid(p));assert(a.valid({...p,rows:[{...r,code:'0000A1'}]}));assert(!a.valid({...p,coverage:{...p.coverage,complete:false}}));assert(!a.valid({...p,rows:[r,r]}));assert(!a.valid({...p,rows:[{...r,balanceKRW:100}]}));assert(!a.valid({...p,status:'unavailable'}));
(async()=>{listeners.DOMContentLoaded();await new Promise(setImmediate);assert.match(el('short-content').innerHTML,/아직 확보하지 못했습니다/);response=p;await el('short-refresh').onclick();assert.match(el('short-content').innerHTML,/잔고 금액 TOP 15/);assert.match(el('short-content').innerHTML,/시총 대비 잔고 TOP 15/);assert.match(el('short-content').innerHTML,/-25.00%/);assert.match(el('short-content').innerHTML,/&lt;unsafe&gt;/);assert(!el('short-content').innerHTML.includes('<unsafe>'));c.fetch=async()=>{throw Error('offline')};await el('short-refresh').onclick();assert.match(el('short-content').innerHTML,/이전 기준일/);assert.match(el('short-content').innerHTML,/잔고 금액 TOP 15/);const n=requests;c.window.location.hash='#rates';listeners.hashchange();assert.equal(requests,n);console.log('PASS short balance precision, exact ranking, provenance guard, actual comparison dates, missing/zero data, escaped sparkline, reload failure preservation and tab isolation');})().catch(e=>{console.error(e);process.exitCode=1});
const published=JSON.parse(fs.readFileSync('data/korean_short_balance.json','utf8'));
assert(a.valid(published));assert.equal(published.status,'verified');
assert.equal(published.coverage.count,2769);assert.equal(published.asOf,'2026-11-06');
for(const metric of ['amount','ratio']){
 const top=[...published.rows].sort((a1,b1)=>a.compare(a1,b1,metric)).slice(0,15);
 assert.equal(top.length,15);for(const row of top){assert.notEqual(a.delta(row,7,published.asOf).value,null);assert.notEqual(a.delta(row,30,published.asOf).value,null);assert.equal(a.delta(row,7,published.asOf).date,'2026-10-30');assert.equal(a.delta(row,30,published.asOf).date,'2026-10-07');}
 assert.equal(top[0].code,metric==='amount'?'373220':'086520');
 for(const row of top){assert.match(a.spark(row,published.asOf),/22개 실제 관측/);assert.match(a.spark(row,published.asOf),/2026-10-07/);}
}
console.log('PASS real official combined universe and all TOP15 exact-date comparison coverage');
