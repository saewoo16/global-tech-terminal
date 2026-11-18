'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const root=path.resolve(__dirname,'..'),html=fs.readFileSync(root+'/index.html','utf8');
const js=html.match(/<script>\n([\s\S]*?)<\/script>/)[1];
const elements=new Map();
function element(id){if(!elements.has(id))elements.set(id,{id,innerHTML:'',textContent:'',links:[],append(...parts){this.links=parts},classList:{toggle(){}}});return elements.get(id);}
const c=vm.createContext({URL,window:{},document:{readyState:'loading',getElementById:element,querySelectorAll:()=>[],addEventListener(){},createElement:()=>({}),createTextNode:text=>({textContent:text})}});
vm.runInContext(js,c);
const old=Object.freeze([Object.freeze(['2026-11-16',196800])]);
for(const [symbol,close,pct] of [['KRX:005930','194,700원','+2.31%'],['KRX:000660','1,144,000원','+4.19%']]){
 c.renderExplorerLatestClose({symbol},{close:196800,priceCurrency:'KRW'},old);
 assert.equal(element('latest-close-label').textContent,'정규장 종가 · 비조정');
 assert.equal(element('last').textContent,close);
 const info=element('priceinfo');
 assert.ok(info.textContent.includes(pct));
 assert.match(info.textContent,/2026-11-18 KST 정규장.*별도 보관 조정종가\(최종 거래일 2026-11-16/);
 assert.deepEqual(info.links.filter(x=>x.href).map(x=>x.href),['https://www.newspim.com/news/view/20261118001065','https://www.yna.co.kr/amp/view/AKR20261118045151008']);
 assert.equal(old[0][1],196800);
 c.renderExplorerLatestClose({symbol},{close:200000,priceCurrency:'KRW'},[['2026-11-19',200000]]);
 assert.equal(element('latest-close-label').textContent,'최근 조정종가');
 assert.equal(element('last').textContent,'200,000 KRW');
}
for(const symbol of ['KRX:005935','TWSE:2330','constructor','NASDAQ:NVDA'])assert.equal(c.explorerKoreaReportedClose(symbol),null);
assert.match(js,/const official=explorerTaiwanClose\(r.symbol,prices.at\(-1\)\?\.\[0\]\), priceInfo=/);
console.log('PASS both 11/18 KRX closes next to selection, two sources, dates/rates separated from archival chart, no future override or Taiwan changes.');
