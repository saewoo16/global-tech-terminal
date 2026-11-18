'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const dir=path.resolve(__dirname,'..');
const html=fs.readFileSync(path.join(dir,'index.html'),'utf8'), js=fs.readFileSync(path.join(dir,'assets/markets.js'),'utf8');
assert.match(html,/markets\.js\?v=20261118-metals-bitcoin/);
const symbols=['OANDA:XAUUSD','COINBASE:BTCUSD','CAPITALCOM:XCUUSD','FX:USOIL'];
const cards=[...html.matchAll(/<article class="rate-card"[^>]*data-external-macro="([^"]+)"[^>]*>([\s\S]*?)<\/article>/g)];
const i=cards.findIndex(c=>c[1]===symbols[0]);
assert.deepEqual(cards.slice(i,i+4).map(c=>c[1]),symbols);
assert.match(cards[i+2][2],/구리 현물 추종 CFD.*Capital.com.*USD/);
assert.match(cards[i+2][2],/COMEX 선물 결제값이나 LME 현물 기준가가 아닙니다/);
const holders=cards.slice(i,i+3).map(([,symbol,card])=>{
 const [_,src,config]=card.match(/<template>[\s\S]*?<script[^>]+src="([^"]+)"[^>]*>([^<]+)<\/script>/);
 assert.equal(src,'https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js');
 assert.equal(JSON.parse(config).symbol,symbol);
 assert.match(card,/role="region" aria-label="[^"]+"/);
 assert.ok(card.includes('https://www.tradingview.com/chart/?symbol='+encodeURIComponent(symbol)));
 const status={}, added=[];
 return {added,status,dataset:{macroChart:symbol},querySelector:()=>({content:{querySelector:()=>({getAttribute:()=>src,textContent:config,remove(){},parentNode:{append(s){added.push(s);}}})}}),
   parentElement:{querySelector:()=>status},append(){}};
});
const unapproved={dataset:{macroChart:'COMEX:HG1!'},querySelector:()=>{throw Error('unexpected symbol accepted');}};
const hook=js.replace('  function loadTradingView() {','  window.tryMacroComponents=loadMacroComponents;\n  function loadTradingView() {');
const window={}, document={readyState:'loading',querySelectorAll:()=>[...holders,unapproved],importNode:x=>x,createElement:()=>({}),addEventListener(){},getElementById:()=>null};
vm.runInNewContext(hook,{window,document,IntersectionObserver:undefined});
window.tryMacroComponents();
window.tryMacroComponents();
holders.forEach(h=>{assert.equal(h.added.length,1);h.added[0].onerror();assert.match(h.status.textContent,/연결 실패/);});
console.log('PASS Gold → Bitcoin → Copper → WTI, precise instruments, official widget, allowlist, single launch, fallback links.');
