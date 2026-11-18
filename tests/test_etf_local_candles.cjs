const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto'),vm=require('node:vm');
const html=fs.readFileSync(path.join(__dirname,'..','assets','etf-local-candles.html'),'utf8');
const raw=tag=>html.match(new RegExp('<'+tag+'>([\\s\\S]*?)</'+tag+'>'))[1];
const hash=tag=>crypto.createHash('sha256').update(raw(tag)).digest('base64');
assert.ok(html.includes("default-src 'none'; connect-src 'none'; base-uri 'none'; form-action 'none'"));
assert.ok(html.includes("script-src 'sha256-"+hash('script')+"'"));
assert.ok(html.includes("style-src 'sha256-"+hash('style')+"'"));
assert.doesNotMatch(html,/<(?:script\s|link\s|img\s|iframe\s|form\s)|\b(?:on[a-z]{3,16}|style)\s*=/i);
assert.doesNotMatch(raw('script'),/\b(?:fetch|postMessage|sendBeacon|XMLHttpRequest|localStorage|sessionStorage|indexedDB)\b/);
const items=new Map(), listeners=new Map(), ctx2d={scales:0,candles:0,scale(){this.scales++},clearRect(){},fillText(){},beginPath(){},moveTo(){},lineTo(){},stroke(){},fillRect(){this.candles++}};
function node(id=''){
 return {id,value:'',checked:false,files:[],hidden:false,textContent:'',children:[],dataset:{},attrs:{},handlers:{},
  classList:{toggle(){}}, clientWidth:350,clientHeight:240,
  addEventListener(name,fn){this.handlers[name]=fn},setAttribute(name,value){this.attrs[name]=value},
  replaceChildren(){this.children=[]},append(...kids){this.children.push(...kids)},getContext(kind){assert.equal(kind,'2d');return ctx2d}
 };
}
const $=id=>{if(!items.has(id))items.set(id,node(id));return items.get(id)};
const buttons=['D','W','M'].map(p=>Object.assign(node(),{dataset:{period:p}}));
const context={Intl,TextDecoder,URLSearchParams,window:{location:{search:'?market=US'},devicePixelRatio:2,addEventListener(){}},
 document:{readyState:'loading',getElementById:$,querySelectorAll:()=>buttons,addEventListener:(id,fn)=>listeners.set(id,fn),createElement:()=>node()}};
vm.createContext(context);
const src=raw('script').replace("if(document.readyState==='loading')","globalThis.api={day,importCandles,aggregate,read,fileText,reset};if(document.readyState==='loading')");
vm.runInContext(src,context);
const {day,importCandles,aggregate}=context.api;
const now='2026-11-18';
assert.equal(day('2026.11.16'),'2026-11-16');
assert.equal(day('20261116'),'2026-11-16');
assert.equal(day('2026/11/16'),'2026-11-16');
for(const bad of ['2026/11.16','2026-02-29','2026-11-16T21:00:00Z','2026-2-3','2026-11-00'])assert.equal(day(bad),'');
const base=[
 '﻿Date,Open,High,Low,Close,Volume,Ticker,Market,Adj Close',
 '2026-11-02,105,107,100,101,13,XLK,NASDAQ,99',
 '2026-10-30,100,103,99,101,"1,000",XLK,NASDAQ,98',
 '2026-11-03,101,110,100,109,9007199254740993,XLK,NASDAQ,96',
 '2026-11-09,99,103,90,93,40,XLK,NASDAQ,91'
].join('\r\n');
const input=importCandles(base,'US','XLK','2026-11-09',now);
const d=aggregate(input.rows,'D'),w=aggregate(input.rows,'W'),m=aggregate(input.rows,'M');
const fields=x=>Array.from(x,q=>[q.start,q.end,q.o,q.h,q.l,q.c,String(q.v),q.n]);
assert.equal(input.symbol,'XLK');
assert.deepEqual(Array.from(d,x=>x.start),['2026-10-30','2026-11-02','2026-11-03','2026-11-09']);
assert.deepEqual(fields(w),[
 ['2026-10-30','2026-10-30',100,103,99,101,'1000',1],
 ['2026-11-02','2026-11-03',105,110,100,109,'9007199254741006',2],
 ['2026-11-09','2026-11-09',99,103,90,93,'40',1]
]);
assert.deepEqual(fields(m),[
 ['2026-10-30','2026-10-30',100,103,99,101,'1000',1],
 ['2026-11-02','2026-11-09',105,110,90,93,'9007199254741046',3]
]);
assert.equal(input.rows[2].c,109);
const kr=['거래일자,시가,고가,저가,종가,거래량(주),종목코드,시장구분',
 '20261116,"1,000","1,010",995,1003,5,069500,KOSPI'].join('\n');
assert.deepEqual(fields(importCandles(kr,'KRX','069500','2026-11-16',now).rows),[
 ['2026-11-16','2026-11-16',1000,1010,995,1003,'5',1]
]);
for(const [problem,pattern] of [
 [base.replace('XLK,NASDAQ','SPY,NASDAQ'),/ETF 코드/],
 [base.replace('XLK,NASDAQ','XLK,KOSPI'),/시장/],
 [base.replace('2026-11-02','2026-11-03'),/중복/],
 [base.replace('2026-11-02','2026-11-01'),/평일/],
 [base.replace('2026-11-02','2026-02-30'),/날짜/],
 [base.replace('2026-11-02','2026-11-02T06:00:00Z'),/날짜/],
 [base.replace('105,107,100','105,104,100'),/시고저종/],
 [base.replace(',13,',',1.3,'),/거래량/],
 [base.replace('Close,Volume','Adjusted,Volume'),/열/],
 [base.replace('"1,000"','"1000'),/따옴표|줄바꿈/],
 [base.replace('XLK,NASDAQ','<img>,NASDAQ'),/ETF 코드/]
])assert.throws(()=>importCandles(problem,'US','XLK','2026-11-09',now),pattern);
assert.throws(()=>importCandles(base,'US','XLK','2026-11-10',now),/마지막 날짜와 일치/);
assert.throws(()=>importCandles(base,'US','XLK','2026-11-19',now),/현지 마지막 거래일/);
assert.throws(()=>importCandles(kr,'KRX','69500','2026-11-16',now),/티커/);
const mkFile=text=>({size:Buffer.byteLength(text),arrayBuffer:async()=>Buffer.from(text)});
(async()=>{
 listeners.get('DOMContentLoaded')();assert.equal($('market').value,'US');
 $('ticker').value='XLK';$('session').value='2026-11-09';$('file').files=[mkFile(base)];$('confirm').checked=true;
 await $('read').handlers.click();
 assert.equal($('result').hidden,false);assert.match($('heading').textContent,/XLK · 일봉/);
 assert.equal($('rows').children.length,4);assert.equal(ctx2d.candles,4);assert.equal($('chart').width,700);
 buttons[1].handlers.click();assert.match($('heading').textContent,/주봉/);
 assert.equal($('rows').children.length,3);assert.equal(buttons[1].attrs['aria-pressed'],'true');
 buttons[2].handlers.click();assert.match($('heading').textContent,/월봉/);
 assert.equal($('rows').children.length,2);assert.equal($('unit').textContent,'USD');
 let finish;
 $('file').files=[{size:1,arrayBuffer:()=>new Promise(r=>{finish=r;})}];
 const late=$('read').handlers.click();$('clear').handlers.click();
 finish(Buffer.from(base));await late;
 assert.equal($('result').hidden,true);assert.equal($('file').value,'');assert.equal($('confirm').checked,false);
 assert.match($('status').textContent,/지워졌어요/);
 await assert.rejects(()=>context.api.fileText({size:8000001}),/8MB/);
 console.log('PASS isolated ETF reader CSP, CSV market/date/session validation, exact OHLCV D/W/M rollups, mobile canvas, a11y controls, and read cancellation');
})().catch(e=>{console.error(e);process.exitCode=1});
