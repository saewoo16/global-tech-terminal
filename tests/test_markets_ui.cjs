const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const root=path.resolve(__dirname,'..'),raw=fs.readFileSync(root+'/assets/markets.js','utf8'),html=fs.readFileSync(root+'/index.html','utf8');
const elements=['DGS10','HQMCB10YRP','DCOILWTICO','DCOILBRENTEU','DEXJPUS','DEXKOUS','DTWEXBGS','BAMLH0A0HYM2'].map(id=>({dataset:{fredSeries:id},children:[],append(...items){this.children.push(...items)}}));
const listeners=new Map(),context={URL,Date,Set,Object,window:{location:{hash:'#explorer'},addEventListener:(n,fn)=>listeners.set(n,fn)},document:{readyState:'loading',addEventListener:(n,fn)=>listeners.set(n,fn),querySelectorAll:()=>elements,createElement:tag=>({tag,classList:{add(){}}})}};
vm.createContext(context);vm.runInContext(raw.replace('  if(document.readyState','  window.api={range,imageUrl,load,boot};\n  if(document.readyState'),context);const api=context.window.api;
assert.equal(api.range(new Date('2026-10-17T08:00:00Z')).start,'2021-10-17');assert.equal(api.range(new Date('2024-02-29T08:00:00Z')).start,'2019-02-28');
assert.equal(api.imageUrl('BAMLH0A0HYM2',api.range()),'');api.boot();assert(elements.every(item=>item.children.length===0));
context.window.location.hash='#rates';listeners.get('hashchange')();assert.equal(elements[0].children.length,3);assert.equal(elements[7].children.length,0);
for(const el of elements.slice(0,7)){const [image,status]=el.children;assert(image.src.startsWith('https://fred.stlouisfed.org/graph/fredgraph.png?'));assert(image.src.includes('cosd='));image.onload();assert(status.textContent.includes('최신 관측일'));image.onerror();assert(image.hidden);assert(status.textContent.includes('불러오지 못했습니다'));el.children[2].onclick();assert.equal(image.hidden,false);assert(image.src.includes('width=1200'));el.children[2].onclick();assert(image.src.includes('width=1100'));}
api.load();assert.equal(elements[0].children.length,3);
assert(html.includes('https://finviz.com/widgets/map?t=sec&amp;st=d1&amp;theme=dark'));assert(!html.includes('src="https://finviz.com/map'));
for(const id of ['BAMLH0A0HYM2','BAMLH0A0HYM2EY']){assert(html.includes('https://fred.stlouisfed.org/series/'+id));assert(!html.includes('data-fred-series="'+id+'"'));}
for(const match of html.matchAll(/<iframe\b[^>]*>/g)){assert(match[0].includes('title='));assert(match[0].includes('loading="lazy"'));}
console.log('PASS macro ranges, leap days, public-domain allowlist, lazy tab load, missing-image fallback, repeat visits, original links, and official FINVIZ embed');
