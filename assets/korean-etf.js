/* Source-backed Korean ETF snapshots. No synthetic intraday prices. */
(function(){
'use strict';
const $=id=>document.getElementById(id),esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt=(v,n=0)=>Number.isFinite(v)?v.toLocaleString('ko-KR',{maximumFractionDigits:n,minimumFractionDigits:n}):'—';
const stamp=v=>{const d=new Date(v);return Number.isNaN(d.getTime())?String(v||'미확인'):d.toLocaleString('ko-KR',{timeZone:'Asia/Seoul',hour12:false})+' KST';};
const pct=v=>Number.isFinite(v)?`${v>0?'+':''}${fmt(v,2)}%`:'—';
let payload=null,selected='',period='3',lastRange='3',candleKind='daily',group='all',query='',sort='day',loading=false,lastLoad=0;
function returns(f,months=1){const d=f.daily||[];if(d.length<2)return null;const last=d.at(-1),cut=new Date(last.date+'T00:00:00Z');const day=cut.getUTCDate();cut.setUTCDate(1);cut.setUTCMonth(cut.getUTCMonth()-months);const end=new Date(Date.UTC(cut.getUTCFullYear(),cut.getUTCMonth()+1,0)).getUTCDate();cut.setUTCDate(Math.min(day,end));const base=d.filter(p=>p.date<=cut.toISOString().slice(0,10)).at(-1);return Number.isFinite(last.close)&&Number.isFinite(base?.close)&&base.close>0?(last.close/base.close-1)*100:null;}
function dailyReturn(f){const d=f.daily||[],last=d.at(-1),prev=d.at(-2);return Number.isFinite(last?.close)&&Number.isFinite(prev?.close)&&prev.close>0?(last.close/prev.close-1)*100:null;}
function weeklyReturn(f){const d=f.daily||[],last=d.at(-1);if(!Number.isFinite(last?.close))return null;const cut=new Date(last.date+'T00:00:00Z');cut.setUTCDate(cut.getUTCDate()-7);const base=d.filter(p=>p.date<=cut.toISOString().slice(0,10)).at(-1);return Number.isFinite(base?.close)&&base.close>0?(last.close/base.close-1)*100:null;}
function listReturn(f){return sort==='month'?returns(f):sort==='week'?weeklyReturn(f):dailyReturn(f);}
function filtered(){return(payload?.funds||[]).filter(f=>(group==='all'||f.group===group)&&[f.name,f.code,f.category,f.issuer,...(f.representatives?.members||[]).map(m=>m.name)].join(' ').toLowerCase().includes(query.toLowerCase())).sort((a,b)=>(listReturn(b)??-Infinity)-(listReturn(a)??-Infinity));}
function representatives(f){const r=f.representatives;if(!r?.members?.length)return '';return `<span class="etf-representatives">(${r.members.slice(0,3).map(m=>esc(m.name)).join(' / ')})</span>`;}
function representativeSources(f){const r=f.representatives;if(!r)return '';if(!r.members?.length)return `<p>${esc(r.methodology||'대표 종목 편입비중 미확인')}</p>`;return `<p>${esc(r.label)} · 구성 기준 ${esc(r.universeAsOf||'미확인')} · 확인 ${esc(stamp(r.asOf))} · ${esc(r.verifiedCount)}개 편입자산 확인${r.refreshStatus==='stale'?' · 이전 검증 자료 유지':''}. ${esc(r.methodology||'')}</p><p>${r.members.slice(0,3).map(m=>`${esc(m.name)} ${fmt(m.weightPct,2)}%`).join(' / ')}</p>${(r.sourceUrls||[]).map(u=>`<div><a href="${esc(safeURL(u))}" target="_blank" rel="noopener noreferrer">대표 종목 구성·편입비중 출처 ↗</a></div>`).join('')}`;}
function selectionSources(f){const e=f.selectionEvidence;if(!e?.disclosure)return '';const links=[[e.officialSourceUrl,'운용사 구성종목 원자료'],[e.officialAum?.sourceUrl,'운용사 순자산 기준일 원자료']];return `<p class="etf-selection-disclosure">${esc(e.disclosure)}</p>${links.filter(([url])=>url).map(([url,title])=>`<div><a href="${esc(safeURL(url))}" target="_blank" rel="noopener noreferrer">${title} ↗</a></div>`).join('')}`;}

function list(){const funds=filtered();$('etf-count').textContent=`${funds.length}개 ETF · 공급사 일별 가격계열(과거 분배락 조정 포함) · 목록 수익률은 ${sort==='month'?'최근 1달':sort==='week'?'최근 1주일':'전일 종가 대비 1일 등락'}`;if(!funds.some(f=>f.code===selected))selected=funds[0]?.code||'';$('etf-list').innerHTML=funds.map(f=>{const r=listReturn(f);return `<button type="button" class="etf-choice ${f.code===selected?'active':''}" data-etf="${esc(f.code)}" aria-pressed="${f.code===selected}"><span class="etf-return ${r>=0?'up':'down'}">${pct(r)}</span><strong>${esc(f.category)}</strong><small>${esc(f.name)}</small>${representatives(f)}</button>`}).join('')||'<p class="etf-empty">검색 결과가 없습니다.</p>';$('etf-list').querySelectorAll('[data-etf]').forEach(b=>b.onclick=()=>{selected=b.dataset.etf;list();detail();});}
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
function plot(f){const data=series(f),intraday=period==='day';if(data.length<(intraday?2:1)){$('etf-plot').innerHTML=`<div class="etf-empty">${intraday?'당일 장중 시세가 아직 확보되지 않았습니다. 일봉을 선택해 주세요.':'이 기간의 차트 자료가 충분하지 않습니다.'}</div>`;$('etf-tooltip').textContent='';return;}
const W=1000,H=440,L=18,R=88,T=25,B=55,priceH=280,volumeY=330,volumeH=48,step=(W-L-R)/data.length;
let lo=Math.min(...data.map(p=>intraday?p.close:p.low)),hi=Math.max(...data.map(p=>intraday?p.close:p.high));const pad=(hi-lo)*.07||hi*.01||1;lo-=pad;hi+=pad;const minute=p=>{const match=String(p.label).match(/(\d{2}):(\d{2})(?::\d{2})?$/);return match?Number(match[1])*60+Number(match[2]):null;},minutes=data.map(minute),timed=intraday&&minutes.every(Number.isFinite)&&minutes.at(-1)>minutes[0];const y=v=>T+(hi-v)/(hi-lo)*priceH,x=i=>timed?L+8+(minutes[i]-minutes[0])/(minutes.at(-1)-minutes[0])*(W-L-R-16):L+(i+.5)*step,vol=Math.max(...data.map(p=>p.volume||0),1);let svg=`<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(f.name)} ${intraday?'당일 장중':candleNames[candleKind]} 가격 및 거래량 차트">`;
for(let i=0;i<5;i++){const v=lo+(hi-lo)*i/4,yy=y(v);svg+=`<line x1="${L}" x2="${W-R}" y1="${yy}" y2="${yy}" stroke="#2b3a55"/><text x="${W-R+10}" y="${yy+4}" fill="#91a5c3" font-size="12">${fmt(v)}</text>`;}
if(intraday)svg+=`<polyline points="${data.map((p,i)=>`${x(i)},${y(p.close)}`).join(' ')}" fill="none" stroke="#a3baff" stroke-width="2.5"/>`;
data.forEach((p,i)=>{const color=intraday?'#6b85bd':p.close>=p.open?'#3bd6aa':'#fd7991',xx=x(i),width=Math.max(1,step*.65);if(!intraday)svg+=`<line x1="${xx}" x2="${xx}" y1="${y(p.high)}" y2="${y(p.low)}" stroke="${color}"/><rect x="${xx-width/2}" y="${Math.min(y(p.open),y(p.close))}" width="${width}" height="${Math.max(1,Math.abs(y(p.open)-y(p.close)))}" fill="${color}"/>`;if(Number.isFinite(p.volume))svg+=`<rect x="${xx-width/2}" y="${volumeY+volumeH-p.volume/vol*volumeH}" width="${width}" height="${p.volume/vol*volumeH}" fill="${color}" opacity=".55"/>`;});
for(const i of [...new Set([0,Math.floor(data.length/3),Math.floor(data.length*2/3),data.length-1])])svg+=`<text x="${x(i)}" y="${H-22}" text-anchor="${i===0?'start':i===data.length-1?'end':'middle'}" fill="#91a5c3" font-size="12">${esc(data[i].label)}</text>`;
svg+=`<text x="${L}" y="${volumeY-5}" fill="#91a5c3" font-size="11">거래량</text><line id="etf-crosshair" y1="${T}" y2="${volumeY+volumeH}" stroke="#a6b9db" stroke-dasharray="4 4" visibility="hidden"/></svg>`;$('etf-plot').innerHTML=svg;
const show=i=>{const p=data[i];$('etf-tooltip').textContent=`${intraday?p.label:candleLabel(p,candleKind)} (KST) · ${intraday?'가격 '+fmt(p.close)+'원':'시가 '+fmt(p.open)+' · 고가 '+fmt(p.high)+' · 저가 '+fmt(p.low)+' · 종가 '+fmt(p.close)+'원'}${Number.isFinite(p.volume)?' · 거래량 '+fmt(p.volume)+'주':''}`;};show(data.length-1);const chart=$('etf-plot').querySelector('svg');chart.onpointermove=e=>{const rect=chart.getBoundingClientRect(),i=Math.max(0,Math.min(data.length-1,(timed?data.reduce((best,p,j)=>Math.abs(x(j)-(e.clientX-rect.left)/rect.width*W)<Math.abs(x(best)-(e.clientX-rect.left)/rect.width*W)?j:best,0):Math.floor(((e.clientX-rect.left)/rect.width*W-L)/step)))),line=$('etf-crosshair');line.setAttribute('x1',x(i));line.setAttribute('x2',x(i));line.setAttribute('visibility','visible');show(i);};chart.onpointerleave=()=>{$('etf-crosshair').setAttribute('visibility','hidden');show(data.length-1);};}
function safeURL(url){try{const u=new URL(url);return ['https:','http:'].includes(u.protocol)?u.href:'#';}catch{return '#';}}
// Two independently corroborated editorial observations, not the ETF ranking data or an OHLC series.
// Fixed editorial examples, not a feed or an addition to the daily price history.
const etfSampleDate='2026-11-18';
const eodNotes=Object.freeze({
 '091160':Object.freeze({o:90685,h:91840,l:86415,c:89755,pct:2.46,issuer:'https://m.samsungfund.com/etf/product/view.do?id=2ETF07'}),
 '466920':Object.freeze({o:17595,h:17900,l:17010,c:17395,pct:-0.57,issuer:'https://www.soletf.co.kr/ko/fund/etf/211028'}),
 '0148J0':Object.freeze({o:7050,h:7675,l:6985,c:7610,pct:9.97,issuer:'https://www.tigeretf.com/'}),
 '0177X0':Object.freeze({o:7190,h:7815,l:7130,c:7795,pct:9.94,issuer:'https://www.aceetf.co.kr/info/report/1348'}),
});
function recentComparison(f){
 const code=f?.code, row=typeof code==='string'&&Object.hasOwn(eodNotes,code)?eodNotes[code]:null;
 if(!row||(f.daily?.at(-1)?.date||'')>=etfSampleDate)return '';
 const y=v=>12+(row.h-v)/(row.h-row.l)*91, color=row.c>=row.o?'#3bd6aa':'#fd7991';
 const lo=Math.min(y(row.o),y(row.c)),height=Math.max(2,Math.abs(y(row.o)-y(row.c)));
 const prices='시가 '+fmt(row.o,0)+'원 · 고가 '+fmt(row.h,0)+'원 · 저가 '+fmt(row.l,0)+'원 · 종가 '+fmt(row.c,0)+'원';
 const guide=(label,value)=>'<line x1="27" x2="116" y1="'+y(value)+'" y2="'+y(value)+'" stroke="#40516c" stroke-dasharray="3 3"/><text x="124" y="'+(y(value)+4)+'" fill="#adc0dc" font-size="11">'+label+' '+fmt(value,0)+'</text>';
 return '<section class="etf-sources" aria-label="표본 ETF '+etfSampleDate+' 일봉"><p><strong>'+etfSampleDate+' 정규장 일봉 · '+code+'</strong> (KST)</p>'+
   '<svg width="100%" height="132" viewBox="0 0 260 117" role="img" aria-label="'+esc(prices)+'">'+
   guide('고가',row.h)+guide('저가',row.l)+
   '<line x1="71" x2="71" y1="'+y(row.h)+'" y2="'+y(row.l)+'" stroke="'+color+'" stroke-width="2"/><rect x="59" y="'+lo+'" width="24" height="'+height+'" fill="'+color+'" rx="2"/></svg>'+
   '<p>'+prices+'</p><p>전 거래일 종가 대비 '+pct(row.pct)+' · 캔들 색은 당일 시가 대비 종가를 나타냅니다.</p>'+
   '<p>출처: <a href="https://etfro.com/etf/'+code+'" target="_blank" rel="noopener noreferrer">ETFRo (KG제로인) '+code+' ↗</a> · <a href="'+row.issuer+'" target="_blank" rel="noopener noreferrer">운용사 ↗</a> · 해당 거래일 한 봉으로, 보관 일봉·주봉·월봉과 전체 수익률 순위에는 합치지 않았습니다.</p></section>';
}
function krxOriginalChart(code){if(typeof code!=='string'||!/^[0-9A-Z]{6}$/.test(code))return '';return `<p class="etf-note"><a class="button" href="https://kr.tradingview.com/symbols/KRX-${code}/" target="_blank" rel="noopener noreferrer">TradingView 원본 일봉·주봉·월봉 ↗</a> <span class="muted">새 탭 · 공급사 지연 시세, 최신 거래일은 원본에서 확인</span></p>`;}
function detail(){const f=payload?.funds.find(f=>f.code===selected);if(!f){$('etf-detail').innerHTML='<div class="etf-empty">ETF를 선택해 주세요.</div>';return;}const d=f.daily||[],last=d.at(-1),change=dailyReturn(f);const intra=f.intraday||{},date=period==='day'?intra.date:last?.date;
$('etf-detail').innerHTML=`<div class="etf-chart-panel"><div class="etf-chart-head"><div class="eyebrow">${esc(f.category)} · ${esc(f.issuer)}</div><h3>${esc(f.name)}</h3>${representatives(f)}<span class="etf-price">${fmt(last?.close)}원</span> <span class="${change>=0?'up':'down'}">${pct(change)}</span><div class="etf-note">종가 기준 ${esc(last?.date||'미확인')} · KRX · KRW</div><div class="etf-periods" aria-label="차트 기간">${[['day','당일'],['3','3개월'],['6','6개월'],['12','12개월']].map(([v,t])=>`<button type="button" data-etf-period="${v}" class="${period===v?'active':''}" aria-pressed="${period===v}">${t}</button>`).join('')}</div><div class="etf-periods" role="group" aria-label="캔들 단위">${Object.entries(candleNames).map(([v,t])=>`<button type="button" data-etf-candle="${v}" class="${period!=='day'&&candleKind===v?'active':''}" aria-pressed="${period!=='day'&&candleKind===v}">${t}</button>`).join('')}</div></div><p class="etf-status">${period==='day'?`${esc(date||'기준일 미확인')} 장중 흐름 · ${esc(intra.interval||'간격 미확인')} · ${esc(stamp(intra.asOf))}`:esc(candleStatus(series(f),candleKind,'Asia/Seoul'))}</p><div id="etf-plot" class="etf-plot"></div><div id="etf-tooltip" class="etf-tooltip" aria-live="off"></div>${krxOriginalChart(f.code)}<div class="etf-meta"><div><small>${Number.isFinite(f.aumKRW)?'순자산':'시가총액'} · 억원</small><strong>${fmt(Number.isFinite(f.aumKRW)?f.aumKRW/1e8:Number.isFinite(f.marketCapKRW)?f.marketCapKRW/1e8:null)}</strong></div><div><small>${Number.isFinite(f.turnoverKRW)?'거래대금 · 억원':'거래량 · 주'}</small><strong>${fmt(Number.isFinite(f.turnoverKRW)?f.turnoverKRW/1e8:f.volume)}</strong></div><div><small>1개월 수익률</small><strong class="${returns(f)>=0?'up':'down'}">${pct(returns(f))}</strong></div></div><p class="etf-status">규모·거래 기준 ${esc(f.metadataAsOf||'미확인')} · 상장 이력이 짧은 ETF는 확보된 기간만 표시합니다. 동일 공급사 가격계열 수익률이며 공인 총수익률과 다를 수 있습니다. ${esc(f.dailyAdjustment||'공급사 가격조정 기준 미확인')} ${esc(f.selectionNote||'')}</p></div><details class="etf-sources"><summary>ETF 정보·시세 출처</summary><p>종목코드 ${esc(f.code)}</p>${representativeSources(f)}${selectionSources(f)}${(f.sourceUrls||[]).map((s,i)=>{const url=typeof s==='string'?s:s.url,title=typeof s==='string'?(f.sourceTitles?.[i]||s):(s.title||s.url);return `<div><a href="${esc(safeURL(url))}" target="_blank" rel="noopener noreferrer">${esc(title)}</a></div>`}).join('')}<p>게시된 시세 스냅샷으로 실시간 호가가 아닙니다. 당일은 수집된 실제 장중 시세만 표시하며 일봉을 분할해 만들지 않습니다.</p></details>${recentComparison(f)}`;
$('etf-detail').querySelectorAll('[data-etf-period]').forEach(b=>b.onclick=()=>{period=b.dataset.etfPeriod;if(period!=='day')lastRange=period;detail();});$('etf-detail').querySelectorAll('[data-etf-candle]').forEach(b=>b.onclick=()=>{candleKind=b.dataset.etfCandle;if(period==='day')period=lastRange;detail();$('etf-detail').querySelector?.('[data-etf-candle="'+candleKind+'"]')?.focus();});plot(f);}
async function load(){if(loading)return;loading=true;try{const response=await fetch('./data/korean_etf_charts.json?ts='+Date.now(),{cache:'no-store'});if(!response.ok)throw Error('HTTP '+response.status);const next=await response.json();if(next.schemaVersion!==1||!Array.isArray(next.funds))throw Error('Invalid ETF schema');payload=next;lastLoad=Date.now();const latest=next.funds.map(f=>f.daily?.at(-1)?.date).filter(d=>typeof d==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(d)).sort().at(-1);const n=next.funds.filter(f=>(f.daily?.at(-1)?.date||'')>='2026-11-18').length;$('etf-updated').textContent=`보관 일봉 최신 ${latest||'미확인'} KST · 11/18 일봉 반영 ${n}/${next.funds.length} · 일부 당일 등락은 별도 표시`;list();detail();}catch(e){$('etf-updated').textContent='ETF 자료를 불러오지 못했습니다. 잠시 후 다시 확인해 주세요.';console.error('ETF data:',e);}finally{loading=false;}}
function boot(){if(!$('etf-panel'))return;$('etf-sort').value=sort;$('etf-search').oninput=e=>{query=e.target.value;list();detail();};$('etf-group').onchange=e=>{group=e.target.value;list();detail();};$('etf-sort').onchange=e=>{sort=['day','week','month'].includes(e.target.value)?e.target.value:'day';list();detail();};const route=()=>{if(location.hash.split('/')[0]==='#etf'&&Date.now()-lastLoad>60000)load();};window.addEventListener('hashchange',route);route();window.setInterval(()=>{if(document.visibilityState!=='hidden')route();},300000);}
window.TerminalETF={returns,series,safeURL,representatives,representativeSources,aggregateCandles,displayCandles,candleLabel,candleStatus};if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot,{once:true});else boot();
}());
