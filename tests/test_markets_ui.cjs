const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const root=path.resolve(__dirname,'..'),raw=fs.readFileSync(root+'/assets/markets.js','utf8'),html=fs.readFileSync(root+'/index.html','utf8');
const elements=['DGS10','HQMCB10YRP','DCOILWTICO','DCOILBRENTEU','DEXJPUS','DEXKOUS','DTWEXBGS','BAMLH0A0HYM2'].map(id=>({dataset:{fredSeries:id},children:[],append(...items){this.children.push(...items)}}));
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
context.window.location.hash='#rates';listeners.get('hashchange')();assert.equal(elements[0].children.length,3);assert.equal(elements[7].children.length,0);
for(const el of elements.slice(0,7)){const [image,status]=el.children;assert(image.src.startsWith('https://fred.stlouisfed.org/graph/fredgraph.png?'));assert(image.src.includes('cosd='));image.onload();assert(status.textContent.includes('최신 관측일'));image.onerror();assert(image.hidden);assert(status.textContent.includes('불러오지 못했습니다'));el.children[2].onclick();assert.equal(image.hidden,false);assert(image.src.includes('width=1200'));el.children[2].onclick();assert(image.src.includes('width=1100'));}
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

const cards=[...html.matchAll(/<article class="rate-card(?: rate-link-card)?" data-series="([^"]+)"/g)].map(m=>m[1]);
assert.deepEqual(cards,['DGS10','BAMLH0A0HYM2EY','BAMLH0A0HYM2','HQMCB10YRP','US594918BC73','DCOILWTICO','DCOILBRENTEU','DXY','DTWEXBGS','DEXJPUS','DEXKOUS']);
assert(html.includes('<h3>하이일드 채권 수익률</h3>'));
assert.equal(cards.filter(id=>id==='BAMLH0A0HYM2').length,1,'OAS chart must replace the final link-only card without duplication');
console.log('PASS Treasury → HY yield → HY OAS → high-quality corporate → Microsoft individual bond order and unchanged remaining cards');

assert.deepEqual(widgetDefinitions.map(item=>item.id),['BAMLH0A0HYM2EY','BAMLH0A0HYM2','US594918BC73']);
for(const [index,widget] of widgets.entries()){
 assert.equal(widget.children.length,1);const fragment=widget.children[0],script=fragment.container.children[0];
 assert(fragment.original.removed,'Inert script is replaced once');
 assert.equal(script.src,'https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js');
 assert.equal(script.type,'text/javascript');assert.equal(script.async,true);
 assert.equal(script.textContent,widget.definition.textContent,'Generated config is copied verbatim');
 const config=JSON.parse(script.textContent);
 assert.equal(config.symbol,['FRED:BAMLH0A0HYM2EY','FRED:BAMLH0A0HYM2','MUN:US594918BC7'][index]);
 assert.equal(config.range,'60M');assert.equal(config.autosize,true);assert.equal(config.theme,'light');
 assert.equal(config.interval,'D');assert.equal(config.timezone,'Etc/UTC');
 assert.match(widget.definition.markup,/tradingview-widget-container__widget/);
 assert.match(widget.definition.markup,/tradingview-widget-copyright/);
 assert.match(widget.definition.markup,/rel="noopener nofollow" target="_blank"/);
 assert.match(widget.definition.markup,/<span class="trademark">&nbsp;by TradingView<\/span>/);
 assert.equal(script.onload,undefined,'Script success must not claim chart data loaded');
 assert.equal(widget.status.textContent.includes('원본 링크'),true);
 widget.frame={attrs:{},getAttribute(key){return this.attrs[key]},setAttribute(key,value){this.attrs[key]=value}};
 if(index===1)widget.frame.attrs.title='Provider supplied title';
 observers[index].callback();assert(observers[index].disconnected);
 assert.equal(widget.frame.attrs.title,index===1?'Provider supplied title':widget.definition.label);
 script.onerror();assert.match(widget.status.textContent,/불러오지 못했습니다/);assert.match(widget.status.textContent,/원본 링크/);
}
for(const route of ['#explorer','#heatmap','#rates','#briefing/US/2026-10-16','#rates']){
 context.window.location.hash=route;listeners.get('hashchange')();
 assert(widgets.every(widget=>widget.children.length===1),'Repeat routes must preserve a single widget');
}
const untrusted=mockWidget({...widgetDefinitions[0],src:'https://example.com/not-a-provider.js'});
widgets.push(untrusted);api.load();assert.equal(untrusted.children.length,0);assert.equal(untrusted.dataset.loaded,undefined);
assert.equal((html.match(/data-fred-series=/g)||[]).length,2,'Two unchanged FRED charts stay intact');
assert.match(html,/markets\.css\?v=20261025-external2/);assert.match(html,/markets\.js\?v=20261025-external2/);
assert.match(fs.readFileSync(root+'/assets/markets.css','utf8'),/\.tradingview-chart\{height:440px;width:100%/);
assert.match(html,/쿠폰 3\.5% · 만기 2035-02-12/);assert.match(html,/회사 전체 금리가 아닙니다/);
assert(!html.includes('MUN:US023135'));assert(!html.includes('MUN:US02079K'));
console.log('PASS official TradingView templates, exact settings and attribution, rates-only lazy loading, accessible titles, script-error fallback, repeat navigation, and provider allowlist');

for(const symbol of ['FINRA-AMZN6237343','FINRA-GOOG6065581']){
 assert(html.includes(`href="https://www.tradingview.com/symbols/${symbol}/" target="_blank" rel="noopener noreferrer"`));
 assert(!widgetDefinitions.some(widget=>widget.markup.includes(symbol)));
}
assert.match(html,/두 채권은 제공사의 위젯 제한/);
console.log('PASS Amazon and Alphabet compact original-source links without unsupported embeds');

assert.equal((html.match(/기본 5년 차트는 주별 표본으로 표시될 수 있습니다/g)||[]).length,3);
assert.equal((html.match(/최신 관측일은 차트\/원본을 확인하세요/g)||[]).length,3);
console.log('PASS five-year sampling and latest-observation notes on all three TradingView cards');

const spreadCard=html.match(/<article class="rate-card" data-series="BAMLH0A0HYM2">[\s\S]*?<\/article>/)[0];
assert.match(spreadCard,/<h3>하이일드 스프레드 \(OAS\)<\/h3>/);
assert.match(spreadCard,/Option-Adjusted Spread · %p · 일별/);
assert.match(spreadCard,/차트의 % 표시는 %p로 읽습니다/);
assert.match(spreadCard,/3\.00%p = 300bp/);
assert.match(spreadCard,/채권의 절대 수익률과 다릅니다/);
assert.match(spreadCard,/href="https:\/\/www\.tradingview\.com\/symbols\/FRED-BAMLH0A0HYM2\/" rel="noopener nofollow" target="_blank"/);
assert.match(spreadCard,/href="https:\/\/fred\.stlouisfed\.org\/series\/BAMLH0A0HYM2" target="_blank" rel="noopener noreferrer"/);
assert(!spreadCard.includes('rate-link-card'));
console.log('PASS OAS title, percentage-point/basis-point explanation, distinction from yield, official attribution, and original-source fallback');

assert(!widgetDefinitions.some(w=>w.id==="DXY"));assert(html.includes("DXY 차트 원본"));

const symbols=['OTCB:US10Y','FX:USOIL','FX:UKOIL','CAPITALCOM:DXY','FX:USDJPY','FX_IDC:USDKRW'];
assert.deepEqual([...html.matchAll(/data-macro-chart="([^"]+)"/g)].map(m=>m[1]),symbols);
const defs=[...html.matchAll(/data-macro-chart="([^"]+)"[^>]*><template>([\s\S]*?)<\/template>/g)].map(([,id,markup])=>{const sc=markup.match(/<script type="([^"]+)" src="([^"]+)" async>([\s\S]*?)<\/script>/);return {id,label:id,markup,type:sc[1],src:sc[2],textContent:sc[3]}});
const holders=defs.map(mockWidget);holders.forEach(h=>h.dataset={macroChart:h.definition.id});
context.document.querySelectorAll=selector=>selector==='[data-macro-chart]'?holders:[];
context.window.location.hash='#explorer';api.load();assert(holders.every(h=>h.children.length===0));
context.window.location.hash='#rates';api.load();api.load();
for(const h of holders){assert.equal(h.children.length,1);const sc=h.children[0].container.children[0];assert.equal(sc.src,'https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js');assert.equal(JSON.parse(sc.textContent).symbol,h.dataset.macroChart);assert.equal(JSON.parse(sc.textContent).theme,'light');sc.onerror();assert(h.status.textContent.includes('원본 링크'));}
const badMacro=mockWidget(defs[0]);badMacro.dataset={macroChart:'TVC:DXY'};holders.push(badMacro);api.load();assert.equal(badMacro.children.length,0);
assert.match(html,/달러인덱스 추종 CFD/);assert.match(html,/CAPITALCOM:DXY/);
assert(!html.includes('symbol="TVC:DXY"'));assert.match(html,/1 USD당 일본 엔/);assert.match(html,/1 USD당 한국 원/);
assert(fs.readFileSync(root+'/assets/macro.js','utf8').includes('card.dataset.externalMacro||!q')); 
console.log('PASS six official external components, source/basis labels, lazy one-time widget load, provider allowlist and link fallback');
