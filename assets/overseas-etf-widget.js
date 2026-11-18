/* Official TradingView Symbol Overview, display only; no capture/redistribution. */
'use strict';
const groups={AMEX:'XOP XLE CRAK XLU FDN XLK IHF XLP XLY XLRE XLV KRE KBE XLF XLI XLC FAN IHI XLB IAI XHB XRT XME BATT XPH LIT XAR XBI TAN',NASDAQ:'CIBR CLOU SOXX SMH IBB ICLN',CBOE:'IGV IYT ITA'};
const s=new URLSearchParams(location.search).get('symbol')||'', [exchange,ticker]=s.split(':');
if(!/^(?:AMEX|NASDAQ|CBOE):[A-Z]{2,5}$/.test(s)||!groups[exchange]?.split(' ').includes(ticker)){
  document.getElementById('chart').textContent='지원 대상 ETF를 선택하세요.';
}else{
  const a=document.createElement('a'), span=document.createElement('span'), script=document.createElement('script');
  a.href='https://www.tradingview.com/symbols/'+s.replace(':','-')+'/';
  a.target='_blank';a.rel='noopener nofollow';a.textContent=ticker+' ETF chart';
  span.className='trademark';span.textContent=' by TradingView';
  document.getElementById('credit').append(a,span);
  script.type='text/javascript';script.async=true;script.src='https://s3.tradingview.com/external-embedding/embed-widget-symbol-overview.js';
  script.textContent=JSON.stringify({symbols:[[ticker,s+'|1M']],dateRanges:['1d|1','1w|60','1m|1D'],chartOnly:false,locale:'kr',colorTheme:'dark',width:'100%',height:'340',autosize:false,hideMarketStatus:false,hideDateRanges:false,hideSymbolLogo:false,changeMode:'price-and-percent'});
  document.getElementById('tv').append(script);
}
