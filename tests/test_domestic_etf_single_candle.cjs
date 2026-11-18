'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const root=path.resolve(__dirname,'..'), read=p=>fs.readFileSync(path.join(root,p),'utf8');
const code=read('assets/korean-etf.js').replace("window.TerminalETF={","window.setTestState=(p,s)=>{payload=p;selected=s;};window.testDetail=detail;window.TerminalETF={");
let html='',focused=false;
const range={dataset:{etfPeriod:'6'}},candles={dataset:{etfCandle:'weekly'}};
const elem={
 'etf-detail':{get innerHTML(){return html;},set innerHTML(s){html=s;},querySelectorAll(q){return [q.includes('period')?range:candles];},querySelector(){return {focus(){focused=true;}};}},
 'etf-plot':{querySelector(){return {};}},
 'etf-tooltip':{},
};
const window={};vm.runInNewContext(code,{window,URL,document:{readyState:'loading',addEventListener(){},getElementById(id){return elem[id];}}});
const f=(code,date)=>({code,name:code,category:'test',issuer:'official',daily:[{date,open:99,high:108,low:95,close:103,volume:100}]});
window.setTestState({funds:[f('091160','2026-11-13'),f('466920','2026-11-13'),f('0148J0','2026-11-18')]},'091160');
window.testDetail();
assert.match(html,/보관 종가 2026-11-13/);assert.doesNotMatch(html,/표본 ETF|2026-11-18 거래소 일봉|보관 차트 보기/);
assert.equal((html.match(/id="etf-plot"/g)||[]).length,1);
for(const t of ['daily','weekly','monthly'])assert.ok(html.includes('data-etf-candle="'+t+'"'));
range.onclick();assert.match(html,/data-etf-period="6" class="active"/);candles.onclick();assert.ok(focused);assert.match(html,/data-etf-candle="weekly" class="active"/);
window.setTestState({funds:[f('0148J0','2026-11-18')]},'0148J0');window.testDetail();
assert.match(html,/보관 종가 2026-11-18/);assert.equal((html.match(/id="etf-plot"/g)||[]).length,1);
assert.doesNotMatch(read('index.html'),/data-etf-today=|etf-today-note/);
assert.match(read('index.html'),/korean-etf\.js\?v=20261119-october-etf/);
console.log('PASS one selected-fund continuous chart; actual archive dates; range and D/W/M controls; no duplicate day candle or quick picker.');
