const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const root=path.resolve(__dirname,'..'),raw=fs.readFileSync(root+'/assets/markets.js','utf8'),html=fs.readFileSync(root+'/index.html','utf8');
const elements=['DGS10','HQMCB10YRP','DCOILWTICO','DCOILBRENTEU','DEXJPUS','DEXKOUS','M1SL','M2SL','BAMLH0A0HYM2'].map(id=>({dataset:{fredSeries:id},children:[],append(...items){this.children.push(...items)}}));
const widgetDefinitions=[...html.matchAll(/<div class="tradingview-chart" data-tradingview-widget="([^"]+)" role="region" aria-label="([^"]+)"><template>\n([\s\S]*?)\n<\/template>/g)].map(([,id,label,markup])=>{
 const script=markup.match(/<script type="([^"]+)" src="([^"]+)" async>([\s\S]*?)<\/script>/);
 assert(script,'Official script must remain inside the inert template');
 return {id,label,markup,type:script[1],src:script[2],textContent:script[3]};
});
function mockWidget(definition){
 const status={textContent:'TradingView 제공 차트 · 표시되지 않으면 아래 원본 링크를 이용하세요.'};
 return {definition,dataset:{tradingviewWidget:definition.id},children:[],status,frame:null,
  querySelector(selector){return selector==='template'?{content:definition}:selector==='iframe'?this.frame:null},
  getAttribute(name){return name==='aria-label'?definition.label:null},
  parentElement:{querySelector:()=>status},append(fragment){this.children.push(fragment)}};
}
const widgets=widgetDefinitions.map(mockWidget),observers=[];
const listeners=new Map(),context={URL,Date,Set,Object,window:{location:{hash:'#explorer'},addEventListener:(n,fn)=>listeners.set(n,fn),MutationObserver:class{constructor(callback){this.callback=callback;observers.push(this)}observe(holder){this.holder=holder}disconnect(){this.disconnected=true}}},document:{readyState:'loading',addEventListener:(n,fn)=>listeners.set(n,fn),querySelectorAll:selector=>selector==='[data-fred-series]'?elements:selector==='[data-tradingview-widget]'?widgets:[],
importNode:definition=>{
 const container={children:[],append(script){this.children.push(script)}};
 const original={type:definition.type,textContent:definition.textContent,parentNode:container,getAttribute:()=>definition.src,remove(){this.removed=true}};
 return {container,original,querySelector:()=>original};
},createElement:tag=>({tag,classList:{add(){}}})}};
vm.createContext(context);vm.runInContext(raw.replace('  if(document.readyState','  window.api={range,imageUrl,load,boot};\n  if(document.readyState'),context);const api=context.window.api;
assert.equal(api.range(new Date('2026-10-17T08:00:00Z')).start,'2021-10-17');assert.equal(api.range(new Date('2024-02-29T08:00:00Z')).start,'2019-02-28');
assert.equal(api.imageUrl('BAMLH0A0HYM2',api.range()),'');api.boot();assert(elements.every(item=>item.children.length===0));assert(widgets.every(item=>item.children.length===0),'No TradingView script activates outside rates');
context.window.location.hash='#rates';listeners.get('hashchange')();assert.equal(elements[0].children.length,3);assert.equal(elements[8].children.length,0);
for(const el of elements.slice(0,8)){const [image,status]=el.children;assert(image.src.startsWith('https://fred.stlouisfed.org/graph/fredgraph.png?'));assert(image.src.includes('cosd='));image.onload();assert(status.textContent.includes('최신 관측일'));image.onerror();assert(image.hidden);assert(status.textContent.includes('불러오지 못했습니다'));el.children[2].onclick();assert.equal(image.hidden,false);assert(image.src.includes('width=1200'));el.children[2].onclick();assert(image.src.includes('width=1100'));}
api.load();assert.equal(elements[0].children.length,3);
assert(!html.includes('id="heatmap-panel"'));assert(!html.includes('data-view="heatmap"'));
for(const id of ['BAMLH0A0HYM2','BAMLH0A0HYM2EY']){assert(html.includes('https://fred.stlouisfed.org/series/'+id));assert(!html.includes('data-fred-series="'+id+'"'));}
for(const match of html.matchAll(/<iframe\b[^>]*>/g)){assert(match[0].includes('title='));assert(match[0].includes('loading="lazy"'));}
console.log('PASS macro ranges, leap days, public-domain allowlist, lazy tab load, missing-image fallback, repeat visits, original links, and retired standalone heatmap');

// Latest user request: official free daily FINVIZ with week/month links, no standalone tab.
const heatmap=fs.readFileSync(root+'/assets/us-analysis.js','utf8');
assert(heatmap.includes('id="us-heatmap"'));
assert(heatmap.includes('finviz.com/widgets/map?t=sec&amp;st=d1'));
assert(!heatmap.includes('us-heatmap-grid'));
assert(heatmap.includes('시점에 따라 변동 가능'));
for(const period of ['d1','w1']) assert(heatmap.includes(`href="https://finviz.com/map?t=sec&amp;st=${period}"`));
assert(heatmap.includes('href="https://finviz.com/map?st=w4&amp;t=sec"'));
for(const period of ['w1','w4']) assert(!heatmap.includes(`widgets/map?t=sec&amp;st=${period}`));
assert(fs.readFileSync(root+'/assets/korea.js','utf8').includes('id="kr-heatmaps"'));
console.log('PASS domestic heatmap, free official FINVIZ daily iframe, week/month links, and no standalone map');

const cards=[...html.matchAll(/<article class="rate-card" data-series="([^"]+)"/g)].map(m=>m[1]);
assert.deepEqual(cards,['DGS10','BAMLH0A0HYM2EY','BAMLH0A0HYM2','HQMCB10YRP','US594918BC73','COMEX_GOLD','CME_CF_BRR','COMEX_COPPER','DCOILWTICO','DCOILBRENTEU','DXY','M1SL','M2SL','DEXJPUS','DEXKOUS']);
assert.deepEqual([...html.matchAll(/data-fred-series="([^"]+)"/g)].map(m=>m[1]),['DGS10','HQMCB10YRP','DCOILWTICO','DCOILBRENTEU','M1SL','M2SL']);
assert.match(html,/3\.00%p = 300bp/);
assert.match(html,/채권의 절대 수익률과 다릅니다/);
assert.match(html,/쿠폰 3\.5% · 만기 2035-02-12/);
assert.match(html,/회사 전체 금리가 아닙니다/);
const rates=html.slice(html.indexOf('id="rates-grid"'),html.indexOf('id="short-panel"'));
assert.doesNotMatch(rates,/data-macro-chart|data-tradingview-widget|data-external-macro|tradingview\.com|CAPITALCOM|OANDA|FXCM/);
assert.match(rates,/https:\/\/www\.ice\.com\/products\/194\/US-Dollar-Index-Futures/);
assert.match(rates,/https:\/\/www\.finra\.org\/finra-data\/fixed-income/);
assert.match(rates,/1 USD당 일본 엔/);assert.match(rates,/1 USD당 한국 원/);
console.log('PASS official-only rates layout, six public-domain FRED chart sources, close-basis labels and official-only original links.');
