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
 if(related==='WTI_FUTURES'||related==='BRENT_FUTURES')note='위 숫자는 선물/파생 시세, 아래 FRED 차트는 현물입니다. 서로 다른 상품입니다. '+note;
 if(related==='UST10Y')note='위 숫자는 시장 국채 수익률, 아래 차트는 FRED 고정만기 수익률입니다. '+note;
 if(q.status==='stale')note='최신 조회 실패 · 이전 검증 수치 유지. '+note;
 return '<span class="quote-label">'+esc(q.quoteLabel||q.name||q.id)+'</span><strong>'+num(q.value,q.precision??2)+'</strong><span class="quote-unit">'+esc(q.unit||'')+'</span><span class="quote-asof">시세 기준 '+(q.observedAt?stamp(q.observedAt):esc(q.asOf||'미확인'))+' · <a href="'+esc(safeURL(q.sourceUrl))+'" target="_blank" rel="noopener noreferrer">'+esc(q.sourceName||q.source||'Investing.com')+' ↗</a></span>'+(note?'<span class="quote-note">'+esc(note)+'</span>':'');
}
function renderQuotes(d){
 const rows=Array.isArray(d.rows)?d.rows:Object.values(d.rows||{});
 const map=Object.fromEntries(rows.map(q=>[q.id||q.key,q]));
 document.querySelectorAll('[data-macro-quote]').forEach(el=>{const id=el.dataset.macroQuote;el.innerHTML=quoteHTML(map[id],id);});
 document.querySelectorAll('.rate-card[data-series]').forEach(card=>{
   const q=map[card.dataset.series];if(!q||!finite(q.value))return;
   let el=card.querySelector('.macro-fred-value');
   if(!el){el=document.createElement('div');el.className='macro-fred-value rate-source';card.querySelector('.rate-head').after(el);}
   el.innerHTML='차트와 동일한 FRED 계열: <strong>'+num(q.value,q.precision??2)+' '+esc(q.unit||'')+'</strong> · 관측일 '+esc(q.asOf)+' · <a href="'+esc(safeURL(q.sourceUrl))+'" target="_blank" rel="noopener noreferrer">원본 ↗</a>'+(q.status==='stale'?' · 이전 검증값 유지':'');
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
 (thirdDir?'<p>'+esc(third.date)+'까지 현재보다 높은 목표금리에 도달할 확률은 '+percent(thirdDir.hike)+'입니다. 다음 회의의 동결 기대가 높더라도 이후 인상 경로 기대는 함께 존재할 수 있습니다.</p>':'')+
 conditionalHTML(d)+'<p class="fedwatch-caveat">표는 현재 대비 누적 목표금리 수준의 Aggregated 확률이며 각 회의 한 번의 인상 확률이 아닙니다. 전일·전주·전월 변화는 다음 회의에 한정해 CME Current 비교표의 동일한 한 자리 소수점 수치를 사용합니다. 주말 비교 기준일은 CME 표시 날짜를 그대로 따릅니다.</p>'+
 '<p class="fedwatch-caveat">선물가격에서 계산한 시장 내재 확률이며 연준의 약속·예측이 아닙니다. CME 공개 화면 검증 스냅샷으로 자동 실시간 갱신되지 않습니다. '+(d.providerAsOf?'CME Current 화면 시각 '+stamp(d.providerAsOf)+'; 위 Aggregated 표는 별도 시각이 표시되지 않아 검증 시각을 사용합니다. ':'')+'<a href="'+esc(safeURL(d.methodologyUrl))+'" target="_blank" rel="noopener noreferrer">CME 산출 방식 ↗</a></p></div>';
}
let lastLoad=0;
async function load(){
 if(window.location.hash.split('/')[0]!=='#rates'||Date.now()-lastLoad<60000)return;
 lastLoad=Date.now();
 const results=await Promise.allSettled(['macro_quotes','fedwatch'].map(n=>fetch('./data/'+n+'.json',{cache:'no-store'}).then(r=>{if(!r.ok)throw Error(r.status);return r.json();})));
 if(results[0].status==='fulfilled')renderQuotes(results[0].value);
 else document.querySelectorAll('[data-macro-quote]').forEach(el=>el.innerHTML='<span>수치 파일을 불러오지 못했습니다. 원본 링크를 확인해 주세요.</span>');
 if($('fedwatch-content'))$('fedwatch-content').innerHTML=results[1].status==='fulfilled'?fedwatchHTML(results[1].value):'<p class="market-note">자료를 불러오지 못했습니다. CME 원본을 확인해 주세요.</p>';
}
function boot(){window.addEventListener('hashchange',load);document.addEventListener('visibilitychange',()=>{if(!document.hidden)load();});load();}
window.TerminalMacro={direction,validFedwatch,quoteHTML,fedwatchHTML,safeURL,range};
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot,{once:true});else boot();
}());
