/* Dated provider snapshots; no iframe scraping or synthetic probabilities. */
(function(){
'use strict';
const $=id=>document.getElementById(id);
const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const finite=x=>typeof x==='number'&&Number.isFinite(x);
const num=(x,p=2)=>finite(x)?x.toLocaleString('ko-KR',{minimumFractionDigits:p,maximumFractionDigits:p}):'미확인';
const safeURL=x=>{try{const u=new URL(x);return u.protocol==='https:'?u.href:'#';}catch(_){return '#';}};
const stamp=x=>{const d=new Date(x);return x&&!Number.isNaN(d.valueOf())?d.toLocaleString('ko-KR',{timeZone:'Asia/Seoul',hour12:false})+' KST':'시각 미확인';};
const percent=x=>num(x,2)+'%';
const range=b=>b.map(n=>num(n/100,2)).join('–')+'%';
const sum=a=>a.reduce((x,y)=>x+y,0);
function direction(columns,probabilities,current){
 let result={cut:0,hold:0,hike:0};
 columns.forEach((b,i)=>{const p=probabilities[i];if(!finite(p))return;result[b[0]<current[0]?'cut':b[0]>current[0]?'hike':'hold']+=p;});
 return result;
}
function validFedwatch(d){
 return d?.schemaVersion===1&&Array.isArray(d.currentTargetBps)&&d.currentTargetBps.length===2&&d.currentTargetBps.every(finite)&&Array.isArray(d.columnsBps)&&d.columnsBps.every(b=>Array.isArray(b)&&b.length===2&&b.every(finite))&&d.meetings?.length&&d.meetings.every(m=>/^\d{4}-\d{2}-\d{2}$/.test(m.date)&&m.probabilities?.length===d.columnsBps.length&&m.probabilities.every(p=>finite(p)&&p>=0&&p<=100)&&Math.abs(sum(m.probabilities)-100)<.1);
}
function quoteHTML(q,related){
 if(!q||!finite(q.value))return '<span class="quote-label">최신 수치 미확인</span>';
 let note=q.note||q.basisNote||'';
 if(related==='WTI_FUTURES'||related==='BRENT_FUTURES')note='위 숫자는 Investing 선물 연계 CFD, 아래 차트는 FXCM CFD입니다. 서로 다른 상품·제공사이며 확정 결제가격이 아닙니다.';
 if(related==='UST10Y')note='위 숫자는 Investing 시장 국채 수익률, 아래 차트는 OTC Bonds 수익률입니다. 제공사·관측시각이 다를 수 있습니다.';
 if(q.status==='stale')note='최신 조회 실패 · 이전 검증 수치 유지. '+note;
 return '<span class="quote-label">'+esc(q.quoteLabel||q.name||q.id)+'</span><strong>'+num(q.value,q.precision??2)+'</strong><span class="quote-unit">'+esc(q.unit||'')+'</span><span class="quote-asof">시세 기준 '+(q.observedAt?stamp(q.observedAt):esc(q.asOf||'미확인'))+' · <a href="'+esc(safeURL(q.sourceUrl))+'" target="_blank" rel="noopener noreferrer">'+esc(q.sourceName||q.source||'Investing.com')+' ↗</a></span>'+(note?'<span class="quote-note">'+esc(note)+'</span>':'');
}
function renderQuotes(d){
 const rows=Array.isArray(d.rows)?d.rows:Object.values(d.rows||{});
 const map=Object.fromEntries(rows.map(q=>[q.id||q.key,q]));
 document.querySelectorAll('[data-macro-quote]').forEach(el=>{const id=el.dataset.macroQuote;el.innerHTML=quoteHTML(map[id],id);});
 document.querySelectorAll('.rate-card[data-series]').forEach(card=>{
   const q=map[card.dataset.series];if(card.dataset.externalMacro||!q||q.sourceName!=='FRED'||!finite(q.value))return;
   let el=card.querySelector('.macro-fred-value');
   if(!el){el=document.createElement('div');el.className='macro-fred-value rate-source';card.querySelector('.rate-head').after(el);}
   el.innerHTML='차트와 동일한 FRED 계열: <strong>'+num(q.value,q.precision??2)+' '+esc(q.unit||'')+'</strong> · '+(q.frequency==='monthly'?'관측월 '+esc(q.asOf.slice(0,7)):'관측일 '+esc(q.asOf))+(q.sourceUpdatedAt?' · FRED 갱신 '+stamp(q.sourceUpdatedAt):'')+' · <a href="'+esc(safeURL(q.sourceUrl))+'" target="_blank" rel="noopener noreferrer">원본 ↗</a>'+(q.status==='stale'?' · 이전 검증값 유지':'');
 });
}
function conditionalHTML(d){
 const c=d.conditionalComparisons;if(!c?.comparisons?.length)return '';
 return '<details class="fedwatch-conditional"><summary>12월·중기 금리 기대 변화 · Conditional 별도 비교</summary><p class="fedwatch-caveat">아래는 CME Current의 Conditional 방식끼리 비교합니다. 위 Aggregated 표와 산출 방식이 달라 확률 수준이 다를 수 있으며 두 방식의 수치를 빼서 변화량을 구하지 않습니다.</p><div class="conditional-cards">'+c.comparisons.map(m=>{
 const index=m.now.indexOf(Math.max(...m.now));
 return '<article class="fedwatch-change"><small>'+esc(m.meetingDate)+' · 동일 Conditional 방식</small><strong>최빈 구간 '+range(m.columnsBps[index])+'</strong><p>'+esc(m.interpretation)+'</p><details><summary>비교 원자료</summary><div class="fedwatch-table-wrap"><table class="fedwatch-table"><thead><tr><th>목표금리</th><th>현재</th><th>전일 '+esc(c.comparisonDates.day)+'</th><th>전주 '+esc(c.comparisonDates.week)+'</th><th>전월 '+esc(c.comparisonDates.month)+'</th></tr></thead><tbody>'+m.columnsBps.map((b,i)=>'<tr><td>'+range(b)+'</td>'+['now','day','week','month'].map(k=>'<td>'+num(m[k][i],1)+'%</td>').join('')+'</tr>').join('')+'</tbody></table></div><p class="fedwatch-caveat">'+esc(m.rowSumRoundingNote)+'</p></details></article>';
 }).join('')+'</div><p class="fedwatch-caveat">검증 '+stamp(c.observedAt)+' · 더 낮은 인상 폭을 기대한다는 뜻이지, 현 금리보다 인하될 확률이 높다는 뜻은 아닙니다.</p></details>';
}
function fedwatchHTML(d){
 if(!validFedwatch(d))return '<p class="market-note">확률 자료를 검증하지 못했습니다. CME 원본에서 확인해 주세요.</p>';
 const ageDays=(Date.now()-new Date(d.observedAt).valueOf())/86400000;
 const ageWarning=ageDays>3?'<p class="fedwatch-caveat">확인 후 '+Math.floor(ageDays)+'일이 지난 자료입니다. 최신 확률은 CME 원본을 확인하세요.</p>':'';
 const first=d.meetings[0],dirs=direction(d.columnsBps,first.probabilities,d.currentTargetBps);
 const c=d.nextMeetingComparison;
 const current=c&&direction(c.columnsBps,c.now.probabilities,d.currentTargetBps);
 const changes=c&&c.meetingDate===first.date?['day','week','month'].map((key,i)=>{
   const before=c[key];if(!before?.probabilities)return '<div class="fedwatch-change">비교 자료 미확인</div>';
   const prior=direction(c.columnsBps,before.probabilities,d.currentTargetBps),delta=Math.round((current.hike-prior.hike)*10)/10;
   return '<div class="fedwatch-change"><small>'+['전일','전주','전월'][i]+' 대비 · '+esc(before.date)+'</small><strong>인상 확률 '+(delta>0?'+':'')+num(delta,1)+'%p</strong><small>'+num(prior.hike,1)+'% → '+num(current.hike,1)+'% · '+(delta<0?'인상 기대 약화':delta>0?'인상 기대 강화':'변화 없음')+'</small></div>';
 }).join(''):'<p>동일 기준 비교 자료 미확인</p>';
 const third=d.meetings.find(m=>m.date.endsWith('-12-09'))||d.meetings[1];
 const thirdDir=third?direction(d.columnsBps,third.probabilities,d.currentTargetBps):null;
 return '<p class="fedwatch-meta">현재 목표금리 '+range(d.currentTargetBps)+' · 공식 화면 검증 '+stamp(d.observedAt)+' · 검증 스냅샷 (실시간 아님)</p>'+
 ageWarning+'<div class="fedwatch-table-wrap"><table class="fedwatch-table"><thead><tr><th>FOMC 회의일</th>'+d.columnsBps.map(b=>'<th>'+range(b)+'</th>').join('')+'</tr></thead><tbody>'+d.meetings.map(m=>'<tr><td>'+esc(m.date)+'</td>'+m.probabilities.map(p=>'<td class="'+(p===0?'prob-zero':p>=50?'prob-high':'prob-mid')+'">'+percent(p)+'</td>').join('')+'</tr>').join('')+'</tbody></table></div>'+
 '<div class="fedwatch-commentary"><h4>금리 경로 해석</h4><p>'+esc(first.date)+' 회의는 <strong>동결 '+percent(dirs.hold)+'</strong>, 인상 '+percent(dirs.hike)+', 인하 '+percent(dirs.cut)+'입니다. '+(dirs.hold>=dirs.hike&&dirs.hold>=dirs.cut?'현재 금리 유지 기대가 우세합니다.':dirs.hike>dirs.cut?'현재보다 높은 목표금리 기대가 우세합니다.':'현재보다 낮은 목표금리 기대가 우세합니다.')+'</p>'+
 '<div class="fedwatch-changes">'+changes+'</div>'+
 (thirdDir?'<p>'+esc(third.date)+'까지 현재보다 높은 목표금리에 도달할 확률은 '+percent(thirdDir.hike)+'입니다. 각 회의의 확률은 해당 시점의 누적 목표금리 구간이며 회의별 단독 결정 확률과 구분합니다.</p>':'')+
 conditionalHTML(d)+'<p class="fedwatch-caveat">표는 현재 대비 누적 목표금리 수준의 Aggregated 확률이며 각 회의 한 번의 인상 확률이 아닙니다. 전일·전주·전월 변화는 다음 회의에 한정해 CME Current 비교표의 동일한 한 자리 소수점 수치를 사용합니다. 주말 비교 기준일은 CME 표시 날짜를 그대로 따릅니다.</p>'+
 '<p class="fedwatch-caveat">선물가격에서 계산한 시장 내재 확률이며 연준의 약속·예측이 아닙니다. CME 공개 화면 검증 스냅샷으로 자동 실시간 갱신되지 않습니다. '+(d.providerAsOf?'CME Current 화면 시각 '+stamp(d.providerAsOf)+'; 위 Aggregated 표는 별도 시각이 표시되지 않아 검증 시각을 사용합니다. ':'')+(d.providerAsOfLabel&&!d.providerAsOf?'CME Current 원문 시각 '+esc(d.providerAsOfLabel)+' (CT 일광절약 종료일 중복시각: UTC 오프셋 미확인). ':'')+'<a href="'+esc(safeURL(d.methodologyUrl))+'" target="_blank" rel="noopener noreferrer">CME 산출 방식 ↗</a></p></div>';
}
const officialCME='https://www.cmegroup.com/trading/interest-rates/countdown-to-fomc.html';
const officialHosts={
 UST2Y:'home.treasury.gov',UST10Y:'home.treasury.gov',UST30Y:'home.treasury.gov',
 USDJPY:'www.federalreserve.gov',USDKRW:'www.federalreserve.gov',USD_BROAD:'fred.stlouisfed.org',
 HQMCB10YRP:'fred.stlouisfed.org',M1SL:'www.federalreserve.gov',M2SL:'www.federalreserve.gov',
 WTI_FUTURES:'www.eia.gov',BRENT_FUTURES:'www.eia.gov',DXY:'www.ice.com'
};
const validDay=x=>typeof x==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(x)&&Number.isFinite(Date.parse(x))&&new Date(x).toISOString().slice(0,10)===x;
const officialHost=(url,host)=>{try{const u=new URL(url);return u.protocol==='https:'&&u.hostname===host&&!u.username&&!u.password&&!u.port;}catch(_){return false;}};
function validOfficial(d){
 if(d?.schemaVersion!==1||!validDay(d.session)||!Number.isFinite(Date.parse(d.verifiedAt))||!Array.isArray(d.rows)||d.rows.length!==Object.keys(officialHosts).length)return false;
 const ids=new Set(d.rows.map(r=>r?.id));if(ids.size!==d.rows.length)return false;
 if(!d.rows.every(r=>Object.prototype.hasOwnProperty.call(officialHosts,r?.id)&&officialHost(r.sourceUrl,officialHosts[r.id])&&typeof r.quoteLabel==='string'&&typeof r.note==='string'&&typeof r.sourceName==='string'&&
    (['WTI_FUTURES','BRENT_FUTURES','DXY'].includes(r.id)?r.status==='link_only'&&r.value===null&&r.asOf===null:
     r.status==='verified'&&finite(r.value)&&r.value>0&&validDay(r.asOf)&&r.asOf<=d.session&&['monthly','daily'].includes(r.frequency)&&Number.isInteger(r.precision)&&r.precision>=0&&r.precision<=4)))return false;
 const p=d.officialPolicy;
 return validDay(p?.decisionDate)&&p.decisionDate<=d.session&&p.liveProbabilitiesUrl===officialCME&&officialHost(p.sourceUrl,'www.federalreserve.gov')&&Array.isArray(p.targetBps)&&p.targetBps.length===2&&p.targetBps.every(x=>Number.isInteger(x)&&x>=0&&x<=3000)&&p.targetBps[0]<p.targetBps[1];
}
function officialLink(url,label){return '<a href="'+esc(safeURL(url))+'" target="_blank" rel="noopener noreferrer">'+esc(label)+' ↗</a>';}
function officialRow(r){
 const value=r.status==='verified'?'<strong>'+num(r.value,r.precision)+'</strong><span class="quote-unit">'+esc(r.unit)+'</span><span class="quote-asof">'+(r.frequency==='monthly'?'관측월 '+esc(r.asOf.slice(0,7)):'관측일 '+esc(r.asOf))+' · '+officialLink(r.sourceUrl,r.sourceName)+'</span>':'<span class="quote-asof">'+officialLink(r.sourceUrl,r.sourceName)+'</span>';
 return '<span class="quote-label">'+esc(r.quoteLabel)+'</span>'+value+'<span class="quote-note">'+esc(r.note)+'</span>';
}
function officialPolicyHTML(d){
 const link=officialLink(officialCME,'CME FedWatch 최신 원본');
 if(!validOfficial(d))return '<p class="market-note">공식 수치를 불러오지 못했습니다. '+link+'</p>';
 const p=d.officialPolicy,m=Object.fromEntries(d.rows.map(r=>[r.id,r]));
 return '<p class="fedwatch-meta">미국 '+esc(d.session)+' ET 세션 참고 자료 · 확인 '+stamp(d.verifiedAt)+'</p>'+
  '<p class="fedwatch-meta">연방기금 목표 범위 <strong>'+range(p.targetBps)+'</strong> · '+esc(p.decisionDate)+' 결정 · '+officialLink(p.sourceUrl,'연준 성명')+'</p>'+
  '<p class="fedwatch-meta">미 재무부 파 수익률 · 2년 '+percent(m.UST2Y.value)+' / 10년 '+percent(m.UST10Y.value)+' / 30년 '+percent(m.UST30Y.value)+' · '+esc(m.UST10Y.asOf)+' 관측 · '+officialLink(m.UST10Y.sourceUrl,'미 재무부')+'</p>'+
  '<p class="fedwatch-caveat">CME 확률은 이곳에 재게시하지 않습니다. '+link+'</p>';
}
// A current official Seoul closing observation, kept apart from H.10 noon rates.
function renderOfficialFX(id,d){
 if(id==='USDJPY')return '<span class="quote-label">공식 종가 미확인</span>';
 if(id!=='USDKRW')return null;
 const r=d?.officialSeoulClose;
 if(!r||r.basis!=='seoul_regular_close_1530'||!finite(r.value)||r.value<=0||!validDay(r.asOf)||!validDay(d.session)||r.asOf>d.session||!officialHost(r.sourceUrl,'english.mofe.go.kr'))return '<span class="quote-label">공식 주간 종가 미확인</span>';
 return '<span class="quote-label">달러/원 · 서울 주간장 마감</span><strong>'+num(r.value,1)+'</strong><span class="quote-unit">원/달러</span><span class="quote-asof">'+esc(r.asOf)+' 15:30 KST · '+officialLink(r.sourceUrl,'재정경제부')+'</span>';
}
function renderOfficial(d){
 const ok=validOfficial(d);const map=Object.fromEntries(ok?d.rows.map(r=>[r.id,r]):[]);
 document.querySelectorAll('[data-macro-quote]').forEach(el=>{
   const id=el.dataset.macroQuote, r=map[id];
   el.innerHTML=renderOfficialFX(id,ok?d:null)??(r?officialRow(r):'<span class="quote-label">공식 수치 미확인 · 원본 링크를 이용하세요.</span>');
 });
 document.querySelectorAll('.rate-card[data-series]').forEach(card=>{
   if(!['HQMCB10YRP','M1SL','M2SL'].includes(card.dataset.series))return;
   let el=card.querySelector('.macro-fred-value');
   if(!el){el=document.createElement('div');el.className='macro-fred-value rate-source';card.querySelector('.rate-head').after(el);}
   el.innerHTML=map[card.dataset.series]?officialRow(map[card.dataset.series]):'<span>공식 수치 미확인</span>';
 });
 const panel=$('fedwatch-content');if(panel)panel.innerHTML=officialPolicyHTML(d);
}
let lastLoad=0;
async function load(){
 if(window.location.hash.split('/')[0]!=='#rates'||Date.now()-lastLoad<60000)return;
 lastLoad=Date.now();
 try{const r=await fetch('./data/macro-official-latest.json',{cache:'no-store'});if(!r.ok)throw Error(r.status);renderOfficial(await r.json());}
 catch(_){lastLoad=0;renderOfficial(null);}
}
function boot(){window.addEventListener('hashchange',load);document.addEventListener('visibilitychange',()=>{if(!document.hidden)load();});load();}
window.TerminalMacro={direction,validFedwatch,quoteHTML,fedwatchHTML,safeURL,range,validOfficial,officialRow,officialPolicyHTML,renderOfficial,load};
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot,{once:true});else boot();
}());
