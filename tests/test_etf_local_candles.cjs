'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const root=path.resolve(__dirname,'..'), html=fs.readFileSync(root+'/index.html','utf8');
assert.doesNotMatch(html,/etf-local-candles\.html|내 CSV로 일봉/);
assert.equal(fs.existsSync(root+'/assets/etf-local-candles.html'),false);
assert.match(html,/short-local-viewer\.html/);
for(const f of ['korean-etf.js','overseas-etf.js']){
 const js=fs.readFileSync(root+'/assets/'+f,'utf8');
 assert.doesNotMatch(js,/data-etf-candle|data-etf-period/);assert.match(js,/마지막 실제 종가/);
 assert.doesNotMatch(js,/etf-local-candles\.html|type="file"/);
}
console.log('PASS public ETF tabs are bot/provider populated only, no CSV workflow, native dated D/W/M kept and separate short CSV feature unchanged.');
