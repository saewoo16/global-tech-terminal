/* Synthetic candidates exercise fail-closed rendering; production data is untouched. */
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const root=path.resolve(__dirname,'..'),data=JSON.parse(fs.readFileSync(root+'/data/us_analysis.json')),raw=fs.readFileSync(root+'/assets/us-analysis.js','utf8');
const elements=new Map();function el(id){if(!elements.has(id))elements.set(id,{id,innerHTML:''});return elements.get(id);}
const ctx={URL,Date,Number,String,Array,Set,Map,Math,console,window:{location:{hash:'#us'},addEventListener(){}},document:{readyState:'loading',getElementById:el,querySelectorAll:()=>[],querySelector:()=>null,addEventListener(){}}};
let next=data;
ctx.fetch=async url=>({ok:true,json:async()=>url.includes('us_heatmaps')?{schemaVersion:1,entries:[]}:structuredClone(next)});
vm.createContext(ctx);vm.runInContext(raw.replace("if(document.readyState==='loading')","window.audit={load,render,earnings,earningsForSession};if(document.readyState==='loading')"),ctx);
const api=ctx.window.audit,fixtureIndex=data.entries.findIndex(e=>e.date==='2026-11-12'),latest=data.entries[fixtureIndex],cards=e=>(api.earnings(e).match(/<article class="us-card">/g)||[]).length;
const fixture=()=>structuredClone(latest),add=(e,changes={})=>{const r={...structuredClone(e.earnings.rows[0]),...changes};e.earnings.rows.push(r);return r;};
(async()=>{
 const before=JSON.stringify(data);assert.equal(cards(latest),latest.earnings.rows.length);
 const unverified=data.entries.find(e=>e.date==='2026-11-13');if(unverified)assert.equal(cards(unverified),0);
 for(const changes of [{summary:'Conflicting fixture'},{callSupplement:{observedAt:'2026-11-08T01:00:00Z'}}]){
  const e=fixture();add(e,changes);const saved=JSON.stringify(e);
  assert.equal(cards(e),latest.earnings.rows.length-1);assert(api.earnings(e).includes('표시를 보류'));
  assert.equal(cards(e),latest.earnings.rows.length-1);assert.equal(JSON.stringify(e),saved);
 }
 const identical=fixture();add(identical);assert.equal(cards(identical),latest.earnings.rows.length);assert(!api.earnings(identical).includes('표시를 보류'));const reordered=fixture();const original=reordered.earnings.rows[0];reordered.earnings.rows.push(Object.fromEntries(Object.entries(structuredClone(original)).reverse()));assert.equal(cards(reordered),latest.earnings.rows.length);
 const defaults=fixture();delete defaults.earnings.rows[0].releaseType;add(defaults,{releaseType:'results'});assert.equal(cards(defaults),latest.earnings.rows.length-1);
 const distinct=fixture();delete distinct.earnings.rows[0].releaseType;add(distinct,{period:'Synthetic distinct period'});add(distinct,{releaseType:'preliminary'});assert.equal(cards(distinct),latest.earnings.rows.length+2);
 const single=fixture();single.earnings.rows=[single.earnings.rows[0]];add(single,{summary:'Conflict'});assert.equal(cards(single),0);assert(api.earnings(single).includes('표시를 보류'));
 const supplement=fixture();supplement.earnings.rows[0].callSupplement={observedAt:'2026-11-08T01:00:00Z'};assert.equal(cards(supplement),latest.earnings.rows.length);assert.equal(supplement.earnings.rows[0].releaseDate,latest.date);
 const historical=structuredClone(data.entries.find(e=>e.date==='2026-11-11'));historical.earnings.rows=[{...historical.earnings.rows[0],ticker:latest.earnings.rows[0].ticker}];assert.equal(cards(historical),1);assert.equal(cards(latest),latest.earnings.rows.length);
 const timezone=fixture();const copy=add(timezone);if(copy.releaseTiming?.publishedAt)copy.releaseTiming.publishedAt=new Date(copy.releaseTiming.publishedAt).toISOString();assert.equal(cards(timezone),JSON.stringify(copy)===JSON.stringify(timezone.earnings.rows[0])?latest.earnings.rows.length:latest.earnings.rows.length-1);
 for(const candidate of [identical,defaults]){next=structuredClone(data);next.entries=next.entries.filter(e=>e.date<latest.date);next.entries.unshift(candidate);const unchanged=JSON.stringify(next);await api.load();const html=el('us-content').innerHTML;assert(html.includes('미국 현지 '+latest.date+' 완료 거래일'));api.render();assert.equal(el('us-content').innerHTML,html);await api.load();assert.equal(el('us-content').innerHTML,html);assert.equal(JSON.stringify(next),unchanged);}assert.equal(JSON.stringify(data),before);
 console.log('PASS US earnings duplicate/conflict, distinct release, archive, call supplement, immutable repeated render/refresh tests');
})().catch(e=>{console.error(e);process.exitCode=1;});
