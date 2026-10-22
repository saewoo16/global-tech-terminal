const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const root=path.resolve(__dirname,'..'),data=JSON.parse(fs.readFileSync(root+'/data/us_analysis.json'));
const entry=data.entries.find(e=>e.date==='2026-10-22'),raw=fs.readFileSync(root+'/assets/us-analysis.js','utf8');
const context={URL,console,window:{},document:{readyState:'loading',addEventListener(){}}};
vm.createContext(context);
vm.runInContext(raw.replace("if(document.readyState==='loading')","window.api={breadth,indices};if(document.readyState==='loading')"),context);
const {breadth,indices}=context.window.api;
let count=0;function test(name,fn){fn();count++;console.log('PASS',name)}
test('breadth follows index cards and precedes FX, with semantic labels and precise scope',()=>{
 const h=indices(entry),panel=breadth(entry);
 assert(h.indexOf('id="us-breadth"')>h.indexOf('class="us-indices"'));
 assert(h.indexOf('id="us-breadth"')<h.indexOf('id="us-fx"'));
 for(const text of ['S&P 500 · 상승·하락 종목 비율','336개','66.8%','166개','33.0%','1개','0.2%',
   '확인 503 / 503개 증권 · 미확인 0개','500개 기업','미국 시장 전체 아님','복수 주식종류',
   '2026-10-22 정규장 종가','직전 거래일 2026-10-21 대비','비율 분모는 확인된 503개 증권',
   'role="region" aria-labelledby="us-breadth-title"','aria-hidden="true"',
   './data/us-close-evidence-20261022.json'])assert(panel.includes(text),text);
 assert.equal((panel.match(/<li>/g)||[]).length,5); // Three readable counts plus two collapsed source links.
 assert(!panel.includes('<details class="us-sources" open'));
});
test('optional historical breadth does not invent older values',()=>{
 assert.equal(breadth(data.entries.find(e=>e.date==='2026-10-16')),'');
});
test('invalid or absent values never become a visible zero-percent distribution',()=>{
 for(const patch of [{asOf:'2026-10-21'},{previousSession:null},{universe:'US'},
  {validCount:null},{validCount:0},{securities:500},{missingCount:1},{status:'unavailable'},
  {counts:{advancing:335,declining:166,unchanged:1}},{percentages:{advancing:66.8,declining:33,unchanged:.2}},
  {sourceIds:[]},{sourceIds:['made_up']}]){
   const h=breadth({...entry,breadth:{...entry.breadth,...patch}});
   assert(h.includes('집계 미확보'),JSON.stringify(patch));assert(!h.includes('class="us-breadth-bar"'));
  }
});
test('partial breadth displays missing securities while excluding them from denominator',()=>{
 const b=JSON.parse(JSON.stringify(entry.breadth));b.status='partial';b.validCount=502;b.missingCount=1;b.missingTickers=['MMM'];b.counts.advancing--;
 b.percentages=Object.fromEntries(Object.entries(b.counts).map(([k,v])=>[k,v/502*100]));
 const h=breadth({...entry,breadth:b});
 for(const t of ['확인 502 / 503개 증권 · 미확인 1개 (MMM)','335개','66.7%','비율 분모는 확인된 502개 증권'])assert(h.includes(t),t);
});
test('unsafe evidence paths are not linked and source notes stay escaped',()=>{
 const h=breadth({...entry,breadth:{...entry.breadth,evidencePath:'javascript:alert(1)',note:'<img src=x>'}});
 assert(!h.includes('javascript:'));assert(h.includes('&lt;img src=x&gt;'));assert(!h.includes('<img src=x>'));
});
test('bar widths use exact counts and maintain all three statuses',()=>{
 const h=breadth(entry),widths=[...h.matchAll(/style="width:([\d.]+)%"/g)].map(m=>Number(m[1]));
 assert.equal(widths.length,3);assert(Math.abs(widths.reduce((a,b)=>a+b,0)-100)<1e-9);
 assert(Math.abs(widths[0]-336/503*100)<1e-9);assert(h.includes('us-breadth-unchanged'));
});
console.log(`${count} US breadth UI tests passed.`);
