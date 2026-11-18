/* Official provider-owned embed scripts: display only, no extraction of their quotes. */
'use strict';
const groups=Object.freeze({AMEX:'XOP XLE CRAK XLU FDN XLK IHF XLP XLY XLRE XLV KRE KBE XLF XLI XLC FAN IHI XLB IAI XHB XRT XME BATT XPH LIT XAR XBI TAN',NASDAQ:'CIBR CLOU SOXX SMH IBB ICLN',CBOE:'IGV IYT ITA'});
const options=new URLSearchParams(location.search);
const symbol=options.get('symbol')||'';
const [exchange,ticker]=symbol.split(':');
const target=document.getElementById('note');
const link=(url,label)=>{const a=document.createElement('a');a.href=url;a.target='_blank';a.rel='noopener noreferrer nofollow';a.textContent=label;return a;};
function vendorScript(src){const s=document.createElement('script');s.type='text/javascript';s.async=true;s.src=src;return s;}
function mountQuoteLinks(){
 const holder=document.getElementById('ql'), chart=document.createElement('div');
 holder.hidden=false;chart.className='ql-stockchart';
 Object.assign(chart.dataset,{symbol:ticker,type:'candles',range:'1m',size:'full',theme:'dark'});
 chart.append(link('https://www.quotelinks.com/etfs/'+ticker.toLowerCase()+'.html',ticker+' ETF chart'),' by ',link('https://www.quotelinks.com/','Quotelinks'));
 holder.append(chart,vendorScript('https://www.quotelinks.com/widgets/stockchart.js'));
 target.textContent='Quotelinks · 미국 정규장 종가 기반, 분할 조정. 조회 길이에 따라 일봉·주봉·월봉 자동 전환. 최신 거래일은 차트에서 확인.';
}
function mountTradingView(){
 const holder=document.getElementById('tv'), credit=document.getElementById('credit');
 holder.hidden=false;
 const attribution=document.createElement('span');attribution.className='trademark';attribution.textContent=' by TradingView';
 credit.append(link('https://www.tradingview.com/symbols/'+symbol.replace(':','-')+'/',ticker+' ETF chart'),attribution);
 const script=vendorScript('https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js');
 const interval=options.get('interval');
 script.textContent=JSON.stringify({symbol,interval:['D','W','M'].includes(interval)?interval:'D',style:'1',timezone:'America/New_York',locale:'kr',theme:'dark',autosize:true,hide_top_toolbar:false,hide_side_toolbar:true,hide_legend:false,hide_volume:false,allow_symbol_change:false,save_image:false,withdateranges:false,calendar:false});
 holder.append(script);
 target.textContent='TradingView · Cboe One 지연 표시. 도구 모음에서 일봉·주봉·월봉 선택. 최신 거래일은 차트에서 확인.';
}
if(!/^(?:AMEX|NASDAQ|CBOE):[A-Z]{2,5}$/.test(symbol)||!groups[exchange]?.split(' ').includes(ticker)){
 target.textContent='지원 대상 ETF를 선택하세요.';
}else if(exchange==='CBOE'){
 mountQuoteLinks();
}else{
 mountTradingView();
}
