'use strict';
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');
const clean=x=>JSON.parse(JSON.stringify(x));
const datum=(date,open,high,low,close,volume)=>({date,open,high,low,close,volume});
for(const [name,api,zone,count,legacy] of [
 ['korean-etf','TerminalETF','Asia/Seoul',39,'korean_etf_charts.json'],
 ['overseas-etf','TerminalOverseasETF','America/New_York',38,'overseas_etf_charts.json']
]){
 const base=fs.readFileSync(path.join(root,'assets',name+'.js'),'utf8');
 const context=vm.createContext({window:{},document:{readyState:'loading',addEventListener(){}}});
 vm.runInContext(base,context);
 const {aggregateCandles,displayCandles,candleLabel,candleStatus}=context.window[api];
 const raw=[
  datum('2026-01-01',103,112,102,110,4),datum('2025-12-29',110,112,104,105,12),
  datum('2026-01-05',112,130,111,127,20),datum('2026-01-02',110,115,99,102,8),
  datum('2026-01-06',127,129,111,124,undefined),datum('2026-02-30',1,2,1,2,50),
  datum('2026-01-07',200,100,90,100,50),datum('2026-01-01',999,1000,998,999,50),
 ];
 const weekly=clean(aggregateCandles(raw,'weekly'));
 assert.deepEqual(weekly,[{key:'2025-12-29',date:'2026-01-02',firstDate:'2025-12-29',label:'2026-01-02',open:110,high:115,low:99,close:102,volume:24,observations:3},
 {key:'2026-01-05',date:'2026-01-06',firstDate:'2026-01-05',label:'2026-01-06',open:112,high:130,low:111,close:124,volume:null,observations:2}]);
 assert.equal(aggregateCandles(raw,'daily').length,5);
 const monthly=clean(aggregateCandles(raw,'monthly'));
 assert.equal(monthly[1].firstDate,'2026-01-01');
 assert.equal(monthly[1].date,'2026-01-06');
 assert.equal(monthly[1].close,124);
 assert.equal(monthly[1].volume,null);
 assert.match(candleLabel(weekly[1],'weekly'),/2026-01-05 ~ 2026-01-06 · 2개 실제 거래일/);
 assert.match(candleStatus(weekly,'weekly',zone,new Date('2026-01-07T20:00Z')),/마지막 실제 종가 2026-01-06 · 현재 주 잠정/);
 assert.match(candleStatus(monthly,'monthly',zone,new Date('2026-02-02T21:00Z')),/마지막 실제 종가 2026-01-06 · 현재 월 관측값 없음/);
 const cut=[datum('2026-02-02',9,16,8,10,10),datum('2026-02-27',10,14,9,13,20),datum('2026-05-31',18,20,15,19,15)];
 const shown=displayCandles(cut,'monthly',3);
 // 2/27 falls before the clamped 2/28 cutoff; no synthetic month-end point.
 assert.deepEqual(clean(shown.map(r=>r.date)),['2026-05-31']);
 const input=process.env.ETF_CANDLE_FIXTURE_DIR||path.join(root,'data');
 const data=JSON.parse(fs.readFileSync(path.join(input,legacy),'utf8'));
 assert.equal(data.funds.length,count);
 for(const f of data.funds){
  const last=f.daily.at(-1);
  for(const kind of ['daily','weekly','monthly']){
   const series=displayCandles(f.daily,kind,3);
   assert.equal(series.at(-1).date,last.date,f.code+' last '+kind);
   assert.equal(series.at(-1).close,last.close,f.code+' close '+kind);
   assert.ok(series.every(r=>Number.isFinite(r.open)&&r.low<=r.open&&r.high>=r.close));
  }
 }
 for(const key of ['daily','weekly','monthly'])assert.match(base,new RegExp(key+":'"));
 assert.match(base,/data-etf-candle/);
 assert.match(base,/if\(period==='day'\)period=lastRange/);
 assert.match(base,/intraday\?p\.label:candleLabel/);
 console.log('PASS '+name+' '+count+' stored funds; no last date or close drift; explicit aggregate calendar/volume/range checks and original-time labels.');
}
