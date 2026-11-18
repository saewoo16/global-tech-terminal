/* Source-backed Overseas ETF snapshots. No synthetic intraday prices. */
(function(){
'use strict';
const $=id=>document.getElementById(id),esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt=(v,n=2)=>Number.isFinite(v)?v.toLocaleString('ko-KR',{maximumFractionDigits:n,minimumFractionDigits:n}):'—';
const stamp=v=>{const d=new Date(v);return Number.isNaN(d.getTime())?String(v||'미확인'):d.toLocaleString('ko-KR',{timeZone:'Asia/Seoul',hour12:false})+' KST';};
const pct=v=>Number.isFinite(v)?`${v>0?'+':''}${fmt(v,2)}%`:'—';
let payload=null,monthOverlay=null,selected='',period='3',lastRange='3',candleKind='daily',group='all',query='',sort='day',loading=false,lastLoad=0;
function returns(f,months=1){const d=f.daily||[];if(d.length<2)return null;const last=d.at(-1),cut=new Date(last.date+'T00:00:00Z');const day=cut.getUTCDate();cut.setUTCDate(1);cut.setUTCMonth(cut.getUTCMonth()-months);const end=new Date(Date.UTC(cut.getUTCFullYear(),cut.getUTCMonth()+1,0)).getUTCDate();cut.setUTCDate(Math.min(day,end));const base=d.filter(p=>p.date<=cut.toISOString().slice(0,10)).at(-1);return Number.isFinite(last.close)&&Number.isFinite(base?.close)&&base.close>0?(last.close/base.close-1)*100:null;}
function dailyReturn(f){const d=f.daily||[],last=d.at(-1),prev=d.at(-2);return Number.isFinite(last?.close)&&Number.isFinite(prev?.close)&&prev.close>0?(last.close/prev.close-1)*100:null;}
function weeklyReturn(f){const d=f.daily||[],last=d.at(-1);if(!Number.isFinite(last?.close))return null;const cut=new Date(last.date+'T00:00:00Z');cut.setUTCDate(cut.getUTCDate()-7);const base=d.filter(p=>p.date<=cut.toISOString().slice(0,10)).at(-1);return Number.isFinite(base?.close)&&base.close>0?(last.close/base.close-1)*100:null;}
const isoSession=v=>typeof v==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(v)?v:null;
function sessionOf(report){const e=report?.entry,v=e?.sessionVerification;return e?.sessionStatus==='closed'&&isoSession(e.date)&&v?.exchangeDate===e.date?e.date:null;}
function freshness(funds,session){const target=isoSession(session),dates=funds.map(f=>isoSession(f.daily?.at(-1)?.date)),known=dates.filter(Boolean).sort(),latest=known.at(-1)||null;return {target,latest,count:funds.length,current:target===null?null:dates.filter(d=>d===target).length};}
function statusLabel(funds,session){const {target,latest,count,current}=freshness(funds,session),saved=latest?`최신 보관 일봉 ${latest} ET`:'보관 일봉 없음';if(!target)return `최신 완료 미국장과 ETF 대조 미확인 · ${saved}`;if(!count)return `미국장 ${target} ET · 보관 ETF 없음`;if(current===count)return `미국장 ${target} ET · 해당 세션 일봉 ${current}/${count}`;return `미국장 ${target} ET · 해당 세션 일봉 ${current}/${count} · ${saved} · 해당일 ETF 원자료 미반영, 보관 자료는 역사 차트로만 표시합니다.`;}
async function getVerifiedSession(){try{return sessionOf(await fetchETFData('./data/us-analysis-latest.json',8000));}catch{return null;}}
function listReturn(f){return sort==='month'?returns(f):sort==='week'?weeklyReturn(f):dailyReturn(f);}
function filtered(){return(payload?.funds||[]).filter(f=>(group==='all'||f.group===group)&&[f.name,f.code,f.category,f.issuer,...(f.holdings?.top5||[]).map(m=>m.name)].join(' ').toLowerCase().includes(query.toLowerCase())).sort((a,b)=>(listReturn(b)??-Infinity)-(listReturn(a)??-Infinity));}
function representativeHoldings(f){const h=f.holdings,rows=h?.top5;if(h?.status!=='verified'||!Array.isArray(rows)||rows.length<3||rows.some(m=>!m||typeof m.weightPct!=='number'||!Number.isFinite(m.weightPct)||m.weightPct<=0||m.weightPct>100||!(m.name||m.ticker)))return [];return [...rows].sort((a,b)=>b.weightPct-a.weightPct).slice(0,3);}
function representatives(f){const rows=representativeHoldings(f);if(!rows.length)return '';return `<span class="etf-representatives">(${rows.map(m=>esc(m.name||m.ticker)).join(' / ')})</span>`;}
function representativeSources(f){const h=f.holdings;if(!representativeHoldings(f).length)return '<p>구성종목 편입비중 미확인</p>';return `<p>편입비중 상위 3종목 · 실제 구성 기준 ${esc(h.asOf||'미확인')} · 최신 시세 기준일과 별개입니다.</p>`;}
function selectionSources(f){const e=f.selectionEvidence;if(!e?.disclosure)return '';const links=[[e.officialSourceUrl,'운용사 구성종목 원자료'],[e.officialAum?.sourceUrl,'운용사 순자산 기준일 원자료']];return `<p class="etf-selection-disclosure">${esc(e.disclosure)}</p>${links.filter(([url])=>url).map(([url,title])=>`<div><a href="${esc(safeURL(url))}" target="_blank" rel="noopener noreferrer">${title} ↗</a></div>`).join('')}`;}

function countsLabel(){
 const funds=payload?.funds||[], counts={industry:0,theme:0};
 for(const f of funds)if(Object.hasOwn(counts,f.group))counts[f.group]++;
 return '업종 '+counts.industry+'개 · 테마 '+counts.theme+'개';
}
function list(){const funds=filtered();$('us-etf-count').textContent=`${funds.length}개 ETF (${countsLabel()}) · 목록 수익률은 ${sort==='month'?'최근 1달':sort==='week'?'최근 1주일':'전일 종가 대비 1일 등락'}`;if(!funds.some(f=>f.code===selected))selected=funds[0]?.code||'';$('us-etf-list').innerHTML=funds.map(f=>{const r=listReturn(f);return `<button type="button" class="etf-choice ${f.code===selected?'active':''}" data-etf="${esc(f.code)}" aria-pressed="${f.code===selected}"><span class="etf-return ${r>=0?'up':'down'}">${pct(r)}</span><strong>${esc(f.category)} <small>${f.group==='industry'?'업종':'테마'}</small></strong><small>${esc(f.code)} (${esc(f.name)})</small>${representatives(f)}</button>`}).join('')||'<p class="etf-empty">검색 결과가 없습니다.</p>';$('us-etf-list').querySelectorAll('[data-etf]').forEach(b=>b.onclick=()=>{selected=b.dataset.etf;list();detail();});}
// Exchange dates are session-local; UTC arithmetic here is calendar-only.
const candleNames={daily:'일봉',weekly:'주봉',monthly:'월봉'};
function dateKey(day){
  if(typeof day!=='string'||!/^\d{4}-\d{2}-\d{2}$/.test(day))return null;
  const t=new Date(day+'T00:00:00Z');
  return Number.isFinite(t.valueOf())&&t.toISOString().slice(0,10)===day?t:null;
}
function candleKey(day,kind){
  const d=dateKey(day);if(!d)return null;
  if(kind==='monthly')return day.slice(0,7);
  if(kind!=='weekly')return day;
  d.setUTCDate(d.getUTCDate()-((d.getUTCDay()+6)%7));
  return d.toISOString().slice(0,10);
}
function aggregateCandles(raw,kind='daily'){
  const seen=new Set();
  const clean=(Array.isArray(raw)?raw:[]).slice().sort((a,b)=>String(a?.date).localeCompare(String(b?.date))).filter(r=>{
    if(!dateKey(r?.date)||seen.has(r.date)||![r.open,r.high,r.low,r.close].every(Number.isFinite)||r.low<=0||r.low>Math.min(r.open,r.close)||r.high<Math.max(r.open,r.close))return false;
    seen.add(r.date);return true;
  });
  const groups=new Map();
  for(const day of clean){
    const key=candleKey(day.date,kind), volume=Number.isSafeInteger(day.volume)&&day.volume>=0?day.volume:null;
    let row=groups.get(key);
    if(!row){
      row={key,date:day.date,firstDate:day.date,label:day.date,open:day.open,high:day.high,low:day.low,close:day.close,volume,observations:1};
      groups.set(key,row);continue;
    }
    row.date=day.date;row.label=day.date;row.high=Math.max(row.high,day.high);row.low=Math.min(row.low,day.low);row.close=day.close;row.observations++;
    row.volume=row.volume!==null&&volume!==null&&Number.isSafeInteger(row.volume+volume)?row.volume+volume:null;
  }
  return [...groups.values()];
}
function displayCandles(raw,kind,months){
  const all=aggregateCandles(raw,kind);
  if(!all.length)return all;
  const cut=dateKey(all.at(-1).date), dom=cut.getUTCDate();
  cut.setUTCDate(1);cut.setUTCMonth(cut.getUTCMonth()-months);
  const end=new Date(cut);end.setUTCMonth(end.getUTCMonth()+1,0);
  cut.setUTCDate(Math.min(dom,end.getUTCDate()));
  return all.filter(row=>row.date>=cut.toISOString().slice(0,10));
}
function todayIn(zone,at=new Date()){
  const parts=new Intl.DateTimeFormat('en-US',{year:'numeric',month:'2-digit',day:'2-digit',timeZone:zone}).formatToParts(at);
  const read=k=>parts.find(p=>p.type===k)?.value;
  return [read('year'),read('month'),read('day')].join('-');
}
function candleLabel(row,kind){
  return kind==='daily'?row.date:row.firstDate+' ~ '+row.date+' · '+row.observations+'개 실제 거래일';
}
function candleStatus(rows,kind,zone,at){
  if(!rows.length)return candleNames[kind]+' · 표시할 관측값 없음';
  const tail=rows.at(-1);
  const base=candleNames[kind]+' '+rows.length+'개 · '+rows[0].firstDate+' ~ '+tail.date+' · 마지막 실제 종가 '+tail.date;
  if(kind==='daily')return base;
  const same=candleKey(todayIn(zone,at),kind)===tail.key;
  const unit=kind==='weekly'?'주':'월';
  return base+(same?' · 현재 '+unit+' 잠정, 확인된 거래일만':' · 현재 '+unit+' 관측값 없음 · 저장 묶음의 전체 거래일 여부 미확인');
}

function series(f){if(period==='day')return(f.intraday?.points||[]).filter(p=>Number.isFinite(p.price)).map(p=>({...p,label:p.time.includes('T')?p.time.slice(11,16):p.time,close:p.price}));return displayCandles(f.daily,candleKind,Number(period));}
function plot(f){const data=series(f),intraday=period==='day';if(data.length<(intraday?2:1)){$('us-etf-plot').innerHTML=`<div class="etf-empty">${intraday?'당일 장중 시세가 아직 확보되지 않았습니다. 일봉을 선택해 주세요.':'이 기간의 차트 자료가 충분하지 않습니다.'}</div>`;$('us-etf-tooltip').textContent='';return;}
const W=1000,H=440,L=18,R=88,T=25,B=55,priceH=280,volumeY=330,volumeH=48,step=(W-L-R)/data.length;
let lo=Math.min(...data.map(p=>intraday?p.close:p.low)),hi=Math.max(...data.map(p=>intraday?p.close:p.high));const pad=(hi-lo)*.07||hi*.01||1;lo-=pad;hi+=pad;const minute=p=>{const match=String(p.label).match(/(\d{2}):(\d{2})(?::\d{2})?$/);return match?Number(match[1])*60+Number(match[2]):null;},minutes=data.map(minute),timed=intraday&&minutes.every(Number.isFinite)&&minutes.at(-1)>minutes[0];const y=v=>T+(hi-v)/(hi-lo)*priceH,x=i=>timed?L+8+(minutes[i]-minutes[0])/(minutes.at(-1)-minutes[0])*(W-L-R-16):L+(i+.5)*step,vol=Math.max(...data.map(p=>p.volume||0),1);let svg=`<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(f.name)} ${intraday?'당일 장중':candleNames[candleKind]} 가격 및 거래량 차트">`;
for(let i=0;i<5;i++){const v=lo+(hi-lo)*i/4,yy=y(v);svg+=`<line x1="${L}" x2="${W-R}" y1="${yy}" y2="${yy}" stroke="#2b3a55"/><text x="${W-R+10}" y="${yy+4}" fill="#91a5c3" font-size="12">${fmt(v)}</text>`;}
if(intraday)svg+=`<polyline points="${data.map((p,i)=>`${x(i)},${y(p.close)}`).join(' ')}" fill="none" stroke="#a3baff" stroke-width="2.5"/>`;
data.forEach((p,i)=>{const color=intraday?'#6b85bd':p.close>=p.open?'#3bd6aa':'#fd7991',xx=x(i),width=Math.max(1,step*.65);if(!intraday)svg+=`<line x1="${xx}" x2="${xx}" y1="${y(p.high)}" y2="${y(p.low)}" stroke="${color}"/><rect x="${xx-width/2}" y="${Math.min(y(p.open),y(p.close))}" width="${width}" height="${Math.max(1,Math.abs(y(p.open)-y(p.close)))}" fill="${color}"/>`;if(Number.isFinite(p.volume))svg+=`<rect x="${xx-width/2}" y="${volumeY+volumeH-p.volume/vol*volumeH}" width="${width}" height="${p.volume/vol*volumeH}" fill="${color}" opacity=".55"/>`;});
for(const i of [...new Set([0,Math.floor(data.length/3),Math.floor(data.length*2/3),data.length-1])])svg+=`<text x="${x(i)}" y="${H-22}" text-anchor="${i===0?'start':i===data.length-1?'end':'middle'}" fill="#91a5c3" font-size="12">${esc(data[i].label)}</text>`;
svg+=`<text x="${L}" y="${volumeY-5}" fill="#91a5c3" font-size="11">거래량</text><line id="us-etf-crosshair" y1="${T}" y2="${volumeY+volumeH}" stroke="#a6b9db" stroke-dasharray="4 4" visibility="hidden"/></svg>`;$('us-etf-plot').innerHTML=svg;
const show=i=>{const p=data[i];$('us-etf-tooltip').textContent=`${intraday?p.label:candleLabel(p,candleKind)} (ET) · ${intraday?'가격 '+fmt(p.close)+' USD':'시가 '+fmt(p.open)+' · 고가 '+fmt(p.high)+' · 저가 '+fmt(p.low)+' · 종가 '+fmt(p.close)+' USD'}${Number.isFinite(p.volume)?' · 거래량 '+fmt(p.volume,0)+'주':''}`;};show(data.length-1);const chart=$('us-etf-plot').querySelector('svg');chart.onpointermove=e=>{const rect=chart.getBoundingClientRect(),i=Math.max(0,Math.min(data.length-1,(timed?data.reduce((best,p,j)=>Math.abs(x(j)-(e.clientX-rect.left)/rect.width*W)<Math.abs(x(best)-(e.clientX-rect.left)/rect.width*W)?j:best,0):Math.floor(((e.clientX-rect.left)/rect.width*W-L)/step)))),line=$('us-etf-crosshair');line.setAttribute('x1',x(i));line.setAttribute('x2',x(i));line.setAttribute('visibility','visible');show(i);};chart.onpointerleave=()=>{$('us-etf-crosshair').setAttribute('visibility','hidden');show(data.length-1);};}
function safeURL(url){try{const u=new URL(url);return ['https:','http:'].includes(u.protocol)?u.href:'#';}catch{return '#';}}
// TradingView canonical ETF pages verified, no market-data queries made here.
const widgetGroups=Object.freeze({AMEX:'XOP XLE CRAK XLU FDN XLK IHF XLP XLY XLRE XLV KRE KBE XLF XLI XLC FAN IHI XLB IAI XHB XRT XME BATT XPH LIT XAR XBI TAN',NASDAQ:'CIBR CLOU SOXX SMH IBB ICLN',CBOE:'IGV IYT ITA'});
function widgetSymbol(code){return Object.entries(widgetGroups).find(([,members])=>members.split(' ').includes(code))?.[0]+':'+code;}
function widgetProviderLink(symbol){return /^((?:AMEX|NASDAQ|CBOE):[A-Z]{2,5})$/.test(symbol)?'https://www.tradingview.com/symbols/'+symbol.replace(':','-')+'/':null;}
function providerPanel(f){
 const symbol=widgetSymbol(f.code),tv=widgetProviderLink(symbol);if(!tv)return '';
 const ql=symbol.startsWith('CBOE:'),provider=ql?'Quotelinks':'TradingView';
 const url=ql?'https://www.quotelinks.com/etfs/'+f.code.toLowerCase()+'.html':tv;
 const timing=ql?'정규장 종가 기반 · 제공사 독립 차트. 위 일봉·주봉·월봉 선택 결과는 보관 캔들에서 확인하세요.':'Cboe One 지연 시세 · 선택한 일봉·주봉·월봉으로 연결합니다.';
 return '<section class="etf-sources" aria-label="외부 제공사 ETF 캔들"><p><strong>'+provider+' ETF 캔들</strong> <a href="'+url+'" target="_blank" rel="noopener noreferrer">제공사에서 열기 ↗</a></p><p>'+timing+' 최신 표시일은 차트에서 확인하세요. 위 보관 캔들 및 순위와는 별도입니다.</p><div id="us-etf-widget-view"></div></section>';
}
function mountProviderPanel(f){
 const target=$('us-etf-widget-view'),symbol=widgetSymbol(f.code);
 if(!target||!widgetProviderLink(symbol)||window.location?.hash.split('/')[0]!=='#overseas-etf')return;
 if(period==='day'){
   target.textContent='당일 장중 모드에서는 위 보관 장중 자료만 표시합니다. 일봉·주봉·월봉을 선택하면 제공사 차트가 열립니다.';return;
 }
 const interval={daily:'D',weekly:'W',monthly:'M'}[candleKind];
 if(!interval)return;
 const frame=document.createElement('iframe');
 frame.title=f.code+' 외부 제공사 ETF 캔들';
 frame.src='./assets/overseas-etf-widget.html?v=20261118-provider-candles&symbol='+encodeURIComponent(symbol)+'&interval='+interval;
 frame.setAttribute('sandbox','allow-scripts allow-popups allow-popups-to-escape-sandbox');
 frame.setAttribute('referrerpolicy','no-referrer');
 frame.style.cssText='width:100%;height:450px;border:0;display:block;margin-top:8px';
 target.replaceChildren(frame);
}
// ETFIQ-computed total returns. This is separate from archived price-return horizons.
async function getLatestTotalReturnMonth(session){if(session!=='2026-11-17')return null;try{const r=await fetch('./data/overseas-etfiq-month-20261117.json',{cache:'no-store'});if(!r.ok)return null;const v=await r.json();return v.asOf===session&&v.from==='2026-10-16'&&v.basis==='total_return_distributions_reinvested'&&v.values?Object.freeze(v.values):null;}catch{return null;}}
function totalReturnMonthPanel(f){const v=monthOverlay?.[f.code];if(!Number.isFinite(v))return '';const cap=Math.max(15,Math.ceil(Math.abs(v)/5)*5),width=Math.abs(v)/cap*214,x=v<0?236-width:236,color=v<0?'#fd7991':'#3bd6aa';return `<section class="etf-sources" aria-label="최신 1개월 총수익률"><p><strong>1개월 총수익률 ${pct(v)}</strong> · 10/16→11/17 미국 정규장(ET), 분배금 재투자 포함</p><svg viewBox="0 0 472 42" width="100%" height="42" role="img" aria-label="1개월 총수익률 ${pct(v)}"><line x1="22" x2="450" y1="20" y2="20" stroke="#40516c"/><line x1="236" x2="236" y1="2" y2="28" stroke="#8196b6"/><rect x="${x}" y="10" width="${width}" height="17" rx="2" fill="${color}"/><text x="236" y="41" text-anchor="middle" fill="#91a5c3" font-size="11">0%</text></svg><p>출처 <a href="https://etfiq.com/data/" target="_blank" rel="noopener noreferrer">ETFIQ (etfiq.com)</a> · 보관 일봉·가격 수익률과 별도</p></section>`;}
// Dated source observations are not merged into missing OHLC bars.
function priorIssuerSessionNote(f){if(f.code==='SOXX')return '<section class="etf-sources"><p><strong>11/17 ET 운용사 확인 종가 $141.46 · +0.17%</strong> · 11/16 종가 $141.22와 비교. 보관 캔들과 별도입니다.</p><a href="https://www.ishares.com/us/products/239705/ishares-semiconductor-etf-soxx" target="_blank" rel="noopener noreferrer">iShares 공식 종가 ↗</a></section>';if(f.code==='SMH')return '<section class="etf-sources"><p><strong>11/17 ET 운용사 순자산가치(NAV) $460.34</strong> · 거래소 종가와 다릅니다. 같은 날짜 편입 비중은 원문에 있습니다.</p><a href="https://www.vaneck.com/us/en/investments/semiconductor-etf-smh/" target="_blank" rel="noopener noreferrer">VanEck 공식 NAV·편입종목 ↗</a></section>';return '';}
// Editorial source checks: selected session close facts, never inserted into archival OHLC.
const sourceClose1117=Object.freeze({
 XLK:{close:163.26,slug:'technology',issuer:'State Street'},
 XLE:{close:63.36,slug:'energy',issuer:'State Street'},
 XLF:{close:57.07,slug:'financial',issuer:'State Street'}
});
function issuerSessionNote(f){
 const row=sourceClose1117[f.code];
 if(row){
  const url='https://www.ssga.com/us/en/intermediary/etfs/state-street-'+row.slug+'-select-sector-spdr-etf-'+f.code.toLowerCase();
  return `<section class="etf-sources"><p><strong>2026-11-17 ET 공식 종가 $${fmt(row.close)}</strong> · 운용사가 게시한 주상장 거래소 종가입니다. 보관 캔들과 별도입니다.</p><a href="${url}" target="_blank" rel="noopener noreferrer">State Street 공식 종가·편입비중 ↗</a></section>`;
 }
 return priorIssuerSessionNote(f);
}

function detail(){const f=payload?.funds.find(f=>f.code===selected);if(!f){$('us-etf-detail').innerHTML='<div class="etf-empty">ETF를 선택해 주세요.</div>';return;}const d=f.daily||[],last=d.at(-1),change=dailyReturn(f);const intra=f.intraday||{},date=period==='day'?intra.date:last?.date;
$('us-etf-detail').innerHTML=`<div class="etf-chart-panel"><div class="etf-chart-head"><div class="eyebrow">${esc(f.category)} · ${esc(f.issuer)}</div><h3>${esc(f.code)} <span class="etf-fullname">(${esc(f.name)})</span></h3>${representatives(f)}<span class="etf-price">${fmt(last?.close)} USD</span> <span class="${change>=0?'up':'down'}">${pct(change)}</span><div class="etf-note">보관 종가 기준 ${esc(last?.date||'미확인')} · ${esc(f.exchange||'미국 상장')} · USD</div><div class="etf-periods" aria-label="차트 기간">${[['day','당일'],['3','3개월'],['6','6개월'],['12','12개월']].map(([v,t])=>`<button type="button" data-etf-period="${v}" class="${period===v?'active':''}" aria-pressed="${period===v}">${t}</button>`).join('')}</div><div class="etf-periods" role="group" aria-label="캔들 단위">${Object.entries(candleNames).map(([v,t])=>`<button type="button" data-etf-candle="${v}" class="${period!=='day'&&candleKind===v?'active':''}" aria-pressed="${period!=='day'&&candleKind===v}">${t}</button>`).join('')}</div></div><p class="etf-status">${period==='day'?`${esc(date||'기준일 미확인')} 미국 정규장 흐름 (ET) · ${esc(intra.interval||'간격 미확인')} · ${esc(stamp(intra.asOf))}${intra.refreshStatus==='stale'?' · 이전 검증 장중 자료 유지':''}`:esc(candleStatus(series(f),candleKind,'America/New_York'))}</p><div class="etf-note"><strong>보관 ${period==='day'?'장중':candleNames[candleKind]}</strong> · 마지막 실제 관측 ${esc(date||'미확인')} ET · 외부 차트와 별도입니다.</div><div id="us-etf-plot" class="etf-plot"></div><div id="us-etf-tooltip" class="etf-tooltip" aria-live="off"></div><div class="etf-meta"><div><small>1일 수익률</small><strong class="${change>=0?'up':'down'}">${pct(change)}</strong></div><div><small>1주일 수익률</small><strong class="${weeklyReturn(f)>=0?'up':'down'}">${pct(weeklyReturn(f))}</strong></div><div><small>1달 수익률</small><strong class="${returns(f)>=0?'up':'down'}">${pct(returns(f))}</strong></div></div><p class="etf-status">미국 상장 업종·테마 ETF · 정규장 가격 기준 수익률(USD)이며 분배금 재투자 수익률·원화 환산 수익률과 다를 수 있습니다. ${esc(f.selectionNote||'')}${f.refreshStatus==='stale'?' 최신 조회 실패로 이전 검증 자료를 유지합니다.':''}</p></div>${providerPanel(f)}<details class="etf-sources"><summary>ETF 정보·시세 출처</summary><p>종목코드 ${esc(f.code)}</p>${issuerSessionNote(f)}${representativeSources(f)}${selectionSources(f)}${(f.sourceUrls||[]).map((s,i)=>{const url=typeof s==='string'?s:s.url,title=typeof s==='string'?(f.sourceTitles?.[i]||s):(s.title||s.url);return `<div><a href="${esc(safeURL(url))}" target="_blank" rel="noopener noreferrer">${esc(title)}</a></div>`}).join('')}<p>게시된 시세 스냅샷으로 실시간 호가가 아닙니다. 당일은 수집된 실제 장중 시세만 표시하며 일봉을 분할해 만들지 않습니다.</p></details><div id="us-etf-total-return-month">${totalReturnMonthPanel(f)}</div>`;

mountProviderPanel(f);
$('us-etf-detail').querySelectorAll('[data-etf-period]').forEach(b=>b.onclick=()=>{period=b.dataset.etfPeriod;if(period!=='day')lastRange=period;detail();});$('us-etf-detail').querySelectorAll('[data-etf-candle]').forEach(b=>b.onclick=()=>{candleKind=b.dataset.etfCandle;if(period==='day')period=lastRange;detail();$('us-etf-detail').querySelector?.('[data-etf-candle="'+candleKind+'"]')?.focus();});plot(f);}
async function fetchETFData(url, timeout=15000){
 const abort=new AbortController(),timer=setTimeout(()=>abort.abort(),timeout);
 try{const r=await fetch(url,{cache:'no-cache',signal:abort.signal});if(!r.ok)throw Error('HTTP '+r.status);return await r.json();}
 finally{clearTimeout(timer);}
}
async function load(){
 if(loading)return;loading=true;
 const label=$('us-etf-updated'); if(!payload)label.textContent='해외 ETF 목록과 차트를 불러오는 중입니다…';
 try{
  const next=await fetchETFData('./data/overseas_etf_charts.json');
  if(next.schemaVersion!==1||!Array.isArray(next.funds)||!next.funds.length)throw Error('Invalid ETF schema');
  payload=next;monthOverlay=null;lastLoad=Date.now();
  label.textContent=statusLabel(next.funds,null);list();detail();
  // The independently fetched US close and returns must not block the ETF list or candle.
  getVerifiedSession().then(session=>{
    if(payload!==next)return;
    label.textContent=statusLabel(next.funds,session);
    if(!session)return;
    getLatestTotalReturnMonth(session).then(v=>{
      if(payload!==next||!v)return;
      monthOverlay=v;const target=$('us-etf-total-return-month'),fund=next.funds.find(f=>f.code===selected);
      if(target&&fund)target.innerHTML=totalReturnMonthPanel(fund);
    });
  });
 }catch(e){
  label.innerHTML=(payload?'새 시세 조회 실패 · 아래에 이전 차트를 유지합니다.':'해외 ETF 자료를 불러오지 못했습니다.')+' <button id="us-etf-retry" class="button" type="button">다시 불러오기</button>';
  const retry=$('us-etf-retry');if(retry)retry.onclick=load;
  console.error('ETF data:',e);
 }finally{loading=false;}
}
function boot(){if(!$('overseas-etf-panel'))return;$('us-etf-sort').value=sort;$('us-etf-search').oninput=e=>{query=e.target.value;list();detail();};$('us-etf-group').onchange=e=>{group=e.target.value;list();detail();};$('us-etf-sort').onchange=e=>{sort=['day','week','month'].includes(e.target.value)?e.target.value:'day';list();detail();};const route=()=>{const active=location.hash.split('/')[0]==='#overseas-etf';if(!active){$('us-etf-widget-view')?.replaceChildren();return;}if(Date.now()-lastLoad>60000){load();return;}const f=payload?.funds.find(x=>x.code===selected);if(f&&!$('us-etf-widget-view')?.querySelector('iframe'))mountProviderPanel(f);};window.addEventListener('hashchange',route);route();window.setInterval(()=>{if(document.visibilityState!=='hidden')route();},300000);}
window.TerminalOverseasETF={returns,series,safeURL,representatives,representativeSources,aggregateCandles,displayCandles,candleLabel,candleStatus};if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot,{once:true});else boot();
}());
