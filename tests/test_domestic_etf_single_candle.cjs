'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const root=path.resolve(__dirname,'..');
const asset=fs.readFileSync(path.join(root,'assets/korean-etf.js'),'utf8');
const exportHook='window.TerminalETF={returns,series,safeURL,representatives,representativeSources,aggregateCandles,displayCandles,candleLabel,candleStatus};';
assert.ok(asset.includes(exportHook));
const ctx=vm.createContext({window:{},URL,document:{readyState:'loading',addEventListener(){}}});
vm.runInContext(asset.replace(exportHook,exportHook+'window.etfSample=recentComparison;'),ctx);
const data={
 '091160':[90685,91840,86415,89755,'#fd7991'],
 '466920':[17595,17900,17010,17395,'#fd7991'],
 '0148J0':[7050,7675,6985,7610,'#3bd6aa'],
 '0177X0':[7190,7815,7130,7795,'#3bd6aa'],
 '0207G0':[5505,5670,5355,5650,'#3bd6aa'],
 '0247S0':[5330,5470,5095,5385,'#3bd6aa'],
 '143860':[32595,32910,31830,31840,'#fd7991'],
 '364970':[6420,6495,6285,6295,'#fd7991'],
 '091180':[21705,21895,21170,21750,'#3bd6aa'],
 '487240':[21750,21985,20810,21460,'#fd7991'],
};
for(const [code,points] of Object.entries(data)){
 const prior=Object.freeze([{date:'2026-11-13',open:100,high:102,low:99,close:101}]);
 const out=ctx.window.etfSample({code,daily:prior});
 assert.match(out,/2026-11-18 거래소 일봉/);
 assert.match(out,/해당 거래일 한 봉으로, 보관 일봉·주봉·월봉과 전체 수익률 순위에는 합치지 않았습니다/);
 assert.ok(out.includes('https://etfro.com/etf/'+code));
 if(code==='091180'||code==='487240')assert.ok(out.includes('전 거래일 종가 대비 '+(code==='091180'?'+1.12%':'+1.42%')));
 assert.equal((out.match(/<rect\b/g)||[]).length,1);
 assert.equal((out.match(/<svg\b/g)||[]).length,1);
 assert.doesNotMatch(out,/NaN|undefined|<script|<iframe/);
 for(const [i,label] of ['시가','고가','저가','종가'].entries()) assert.ok(out.includes(label+' '+points[i].toLocaleString('ko-KR')+'원'));
 assert.ok(out.includes('fill="'+points[4]));
 assert.equal(prior.at(-1).date,'2026-11-13');
 assert.equal(ctx.window.etfSample({code,daily:[{date:'2026-11-18'}]}),'');
 assert.equal(ctx.window.etfSample({code,daily:[{date:'2026-11-19'}]}),'');
}
for(const code of ['069500','constructor','__proto__','"><script>'])assert.equal(ctx.window.etfSample({code}),'');
const html=fs.readFileSync(path.join(root,'index.html'),'utf8');
assert.match(html,/korean-etf\.js\?v=20261118-ten-editorial-candles/);
console.log('PASS all ten exact OHLCs and links/date; candle body color vs. prior close text; only one original SVG; immutable archive, no unsupported symbol or duplicate current data.');
