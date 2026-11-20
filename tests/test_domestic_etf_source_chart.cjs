const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const root=path.resolve(__dirname,'..'),text=f=>fs.readFileSync(path.join(root,f),'utf8');
const payload=JSON.parse(text('data/korean_etf_charts.json')),nodes={};
const ctx={URL,Date,Number,String,Math,Array,console,
 document:{readyState:'loading',addEventListener(){},getElementById:id=>nodes[id]||(nodes[id]={innerHTML:'',textContent:'',querySelector:()=>null})},window:{}};
const raw=text('assets/korean-etf.js');
const start='window.TerminalETF={';
assert.equal(raw.split(start).length,2);
vm.runInNewContext(raw.replace(start,start+'originalEtfChart,detail,setData:p=>payload=p,setSelected:s=>selected=s,'),ctx);
const etf=ctx.window.TerminalETF,archived=JSON.stringify(payload);
etf.setData(payload);
for(const f of payload.funds){
 etf.setSelected(f.code);
 etf.detail();
 const detail=nodes['etf-detail'].innerHTML, matched=detail.match(/href="([^"]+)" target="_blank" rel="noopener noreferrer">TradingView 일봉 원본/);
 assert.ok(matched,f.code);
 const url=new URL(matched[1].replace('&amp;','&'));
 assert.equal(url.origin,'https://www.tradingview.com');
 assert.equal(url.pathname,'/chart/');
 assert.equal(url.searchParams.get('symbol'),'KRX:'+f.code);
 assert.equal(url.searchParams.get('interval'),'D');
 assert.match(detail,/외부 차트이며 아래 보관 일봉·수익률과 별개/);
 assert.match(detail,new RegExp(f.daily.at(-1).date));
}
assert.equal(JSON.stringify(payload),archived);
for(const value of [null,123456,'ABC','<1234>','12345\\','1234567','JAVASCRIPT:ALERT(1)'])assert.equal(etf.originalEtfChart(value),'');
assert.match(text('index.html'),/assets\/korean-etf\.js\?v=20261120-fixed-daily-source-links/);
console.log('PASS all '+payload.funds.length+' domestic ETF original daily routes, code validation, and archive separation');
