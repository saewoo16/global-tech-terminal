/* Source-backed Korean market analysis. Unknown values stay null, never zero. */
(function () {
  'use strict';
  const el = id => document.getElementById(id);
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const list = value => Array.isArray(value) ? value : [];
  const finite = value => typeof value === 'number' && Number.isFinite(value);
  const fmt = (value, digits=0) => finite(value) ? value.toLocaleString('ko-KR',{maximumFractionDigits:digits}) : '미확인';
  // Display rounding is separate from source values, calculations and percentage formatting.
  const rounded = value => finite(value) ? Math.sign(value)*Math.round(Math.abs(value))||0 : null;
  const integer = value => fmt(rounded(value));
  const signedInteger = value => finite(value) ? (rounded(value)>0?'+':'')+integer(value) : '미확인';
  const signed = value => finite(value) ? `<span class="kr-value ${rounded(value)>0?'up':rounded(value)<0?'down':''}">${signedInteger(value)}</span>` : '<span class="muted">미확인</span>';
  function briefDisplayText(value) {
    // Only explicitly labeled money/index tokens in briefing paragraphs; never process HTML or source records.
    const number = token => {const value=Number(token.replaceAll(',',''));return (token.startsWith('+')&&rounded(value)>0?'+':'')+integer(value);};
    return String(value??'').split(/(https?:\/\/\S+)/g).map((text,index)=>index%2?text:text.replace(/(^|[\s(])([+-]?\d[\d,]*\.\d+)(?=원)/g,(_,prefix,token)=>prefix+number(token))
      .replace(/(US\$)([+-]?\d[\d,]*\.\d+)(?!\d|\.\d|%)/g,(_,prefix,token)=>prefix+number(token))
      .replace(/((?:나스닥종합|코스피|코스닥|KOSPI|KOSDAQ)(?:은|는|지수는)?\s+)([+-]?\d[\d,]*\.\d+)(?!\d|\.\d|%)/g,(_,prefix,token)=>prefix+number(token))).join('');
  }
  const safe = value => {try {const url=new URL(value);return ['https:','http:'].includes(url.protocol)&&!url.username&&!url.password?url.href:'';} catch (_) {return '';}};
  const isDate = value => typeof value==='string' && /^\d{4}-\d{2}-\d{2}$/.test(value) && Number.isFinite(Date.parse(value)) && new Date(value).toISOString().slice(0,10)===value;
  const COLORS = {foreign:'#f3b971',institution:'#88a9ff',individual:'#5ad3bd',deposits:'#88a9ff',creditKOSPI:'#f3b971',creditKOSDAQ:'#5ad3bd',openInterest:'#88a9ff',turnover:'#88a9ff',closingTurnover:'#f3b971',regularTurnover:'#88a9ff',integratedTurnover:'#f3b971'};
  const NAMES = {turnover:'ECOS 거래대금',closingTurnover:'KRX 마감(한경)',regularTurnover:'KRX 정규장',integratedTurnover:'NXT 포함',foreign:'외국인',institution:'기관',individual:'개인',deposits:'투자자예탁금',creditKOSPI:'KOSPI 신용융자',creditKOSDAQ:'KOSDAQ 신용융자'};
  let payload=null, loading=false, failed=false, flowRange='1M', futuresRange='1M', liquidityRange='3Y', selected='', selectedIndex='KOSPI200', moversPeriod='day', rankMarket='ALL', sectorSort='day', sectorDescending=true;
  let charts = new Map(), selectedBriefDate='', lastLoaded=0, rankDatePinned=false;
  function empty(message) {return `<div class="kr-empty">${esc(message||'검증된 자료를 아직 확보하지 못했습니다. 미확인은 0 또는 해당 없음이 아닙니다.')}</div>`;}
  function sourceLinks(ids) {return list(ids).map(id=>list(payload?.sources).find(s=>s.id===id)).filter(Boolean).map(s=>{const href=safe(s.url);return href?`<a href="${esc(href)}" target="_blank" rel="noopener noreferrer">${esc(s.title||s.id)} ↗</a>`:'';}).join(' ');}
  function meta(section, suffix='') {
    const cov=section?.coverage||{}, rows=list(section?.rows), first=cov.start||rows[0]?.date, last=cov.end||rows.at(-1)?.date;
    const dateLabel=first&&last?`${first} ~ ${last}`:last||first||'기준일 미확인';
    const counts=Number.isInteger(cov.sampleCount)?`${fmt(cov.validCount??cov.sampleCount)}/${fmt(cov.sampleCount)}개 종목 확인`:Number.isInteger(cov.count)?`${fmt(cov.count)}개 관측`:rows.length?`${fmt(rows.length)}개 관측`:'';
    return `<p class="kr-coverage-line">${esc([dateLabel,counts,section?.status==='partial'?'일부 확인':section?.status==='unavailable'?'미확보':''].filter(Boolean).join(' · '))}</p><details class="kr-metadata"><summary>${esc([dateLabel,counts,suffix,section?.status==='partial'?'일부 확인':section?.status==='unavailable'?'미확보':'','출처·확인 범위'].filter(Boolean).join(' · '))}</summary>${section?.note?`<p>${esc(section.note)}</p>`:''}${cov.note?`<p>${esc(cov.note)}</p>`:''}${cov.actualCountNote?`<p>${esc(cov.actualCountNote)}</p>`:''}${section?.status==='partial'||section?.status==='unavailable'?`<p>수집 상태: ${section.status==='partial'?'일부 확인':'미확보'}. 결측값을 보간하거나 0으로 채우지 않습니다.</p>`:''}${sourceLinks(section?.sourceIds)}</details>`;
  }
  const FLOW_SESSIONS = {'1W':5,'1M':21,'3M':63,'6M':126,'1Y':252};
  function rangeRows(rows, range, tradingSessions=false) {
    const sorted=list(rows).filter(r=>r&&isDate(r.date)).slice().sort((a,b)=>a.date.localeCompare(b.date));
    if (!sorted.length || range==='3Y') return sorted;
    if(tradingSessions)return sorted.slice(-(FLOW_SESSIONS[range]||21));
    const start=new Date(sorted.at(-1).date+'T00:00:00Z');
    if (range==='1Y') start.setUTCFullYear(start.getUTCFullYear()-1); else {const months=({'1M':1,'3M':3,'6M':6})[range]||3,day=start.getUTCDate();start.setUTCDate(1);start.setUTCMonth(start.getUTCMonth()-months);start.setUTCDate(Math.min(day,new Date(Date.UTC(start.getUTCFullYear(),start.getUTCMonth()+1,0)).getUTCDate()));}
    return sorted.filter(r=>r.date>=start.toISOString().slice(0,10));
  }
  function chartModel(rows, keys, range, includeZero, tradingSessions=false) {
    const filtered=rangeRows(rows,range,tradingSessions), values=filtered.flatMap(r=>keys.map(k=>r[k])).filter(finite);
    if(!filtered.length||!values.length) return null;
    let min=Math.min(...values),max=Math.max(...values);
    if(includeZero){min=Math.min(min,0);max=Math.max(max,0);}
    const pad=(max-min||Math.abs(max)||1)*.08;min-=pad;max+=pad;
    const width=620,height=260,left=62,right=12,top=16,bottom=31;
    const x=i=>left+(width-left-right)*(filtered.length===1?.5:i/(filtered.length-1)), y=v=>top+(height-top-bottom)*(max-v)/(max-min);
    const paths=keys.map(key=>{let path='',pen=false;filtered.forEach((r,i)=>{if(!finite(r[key])){pen=false;return;}path+=`${pen?'L':'M'}${x(i).toFixed(2)},${y(r[key]).toFixed(2)} `;pen=true;});return {key,path};});
    return {rows:filtered,keys,min,max,width,height,left,right,top,bottom,x,y,paths};
  }
  function tooltip(model, row) {return `<b>${esc(row.date)}${row.sourceBalanceWarning?' · 원자료 집계 주의':''}</b>${model.keys.map(key=>`<span style="color:${COLORS[key]||'#88a9ff'}">${esc(model.names?.[key]||NAMES[key]||key)} ${finite(row[key])?integer(row[key])+(model.unit||'억원'):'미확인'}</span>`).join('')}`;}
  function chart(id, rows, keys, range, label, includeZero=true, options={}) {
    const tradingSessions=options.tradingSessions??id.startsWith('flow-'),model=chartModel(rows,keys,range,includeZero,tradingSessions);if(!model)return empty();model.unit=options.unit||'억원';model.names=options.names||{};charts.set(id,model);
    const ticks=Array.from({length:5},(_,i)=>model.max-(model.max-model.min)*i/4);
    const dateIndexes=[...new Set([0,Math.floor((model.rows.length-1)/2),model.rows.length-1])];
    const legend=keys.map(key=>`<span><i style="background:${COLORS[key]||'#88a9ff'}"></i>${esc(model.names?.[key]||NAMES[key]||key)}</span>`).join('');
    const lines=ticks.map(value=>`<line class="kr-gridline" x1="${model.left}" x2="${model.width-model.right}" y1="${model.y(value)}" y2="${model.y(value)}"/><text x="${model.left-8}" y="${model.y(value)+3}" text-anchor="end">${integer(value)}</text>`).join('');
    const dates=dateIndexes.map((i,n)=>`<text x="${model.x(i)}" y="${model.height-8}" text-anchor="${n===0?'start':n===dateIndexes.length-1?'end':'middle'}">${model.rows[i].date}</text>`).join('');
    const paths=model.paths.map(p=>`<path d="${p.path}" fill="none" stroke="${COLORS[p.key]||'#88a9ff'}" stroke-width="1.4" vector-effect="non-scaling-stroke"/>`).join('');
    const zero=includeZero&&model.min<=0&&model.max>=0?`<line class="kr-zero" x1="${model.left}" x2="${model.width-model.right}" y1="${model.y(0)}" y2="${model.y(0)}"/>`:'';
    return `<div class="kr-legend">${legend}</div><div class="kr-chart" data-kr-chart="${id}"><svg viewBox="0 0 ${model.width} ${model.height}" role="img" aria-label="${esc(label)}. ${model.rows[0].date}부터 ${model.rows.at(-1).date}, ${model.rows.length}개 일별 관측, 단위 ${esc(model.unit)}. 아래 일별 표에서도 확인 가능합니다." tabindex="0">${lines}${zero}${dates}${paths}${list(options.isolatedPoints).flatMap(key=>model.rows.map((row,i)=>finite(row[key])?`<circle cx="${model.x(i)}" cy="${model.y(row[key])}" r="4" fill="${COLORS[key]}"/>`:``)).join('')}${list(options.showSingletons).flatMap(key=>model.rows.map((row,i)=>finite(row[key])&&!finite(model.rows[i-1]?.[key])&&!finite(model.rows[i+1]?.[key])?`<circle cx="${model.x(i)}" cy="${model.y(row[key])}" r="3" fill="${COLORS[key]}"/>`:``)).join('')}${model.rows.length===1&&!options.showSingletons?keys.filter(key=>finite(model.rows[0][key])).map(key=>`<circle cx="${model.x(0)}" cy="${model.y(model.rows[0][key])}" r="3" fill="${COLORS[key]}"/>`).join(''):''}<line data-kr-cursor x1="0" x2="0" y1="16" y2="229" stroke="#9bb0d1" stroke-dasharray="3 3" visibility="hidden"/></svg><div class="kr-tooltip" data-kr-tooltip aria-live="off">${tooltip(model,model.rows.at(-1))}</div></div><details class="kr-chart-table"${options.tableOpen?' open':''}><summary>일별 데이터 표 · ${model.rows.length}개 관측</summary><div class="kr-table-wrap" tabindex="0" role="region" aria-label="${esc(label)} 일별 표"><table class="kr-table"><thead><tr><th scope="col">날짜</th>${keys.map(key=>`<th scope="col">${esc(model.names?.[key]||NAMES[key]||key)} · ${esc(model.unit)}</th>`).join('')}</tr></thead><tbody>${model.rows.slice().reverse().map(row=>`<tr><td>${row.date}${row.sourceBalanceWarning?'<small>원자료 집계 주의</small>':''}</td>${keys.map(key=>`<td>${includeZero?signed(row[key]):integer(row[key])}</td>`).join('')}</tr>`).join('')}</tbody></table></div></details>`;
  }
  function ranges(kind, active) {
    const sessionRange=['flow','futures'].includes(kind),choices=sessionRange?[['1W','1주'],['1M','1개월'],['3M','3개월'],['6M','6개월'],['1Y','1년']]:[['3M','3개월'],['1Y','1년'],['3Y','3년']];
    return `<div class="kr-controls" role="group" aria-label="${kind==='flow'?'투자자 순매수':kind==='futures'?'KOSPI 200 선물':'예탁금·신용잔고'} 차트 기간">${choices.map(([value,label])=>`<button type="button" data-kr-range="${kind}" data-range="${value}" aria-pressed="${active===value}"${sessionRange?` title="최근 ${FLOW_SESSIONS[value]}개 거래일 관측"`:''}>${label}</button>`).join('')}</div>`;
  }
  function latestBrief() {const entries=list(window.TerminalBriefingData?.entries).filter(entry=>entry?.market==='KR'&&isDate(entry.date)).sort((a,b)=>b.date.localeCompare(a.date));return entries[0]||null;}
  function briefSourceLinks(ids, entry) {return list(ids).map(id=>list(entry?.sources).find(source=>source.id===id)).filter(Boolean).map(source=>safe(source.url)?`<a href="${esc(safe(source.url))}" target="_blank" rel="noopener noreferrer" title="${esc(source.note||'')}">${esc(source.title||source.id)} ↗</a>`:'').join(' ');}
  function briefSources(entry, ids, note) {return `<details class="kr-metadata"><summary>${esc(entry?.date||'')} 기준 · 출처·확인 범위</summary>${note?`<p>${esc(note)}</p>`:''}${briefSourceLinks([...new Set(ids)],entry)}</details>`;}
  function pct(value) {return finite(value)?`<span class="kr-value ${value>0?'up':value<0?'down':''}">${value>0?'+':''}${fmt(value,2)}%</span>`:'<span class="muted">미확인</span>';}
  function closeSection() {
    const entry=latestBrief();
    if(!entry)return `<section class="kr-section" id="kr-close"><div class="kr-section-head"><h3>국내 시장 마감</h3></div>${empty(window.TerminalBriefingData?.failed?'일일 분석 자료를 불러오지 못했습니다. 아래 수급·자금 자료는 별도로 표시합니다.':'일일 분석을 불러오는 중입니다.')}</section>`;
    const stories=list(entry.summary), follow=stories.filter(story=>/휴장일 후속/.test(story.title||'')), close=stories.filter(story=>!/휴장일 후속/.test(story.title||''));
    const ids=[...stories.flatMap(story=>list(story.sourceIds)),...list(entry.indices).flatMap(row=>list(row.sourceIds))];
    return `<section class="kr-section kr-close" id="kr-close" aria-labelledby="kr-close-title"><div class="kr-close-top"><div><div class="eyebrow">KOREA MARKET CLOSE · ${entry.date}</div><h3 id="kr-close-title">${esc(entry.title||'국내 시장 마감')}</h3><p>한국 현지 ${entry.date} 마감 기준 · 이후 소식은 별도 표시</p></div><div class="kr-close-indices">${list(entry.indices).map(index=>`<article><small>${esc(index.name)}</small><strong>${integer(index.close)}</strong>${pct(index.changePct)}</article>`).join('')}</div></div><div class="kr-close-points">${close.map(story=>`<article><h4>${esc(story.title)}</h4><p>${esc(briefDisplayText(story.text))}</p></article>`).join('')}</div>${follow.length?`<details class="kr-holiday"><summary>휴장일 후속 소식 · ${follow.length}건</summary><p class="kr-note">아래 소식은 ${entry.date} 마감 이후 정보입니다. 새로운 국내 거래일 수치가 아닙니다.</p>${follow.map(story=>`<article><h4>${esc(story.title)}</h4><p>${esc(briefDisplayText(story.text))}</p></article>`).join('')}</details>`:''}${briefSources(entry,ids,'마감 시황은 날짜별로 검증한 분석 자료입니다. 아래 일별 수급은 별도의 NAVER 최신 일별 표이며 마감 기사와 집계시각이 다를 수 있습니다.')}</section>`;
  }
  function analysisControls() {return `<div class="kr-analysis-controls"><button class="button" id="kr-refresh" type="button">최신 게시 자료 확인</button></div>`;}

  // A dated original comparison of selected observations, not the archived market-cap universe.
  const REPORTED_HEATMAP_DATE='2026-11-18';
  // Selected closing-price facts from 11/18 regular-session reporting, with 11/17 comparison prices.
  const REPORTED_HEATMAP=Object.freeze({
    KOSPI:[['005930',194700,190300],['000660',1144000,1098000],['402340',709000,679000],['373220',305000,305500],['207940',1366000,1414000],['005380',267000,259000]],
    KOSDAQ:[['196170',170900,173000],['086520',69000,67600],['247540',85500,84700],['277810',407000,339000],['036930',150500,147700],['000250',137300,160700]]
  });
  const hasCapHeatmap=(date,section)=>isDate(date)&&section?.asOf===date&&['KOSPI','KOSDAQ'].every(m=>{
    const market=section.markets?.[m],coverage=market?.coverage;
    return market?.asOf===date&&coverage?.isFullUniverseAttempt===true&&coverage?.topNLimit==null&&list(market.rows).some(row=>finite(row.marketCapKRW)&&row.marketCapKRW>0&&finite(row.changePct));
  });
  function currentDomesticDate() {return [latestBrief()?.date,payload?.asOf].filter(isDate).sort().at(-1);}
  function renderMarketHeader() {
    const target=el('kr-asof');if(!target)return;
    // The archive metadata does not establish a new completed market close.
    const verifiedClose=latestBrief()?.date, activeDate=currentDomesticDate();
    const closeDate=verifiedClose===activeDate?activeDate:verifiedClose;
    target.innerHTML=`<span>마감 기준일</span><strong>${esc(closeDate||'미확인')}</strong><span>수급·업종 등은 항목별 실제 관측일로 표시</span>`;
  }
  function freshnessSection() {
    const latest=list(window.TerminalBriefingData?.entries).filter(e=>e?.market==='KR'&&isDate(e.date)).sort((a,b)=>b.date.localeCompare(a.date))[0];
    const sector=payload?.sectorReturns,sectorRows=list(sector?.rows),sectorCurrent=sectorRows.filter(row=>(row.asOf||sector?.asOf)===sector?.asOf).length,sectorDate=sector?.asOf+(sectorRows.length&&sectorCurrent<sectorRows.length?' · '+sectorCurrent+'/'+sectorRows.length+'개 최신 · '+(sectorRows.length-sectorCurrent)+'개 이전일 유지':'');
    const flowDate=reportedFlowEvidence()?.observation?.date;const rows=[['최신 시황',latest?.date],['당일 수급',flowDate?flowDate+' · 잠정':null],['수급 추이',payload?.asOf],['업종 수익률',sector?.asOf?sectorDate+(latest?.date&&sector.asOf!==latest.date?' · 이전일 참고':''):null],['신고가 선별',payload?.highsScreen?.asOf],['히트맵',latest?.date===REPORTED_HEATMAP_DATE&&['KOSPI','KOSDAQ'].every(m=>reportedHeatmapRows(m).length===REPORTED_HEATMAP[m].length)?latest.date+' · 선별 12종목':hasCapHeatmap(payload?.heatmaps?.asOf,payload?.heatmaps)?payload.heatmaps.asOf+(payload.heatmaps.asOf===latest?.date?'':' · 이전일 참고'):null],['종목 순매수',list(payload?.rankings?.dates).slice().sort().at(-1)],['테마 수급',latest?.date&&latestDailySnapshot('themes',null,latest.date).date===latest.date?latest.date:null],['지수 종목 등락',list(payload?.indexMovers?.dates).slice().sort().at(-1)],['예탁금·신용',payload?.liquidity?.series?.deposits?.coverage?.end]];
    return `<div class="kr-freshness" id="kr-latest-status" aria-label="항목별 최신 검증일">${rows.map(([label,value])=>`<span>${label} <strong>${esc(value||'미확인')}</strong></span>`).join('')}</div>`;
  }
  function unusualMoverNews(row, entry) {
    const news=row?.news, sources=list(news?.sourceIds).map(id=>list(entry?.sources).find(source=>source.id===id)).filter(source=>source&&safe(source.url));
    if(!news?.text?.trim()||!isDate(news.date)||!sources.length)return '';
    return `<p class="kr-mover-news"><small>관련 뉴스 · ${esc(news.date)}</small><br>${esc(news.text)} <a href="${esc(safe(sources[0].url))}" target="_blank" rel="noopener noreferrer" title="${esc(sources[0].title||'관련 뉴스')}">출처 ↗</a></p>`;
  }
  function unusualMoversSection() {
    const entry=latestBrief(),section=entry?.movers||{},rows=list(section.rows);
    return `<section class="kr-section" id="kr-unusual"><div class="kr-section-head"><div><h3>이례적 상승 · 하락</h3><p>${esc(entry?.date||'미확인')} · ${rows.length}개 확인 사례 · 가격·거래량 동시조건</p></div></div><p class="kr-note">${esc(section.criteria||'선별 기준 미확인')}</p>${rows.length?`<div class="kr-story-grid">${rows.map(row=>`<article class="kr-story"><h4>${esc(row.name)} <small>${esc(row.ticker)}</small> ${pct(row.changePct)}</h4><div class="kr-story-metrics"><div><small>당일 거래량</small><strong>${fmt(row.volumeCurrent)}주</strong></div><div><small>전일 거래량</small><strong>${fmt(row.volumePrevious)}주</strong></div><div><small>전일 대비 거래량</small><strong>${pct(row.volumeChangePct)}</strong></div></div>${unusualMoverNews(row,entry)}${row.regularSessionVolumeCertified===false?'<p>일별 거래량 기준 · 정규장 전용 범위 미확인</p>':''}${briefSources(entry,[...list(row.sourceIds),...list(row.news?.sourceIds)],[row.reason,row.volumeBasis].filter(Boolean).join(' '))}</article>`).join('')}</div>`:empty('검증된 사례를 아직 확보하지 못했습니다. 전체 시장에 해당 사례가 없다는 뜻이 아닙니다.')}${briefSources(entry,[],section.note)}</section>`;
  }
  function earningsHighlights(row) {
    return list(row.displayCallHighlights||row.callHighlights).filter(text=>typeof text==='string' && text.trim() && !/교차확인|HTTP\d|직접 확인했습니다|직접 대조.*미완료|원문.*미확인|미확인 상태로 남|정밀 원자료/.test(text));
  }
  function quarterlyTable(row) {
    const history=row.quarterlyHistory||{}, rows=list(history.rows).slice(-4);if(!rows.length)return '';
    const number=(value,margin=false)=>finite(value)?fmt(value,margin?2:0)+(margin?'%':''):'—';
    const margin=q=>finite(q.revenue)&&q.revenue!==0&&finite(q.operatingIncome)?q.operatingIncome/q.revenue*100:null;
    return `<div class="kr-quarterly"><h5>최근 4개 분기</h5><p>${esc([history.unit,history.basis].filter(Boolean).join(' · '))}</p><div class="kr-table-wrap" tabindex="0" role="region" aria-label="${esc(row.name)} 최근 4개 분기 실적"><table class="kr-table"><thead><tr><th scope="col">분기</th><th scope="col">Rev</th><th scope="col">OP</th><th scope="col">OPM</th></tr></thead><tbody>${rows.map(q=>`<tr><th scope="row">${esc(q.period)}${q.basis&&q.basis!==history.basis?`<small> · ${esc(q.basis)}</small>`:''}</th><td>${number(q.revenue)}</td><td>${number(q.operatingIncome)}</td><td>${number(margin(q),true)}</td></tr>`).join('')}</tbody></table></div>${rows.some(q=>!finite(q.revenue)||!finite(q.operatingIncome)||!finite(margin(q)))?'<p class="kr-quarterly-key">— 미공시·미확인 또는 해당 없음</p>':''}</div>`;
  }
  function earningsSection() {
    const entry=latestBrief(),section=entry?.earnings||{},seen=new Set();
    const rows=list(section.rows).filter(row=>{const id=row.companyId||row.ticker;if(section.scope!=='KOSPI200_KOSDAQ150'||row.releaseDate!==entry?.date||row.membershipVerified!==true||!['KOSPI200','KOSDAQ150'].includes(row.universeScope)||seen.has(id))return false;seen.add(id);return true;});if(!rows.length)return '';
    return `<section class="kr-section" id="kr-earnings"><div class="kr-section-head"><div><h3>당일 실적 발표 · 컨퍼런스콜</h3><p>${esc(entry.date)} KST 발표 · ${rows.length}개 확인 기업 · KOSPI200 / KOSDAQ150</p></div></div>${section.coverageNote?`<p class="kr-note">${esc(section.coverageNote)}</p>`:''}<div class="kr-earnings-grid">${rows.map(row=>{const highlights=row.callStatus==='transcript_verified'?earningsHighlights(row):[],release=list(row.releaseHighlights).filter(x=>typeof x==='string'&&x.trim());return `<article class="kr-story kr-earnings-card"><h4>${esc(row.name)} <small>${esc(row.ticker)} · ${esc(row.universeScope)}</small></h4><p class="kr-earnings-period">${esc(row.period||'')} · 발표 ${esc(row.releaseDate)} KST${row.releaseType==='preliminary'?' · 잠정실적':''}</p>${quarterlyTable(row)}${highlights.length?`<div class="kr-call"><h5>컨퍼런스콜 요약</h5><ul>${highlights.map(text=>`<li>${esc(text)}</li>`).join('')}</ul></div>`:release.length?`<div class="kr-call"><h5>회사 실적 발표 · 관련 이슈</h5><ul>${release.map(text=>`<li>${esc(text)}</li>`).join('')}</ul></div>`:''}${briefSources(entry,[...list(row.sourceIds),...list(row.quarterlyHistory?.rows).flatMap(q=>list(q.sourceIds))],[row.note,row.quarterlyHistory?.note,'구성 확인일: '+row.membershipAsOf,'실제 자료 확인: '+row.observedAt].filter(Boolean).join(' '))}</article>`;}).join('')}</div>${briefSources(entry,list(section.sourceIds),section.note)}</section>`;
  }
  function analysisSources() {
    const entry=latestBrief();if(!entry)return '';
    return `<details class="kr-source-list"><summary>${esc(entry.date)} 일일 분석 출처·확인 범위</summary>${list(entry.watchlist).length?`<h4>다음 거래일 확인 사항</h4><ul>${entry.watchlist.map(x=>`<li>${esc(x)}</li>`).join('')}</ul>`:''}<ul>${list(entry.limitations).map(x=>`<li>${esc(x)}</li>`).join('')}</ul>${briefSourceLinks(list(entry.sources).map(x=>x.id),entry)}</details>`;
  }
  function bindAnalysisControls(){
    if(el('kr-analysis-date'))el('kr-analysis-date').onchange=event=>{selectedBriefDate=event.target.value;window.location.hash='#korea'+(selectedBriefDate?'/'+selectedBriefDate:'');render();};
    if(el('kr-refresh'))el('kr-refresh').onclick=()=>{window.TerminalRefreshArchive?.();load();};
  }
  // The two scopes stay separate; absent dates are explicit nulls, never copied or summed.
  const turnoverMarkets=['KOSPI','KOSDAQ'];
  function closeObservation(key,scope,status) {
    const entry=latestBrief(), observation=entry?.[key];
    if(!observation||observation.date!==entry.date||observation.scope!==scope||observation.status!==status||!Number.isFinite(Date.parse(observation.observedAt)))return null;
    const byId=new Map(list(entry.sources).map(source=>[source?.id,source]));
    const ids=list(observation.sourceIds);
    if(new Set(ids).size<2||!ids.every(id=>byId.get(id)?.title&&safe(byId.get(id)?.url)))return null;
    const citations=ids.map(id=>{const s=byId.get(id);return `<a href="${esc(safe(s.url))}" target="_blank" rel="noopener noreferrer">${esc(s.title)} ↗</a>`;}).join(' · ');
    return {observation,citations};
  }
  function marketTurnoverSection() {
    const evidence=closeObservation('regularClosingTurnover','krx-regular-market-close','reported-approximate'), observation=evidence?.observation;
    const valid=observation?.unit==='조원'&&turnoverMarkets.every(market=>finite(observation.markets?.[market])&&observation.markets[market]>0);
    const cards=valid?`<div class="kr-grid">${turnoverMarkets.map(market=>`<article class="kr-card"><div class="kr-card-head"><h4>${market}</h4><span class="kr-badge">${esc(observation.date)} · 마감 보도 기준</span></div><div class="kr-daily-values"><div><small>KRX 정규장</small><strong>약 ${fmt(observation.markets[market],1)}조원</strong></div></div></article>`).join('')}</div><p class="kr-note">출처: ${evidence.citations}</p>`:'<p class="kr-note">최신 KRX 정규장 거래대금은 아직 확인되지 않았습니다.</p>';
    return `<section class="kr-section" id="kr-market-turnover" aria-labelledby="kr-market-turnover-title"><div class="kr-section-head"><div><h3 id="kr-market-turnover-title">시장 거래대금 · KRX 정규장</h3><p>KOSPI · KOSDAQ 시장 전체 · NXT 및 시간외 제외</p></div></div>${cards}<p class="kr-note">같은 기준으로 확인한 과거 자료가 없어 추이 차트는 표시하지 않습니다. 기존 KRX+NXT 합산 자료나 ECOS 공표값과 연결하지 않습니다.</p></section>`;
  }
  function reportedFlowEvidence() {
    const evidence=closeObservation('reportedCloseFlow','krx-market-close-reports','reported-provisional'), observation=evidence?.observation;
    const data=observation?.roundedEok, markets=['KOSPI','KOSDAQ'], keys=['foreign','institution','individual'];
    return observation?.date===currentDomesticDate()&&observation?.unit==='억원'&&markets.every(m=>keys.every(k=>Number.isInteger(data?.[m]?.[k])&&Math.abs(data[m][k])<1000000))?evidence:null;
  }
  function dailyFlowSummary() {
    const evidence=reportedFlowEvidence(), observation=evidence?.observation, date=currentDomesticDate();
    const cards=observation?`<div class="kr-grid">${['KOSPI','KOSDAQ'].map(market=>`<article class="kr-card"><div class="kr-card-head"><h4>${market}</h4><span class="kr-badge">${esc(observation.date)} · 잠정</span></div><div class="kr-daily-values">${['foreign','institution','individual'].map(key=>`<div><small>${NAMES[key]}</small><strong>${signed(observation.roundedEok[market][key])}</strong></div>`).join('')}</div></article>`).join('')}</div><p class="kr-note">마감 보도를 대조한 대략적인 규모입니다. 보도마다 집계 시점이 달라 두 시장을 합산하거나 아래 과거 추이와 연결하지 않습니다.</p><p class="kr-note">출처: ${evidence.citations}</p>`:`<p class="kr-note">${esc(date||'최신 거래일')} 기준으로 표시할 당일 시장 수급을 확인하지 못했습니다.</p>`;
    return `<section class="kr-section" aria-labelledby="kr-daily-flow-title"><div class="kr-section-head"><div><h3 id="kr-daily-flow-title">당일 시장 수급</h3><p>순매수(+) · 순매도(−) · 억원</p></div></div>${cards}</section>`;
  }
  function sectorReturnsSection() {
    const entry=latestBrief(),section=payload?.sectorReturns||entry?.sectors||{},rows=list(section.rows);
    const currentCount=rows.filter(row=>(row.asOf||section.asOf)===section.asOf).length,retainedCount=rows.length-currentCount;
    const rowDate=row=>row.asOf||section.asOf||entry?.date||'',currentDate=section.asOf||entry?.date||'';
    const sorted=rows.slice().sort((a,b)=>rowDate(a)!==rowDate(b)?(rowDate(a)===currentDate?-1:rowDate(b)===currentDate?1:rowDate(b).localeCompare(rowDate(a))):finite(a[sectorSort])&&finite(b[sectorSort])?(sectorDescending?b[sectorSort]-a[sectorSort]:a[sectorSort]-b[sectorSort]):finite(a[sectorSort])?-1:finite(b[sectorSort])?1:0);
    const headings=[['day','1일'],['week','1주'],['month','1개월']].map(([key,label])=>`<th scope="col" aria-sort="${sectorSort===key?(sectorDescending?'descending':'ascending'):'none'}"><button type="button" data-kr-sector-sort="${key}">${label}${sectorSort===key?(sectorDescending?' ↓':' ↑'):' ↕'}</button></th>`).join('');
    let groupRank=0;
    const body=sorted.map((row,i)=>{const date=rowDate(row),isCurrent=date===currentDate,newDate=i===0||date!==rowDate(sorted[i-1]);if(newDate)groupRank=0;groupRank++;const divider=newDate?`<tr class="kr-sector-date-group" data-sector-date="${esc(date)}"><th colspan="5" scope="colgroup">${isCurrent?'최신 거래일 '+esc(date)+' · 당일 순위':'이전 기준일 '+esc(date)+' · 참고용 · 오늘 순위에서 제외'}</th></tr>`:'';const group=row.group||'업종 비교';const holding=row.holdings, names=row.instrumentType==='etf'&&holding?.status==='verified'&&list(holding.top5).length===5?list(holding.top5).slice(0,3).map(item=>esc(item.shortName||item.name)).join(' / '):null,basketNames=list(row.constituents||row.members||row.constituentMetadata?.members).map(item=>esc(item.shortName||item.name)).join(' / ');return `${divider}<tr data-sector-row-date="${esc(date)}"><td>${isCurrent?groupRank:"참고"}</td><td><strong>${esc(row.name)}</strong><small>${esc(group)}</small><small>${esc(row.asOf||section.asOf||entry?.date||'미확인')} 기준${row.refreshStatus==='retained_previous'?' · 이전 검증값 보존':''}</small>${names?`<small>(${names})</small>`:row.instrumentType==='basket'?`<small>대표 종목 바스켓${basketNames?' ('+basketNames+')':''}</small>`:'<small>상위 3종목 미확인</small>'}</td><td>${pct(row.day)}</td><td>${pct(row.week)}</td><td>${pct(row.month)}</td></tr>`;}).join('');
    const ids=rows.flatMap(row=>[...list(row.sourceIds),...list(row.holdings?.sourceIds)]);
    const holdingDates=rows.map(row=>`${row.name} · ${row.ticker||''} · ${row.benchmark||''}${row.holdings?.asOf?' · 보유내역 '+row.holdings.asOf:''}`).join(' / ');
    const note=[section.methodology,section.priceAdjustment,section.priceSessionScope,section.note,section.chartUniverseNote,holdingDates].filter(Boolean).join(' '),asOf=section.asOf||entry?.date;
    const rowDetails=payload?.sectorReturns?rows.map(row=>`<details class="kr-metadata"><summary>${esc(row.name)} · ${esc(row.proxyTypeLabel||row.instrumentType)} · 계산·구성 근거</summary><p>${esc(row.ticker||'')} · ${esc(row.benchmark||'')}</p><p>${esc(row.scopeNote||'')} ${esc(row.methodology||'')} ${esc(row.refreshNote||'')}</p><p>${esc(row.holdings?.asOf?'구성 기준일 '+row.holdings.asOf:'')}</p>${sourceLinks([...new Set([...list(row.sourceIds),...list(row.holdings?.sourceIds)])])}</details>`).join(''):'';
    const details=payload?.sectorReturns?meta({...section,status:section.status||'verified',sourceIds:[...new Set([...list(section.sourceIds),...ids])],note,coverage:{start:rows.map(row=>row.asOf||asOf).filter(Boolean).sort()[0]||asOf,end:rows.map(row=>row.asOf||asOf).filter(Boolean).sort().at(-1)||asOf}},'수익률·구성 근거'):briefSources(entry,ids,note);
    return `<section class="kr-section" id="kr-sector-returns" aria-labelledby="kr-sector-return-title"><div class="kr-section-head"><div><h3 id="kr-sector-return-title">업종별 수익률</h3><p>최신 가격 ${esc(asOf||'미확인')} · ${currentCount}/${rows.length}개 최신${retainedCount?' · '+retainedCount+'개 이전일 유지':''} · 이전 기준일 자료는 하단 참고 구역으로 분리 · 같은 기준일 안에서 기본 1일 수익률 높은 순 · 열 제목으로 정렬</p></div></div><article class="kr-card">${rows.length?`<div class="kr-table-wrap" tabindex="0" role="region" aria-label="국내 업종별 1일 1주 1개월 수익률"><table class="kr-table kr-sector-return-table"><caption>괄호는 검증된 ETF 편입비중 상위 3개 보유종목 · 대표 종목 바스켓은 별도 표시 · 산식·기준일·ETF 정보는 아래 출처</caption><thead><tr><th scope="col">#</th><th scope="col">업종 (구성종목)</th>${headings}</tr></thead><tbody>${body}</tbody></table></div>`:empty('검증된 국내 업종 수익률을 불러오지 못했습니다.')}${details}${rowDetails}</article></section>`;
  }
  // One dated independently sourced reference, not the 52-week screen or historical data.
  function standaloneCloseBreakout(entry) {
    if(entry?.market!=='KR'||entry.date!=='2026-11-18')return '';
    return '<aside class="kr-card" aria-label="11월 18일 종가 신고가 확인 사례"><div class="kr-card-head"><h4>종가 돌파 · 별도 확인 사례</h4><span class="kr-badge">2026-11-18 · 1건</span></div>'+
      '<div class="kr-card-body"><p><strong>진양산업 (003780)</strong> · 정규장 종가 <strong>8,000원</strong> '+pct(19.40)+' · 장중 고가 <strong>8,590원</strong></p>'+
      '<p class="kr-note">매동 집계에서 직전 250거래일의 최고 종가를 넘어선 사례입니다. 장중 고가 8,590원은 당일 값이며, 이전 52주 장중 고가를 돌파했다는 뜻은 아닙니다. 위 선별 목록과 기준이 다르며, 전 종목을 검증한 결과가 아닙니다.</p>'+
      '<p><a href="https://maedong.kr/daily/2026-11-18" target="_blank" rel="noopener noreferrer">매동 · 종가 돌파 판정 ↗</a> · <a href="https://stock.mk.co.kr/price/home/KR7003780004" target="_blank" rel="noopener noreferrer">매일경제 · 당일 종가·장중 고가 ↗</a></p></div></aside>';
  }
  function highsSection() {
    const entry=latestBrief(),section=payload?.highsScreen||entry?.highs||{},rows=list(section.rows),coverage=section.coverage||entry?.screeningCoverage||{},asOf=section.asOf||entry?.date;
    const ids=rows.flatMap(row=>list(row.sourceIds)),newScreen=!!payload?.highsScreen;
    const details=newScreen?meta({...section,status:section.status||'verified',sourceIds:[...new Set([...list(section.sourceIds),...ids])],coverage:{...coverage,start:asOf,end:asOf}},'52주 고가 선별'):briefSources(entry,ids,section.note);
    const table=newScreen?`<div class="kr-table-wrap" tabindex="0" role="region" aria-label="52주 신고가와 근접 종목"><table class="kr-table kr-highs-table"><caption>진짜 신고가와 52주 고가까지 종가 기준 3% 이내인 종목을 구분합니다.</caption><thead><tr><th scope="col">종목</th><th scope="col">구분</th><th scope="col">종가 · 원</th><th scope="col">52주 고가 · 원</th><th scope="col">고가 대비</th><th scope="col">당일</th></tr></thead><tbody>${rows.map(row=>`<tr><th scope="row">${esc(row.name)}<small>${esc(row.code||row.ticker)}</small></th><td><span class="kr-high-label ${row.classification==='new_high'?'new':'near'}">${esc(row.classification==='new_high'?'52주 신고가':row.classification==='near_high'?'52주 고가 근접':row.kind||row.classification)}</span>${row.isNearHigh&&row.classification==='new_high'?'<span class="kr-high-label near">52주 고가 근접</span>':''}</td><td>${integer(row.close)}</td><td>${integer(row.high52)}</td><td>${pct(row.distancePct)}</td><td>${pct(row.changePct)}</td></tr>`).join('')}</tbody></table></div>`:rows.map(row=>`<article class="kr-card"><div class="kr-card-head"><h4>${esc(row.name)} <small class="muted">${esc(row.ticker)}</small></h4>${pct(row.changePct)}</div><div class="kr-card-body"><p class="kr-note">${esc(row.kind)}</p><p>${esc(row.reason)}</p></div></article>`).join('');
    return `<section class="kr-section" id="kr-highs" aria-labelledby="kr-highs-title"><div class="kr-section-head"><div><h3 id="kr-highs-title">52주 신고가 · 고가 근접 기업</h3><p>${esc(asOf||'미확인')} 기준 · ${esc(section.caption||'시가총액 상위 300개 기업 선별')}</p></div></div><p class="kr-note">${esc((section.criteria||'').replace('× 0.97','× 97%'))} 장중 신고가는 종가 신고가·사상 최고가를 뜻하지 않습니다.</p><div class="kr-highs-coverage">${[['선별 기업',coverage.selected],['당일 일봉 확인',coverage.dailyValid],['52주 이력 확인',coverage.full52WeekHistory],['짧은 상장 이력',coverage.shortHistoryCount??(coverage.selected-coverage.dailyValid<coverage.selected-coverage.full52WeekHistory?coverage.dailyValid-coverage.full52WeekHistory:null)],['검증 제외',coverage.missingCount]].map(([label,value])=>`<span>${label} <b>${fmt(value)}</b></span>`).join('')}</div><article class="kr-card">${rows.length?table:empty(coverage.full52WeekHistory>0?'52주 이력이 확인된 '+fmt(coverage.full52WeekHistory)+'개에서 신고가·근접 조건 충족 0개입니다. 미확인 종목은 별도이며 전체 시장에 없다는 뜻은 아닙니다.':'확인된 신고가·근접 목록이 없습니다. 미확인은 해당 사례가 없다는 뜻이 아닙니다.')}${details}</article>${standaloneCloseBreakout(entry)}</section>`;
  }
  // Squarified in the actual display aspect ratio; every area remains cap-proportional.
  function treemap(rows,x=0,y=0,width=100,height=100,aspect=1.42) {
    if(!rows.length)return [];
    const total=rows.reduce((sum,row)=>sum+row.marketCapKRW,0), scale=width*aspect*height/total;
    const pending=rows.map(row=>({...row,area:row.marketCapKRW*scale})), result=[];
    let left=0,top=0,w=width*aspect,h=height,index=0;
    const worst=(group,side)=>{const sum=group.reduce((n,row)=>n+row.area,0),min=Math.min(...group.map(row=>row.area)),max=Math.max(...group.map(row=>row.area));return Math.max(side*side*max/(sum*sum),sum*sum/(side*side*min));};
    while(index<pending.length){
      const group=[pending[index++]];let side=Math.min(w,h);
      while(index<pending.length&&worst([...group,pending[index]],side)<=worst(group,side))group.push(pending[index++]);
      const sum=group.reduce((n,row)=>n+row.area,0),vertical=w>=h,thickness=sum/(vertical?h:w);let offset=0;
      for(const row of group){const length=row.area/thickness;result.push({...row,x:x+(left+(vertical?0:offset))/aspect,y:y+top+(vertical?offset:0),width:(vertical?thickness:length)/aspect,height:vertical?length:thickness});offset+=length;}
      if(vertical){left+=thickness;w=Math.max(0,w-thickness);}else{top+=thickness;h=Math.max(0,h-thickness);}
    }
    return result;
  }
  function heatColor(value) {if(!finite(value))return '#3c485a';const strength=Math.min(Math.abs(value)/5,1);return value===0?'#46536a':value>0?`hsl(156 55% ${22+strength*19}%)`:`hsl(347 57% ${25+strength*20}%)`;}
  const heatState={KOSPI:{scope:'30',expanded:false},KOSDAQ:{scope:'30',expanded:false}};
  let heatObserver=null, heatArchiveOpen=false;
  function heatmapView(market) {
    const part=payload?.heatmaps?.markets?.[market]||{},all=list(part.rows).filter(row=>finite(row.marketCapKRW)&&row.marketCapKRW>0&&finite(row.changePct)).slice().sort((a,b)=>b.marketCapKRW-a.marketCapKRW||String(a.code).localeCompare(String(b.code)));
    const scope=heatState[market].scope,start=scope.startsWith('range-')?Number(scope.slice(6)):0;
    const rows=scope==='all'?all:all.slice(start,start+(scope==='100'?100:30));
    const total=all.reduce((sum,row)=>sum+row.marketCapKRW,0),shown=rows.reduce((sum,row)=>sum+row.marketCapKRW,0);
    const label=scope==='all'?'검증 종목 전체':start?`시총 ${start+1}–${Math.min(start+30,all.length)}위 확대`:`시총 상위 ${rows.length}종목`;
    return {part,all,rows,label,coverage:total?shown/total*100:0};
  }
  function industryFor(row) {
    return row.industry?.id&&row.industry?.name?row.industry:{id:'unclassified',name:'미분류'};
  }
  function groupedTreemap(rows, aspect=1.42) {
    const byIndustry=new Map();
    rows.forEach(row=>{const industry=industryFor(row);if(!byIndustry.has(industry.id))byIndustry.set(industry.id,{id:industry.id,name:industry.name,rows:[],marketCapKRW:0});const group=byIndustry.get(industry.id);group.rows.push(row);group.marketCapKRW+=row.marketCapKRW;});
    const groups=treemap([...byIndustry.values()].sort((a,b)=>b.marketCapKRW-a.marketCapKRW||a.id.localeCompare(b.id)),0,0,100,100,aspect);
    const tiles=groups.flatMap(group=>treemap(group.rows,group.x,group.y,group.width,group.height,aspect).map(row=>({...row,industryId:group.id,industryName:group.name,groupTop:group.y})));
    return {groups,tiles};
  }
  function heatmapCard(market) {
    const section=payload.heatmaps,{part,all,rows,label,coverage}=heatmapView(market),state=heatState[market],layout=groupedTreemap(rows);
    const classification=section.classification||{},classified=all.filter(row=>industryFor(row).id!=='unclassified').length;
    const options=[['30','시총 상위 30'],['100','시총 상위 100'],['all',`전체 ${all.length}종목`],...Array.from({length:Math.max(0,Math.ceil(all.length/30)-1)},(_,i)=>{const start=(i+1)*30;return ['range-'+start,`시총 ${start+1}–${Math.min(start+30,all.length)}위 확대`];})];
    const tiles=layout.tiles.map((row,tileIndex)=>{const detail=`${row.name} (${row.code}) · ${row.industryName} · ${row.changePct>0?'+':''}${fmt(row.changePct,2)}% · 시가총액 ${integer(row.marketCapKRW/1e8)}억원`;return `<button type="button" tabindex="${tileIndex===0?0:-1}" class="kr-heat-tile" style="left:${row.x}%;top:${row.y}%;width:${row.width}%;height:${row.height}%;background:${heatColor(row.changePct)}" title="${esc(detail)}" aria-label="${esc(detail)}" data-kr-code="${esc(row.code)}" data-kr-heat-detail="${esc(detail)}"><b>${esc(row.name)}</b><span>${row.changePct>0?'+':''}${fmt(row.changePct,2)}%</span></button>`;}).join('');
    const groups=layout.groups.map(group=>`<div class="kr-heat-group" data-kr-industry="${esc(group.id)}" style="left:${group.x}%;top:${group.y}%;width:${group.width}%;height:${group.height}%" aria-hidden="true"><span>${esc(group.name)}</span></div>`).join('');
    return `<article class="kr-card kr-heat-card${state.expanded?' is-expanded':''}" data-kr-heat-card="${market}"><div class="kr-card-head"><h4>${market}</h4><span class="kr-badge">${esc(part.asOf||section.asOf)} · 검증 ${all.length}종목</span></div><div class="kr-controls kr-heat-controls"><label for="kr-heat-scope-${market}">표시 범위<select id="kr-heat-scope-${market}" data-kr-heat-scope="${market}" aria-label="${market} 히트맵 표시 범위">${options.map(([value,text])=>`<option value="${value}"${state.scope===value?' selected':''}>${esc(text)}</option>`).join('')}</select></label><button type="button" id="kr-heat-expand-${market}" data-kr-heat-expand="${market}" aria-pressed="${state.expanded}">${state.expanded?'기본 크기':'크게 보기'}</button></div><p class="kr-heat-current"><strong>${esc(label)}</strong> · ${rows.length}/${all.length}종목 · 검증 시총의 ${coverage>0&&coverage<0.1?'0.1% 미만':fmt(coverage,1)+'%'}<small>넓이는 현재 표시 범위 안에서 비교합니다. 업종별로 묶어 표시하며 한 종목은 한 업종에만 포함됩니다.${['all','100'].includes(state.scope)?' 작은 칸의 이름은 생략됩니다. 순위별 30종목 확대를 이용하세요.':' 다른 종목은 표시 범위에서 순위별로 확대하거나 전체 보기로 확인하세요.'}</small></p><div class="kr-treemap" role="group" aria-label="${market} 업종별 종목 히트맵 · ${esc(label)}" data-kr-heat-market="${market}">${tiles}${groups}</div><div class="kr-heat-industries" aria-label="${market} 현재 표시 업종">${layout.groups.map(group=>`<span>${esc(group.name)} <small>${group.rows.length}종목</small></span>`).join('')}</div><div class="kr-heat-detail" aria-live="polite">종목에 마우스를 올리거나 탭하면 업종·이름·등락률·시가총액이 표시됩니다.</div><p class="kr-note kr-heat-scope">업종 분류 ${esc(classification.asOf||'기준일 미확인')} · ${classified}/${all.length}종목 확인${classified<all.length?' · 미분류 '+(all.length-classified)+'종목':''}<br>${esc(part.coverage?.universe||part.note||'확인된 종목 시가총액 비중')} · 대상 ${integer(part.coverage?.eligibleCount||all.length)}개 · 거래정지 ${integer(part.coverage?.haltedCount||0)}개 · 시세 검증 제외 ${integer(part.coverage?.missingCount||0)}개</p><details class="kr-metadata kr-heat-numbers"><summary>검증 종목 전체 ${all.length}개 · 숫자로 보기</summary><div class="kr-table-wrap" tabindex="0"><table class="kr-table"><thead><tr><th scope="col">종목</th><th scope="col">업종</th><th scope="col">등락률</th><th scope="col">시가총액 · 억원</th></tr></thead><tbody>${all.map(row=>`<tr><td>${esc(row.name)}<small>${esc(row.code)}</small></td><td>${esc(industryFor(row).name)}</td><td>${pct(row.changePct)}</td><td>${integer(row.marketCapKRW/1e8)}</td></tr>`).join('')}</tbody></table></div></details>${meta({...part,status:part.status||(part.coverage?.isComplete===false?'partial':'verified'),sourceIds:[...new Set([...list(part.sourceIds||section.sourceIds),...list(classification.sourceIds)])],note:[section.note,part.note,classification.note].filter(Boolean).join(' '),coverage:{...part.coverage,start:part.asOf||section.asOf,end:part.asOf||section.asOf}})}</article>`;
  }
  function heatmapsSection(supplement='',status='',id='kr-heatmaps') {
    const section=payload?.heatmaps;if(!section)return '';
    return `<section class="kr-section kr-heatmaps" id="${id}" aria-labelledby="${id}-title" data-kr-heat-date="${esc(section.asOf||'')}"><div class="kr-section-head"><div><h3 id="${id}-title">KOSPI · KOSDAQ 히트맵</h3><p>${esc(section.asOf||'기준일 미확인')} 정규장 마감 · 넓이 = 표시 종목 내 시가총액 비중 · 색 = 전 거래일 종가 대비 등락률</p></div><div class="kr-heat-legend"><span>−5% 이하</span><i></i><span>+5% 이상</span></div></div>${status}<p class="kr-note">기본은 시총 상위 30종목의 업종별 지도입니다. 작은 업종명은 지도 아래 목록에서도 확인할 수 있습니다. 전체 지도와 시총 순위별 30종목 확대도 선택할 수 있습니다.</p><div class="kr-grid">${['KOSPI','KOSDAQ'].map(heatmapCard).join('')}</div>${supplement}</section>`;
  }
  function reportedHeatmapRows(market) {
    if(!isDate(payload?.heatmaps?.asOf)||payload.heatmaps.asOf>REPORTED_HEATMAP_DATE)return [];
    const reference=new Map(list(payload?.heatmaps?.markets?.[market]?.rows).map(row=>[row.code,row]));
    return list(REPORTED_HEATMAP[market]).flatMap(([code,close,previousClose])=>{
      const row=reference.get(code);
      // Nov 16 filed 6-K: 23,693,272 treasury shares retired on Nov 5, before this market close.
      const shares=code==='000660'?706799093:row?.sharesOutstanding;
      if(!row||!Number.isSafeInteger(shares)||shares<=0||!String(row.sharesSnapshotRetrievedAt||'').startsWith('2026-11-06'))return [];
      return [{code,name:row.name,industry:row.industry,close,changePct:(close/previousClose-1)*100,marketCapKRW:close*shares}];
    }).sort((a,b)=>b.marketCapKRW-a.marketCapKRW);
  }
  function reportedHeatmap() {
    const cards=['KOSPI','KOSDAQ'].map(market=>{
      const rows=reportedHeatmapRows(market),layout=groupedTreemap(rows);
      const tiles=layout.tiles.map((r,i)=>{const text=`${r.name} · ${r.industryName} · 종가 ${integer(r.close)}원 · ${pct(r.changePct)} · 추정 시총 ${integer(r.marketCapKRW/1e8)}억원`;
        return `<button type="button" tabindex="${i===0?0:-1}" class="kr-heat-tile" data-kr-code="${esc(r.code)}" data-kr-heat-detail="${esc(text)}" aria-label="${esc(text)}" style="left:${r.x}%;top:${r.y}%;width:${r.width}%;height:${r.height}%;background:${heatColor(r.changePct)}"><b>${esc(r.name)}</b><span>${pct(r.changePct)}</span></button>`;}).join('');
      const groups=layout.groups.map(g=>`<div class="kr-heat-group" data-kr-industry="${esc(g.id)}" style="left:${g.x}%;top:${g.y}%;width:${g.width}%;height:${g.height}%" aria-hidden="true"><span>${esc(g.name)}</span></div>`).join('');
      const table=rows.map(r=>`<tr><th scope="row">${esc(r.name)}</th><td>${integer(r.close)}</td><td>${pct(r.changePct)}</td><td>${integer(r.marketCapKRW/1e8)}</td></tr>`).join('');
      return `<article class="kr-card kr-heat-card"><div class="kr-card-head"><h4>${market}</h4><span class="kr-badge">${REPORTED_HEATMAP_DATE} · 선별 ${rows.length}종목</span></div><div class="kr-treemap" role="group" aria-label="${market} 선별 종목 시총 히트맵" data-kr-heat-market="${market}" data-kr-heat-layer="sample">${tiles}${groups}</div><div class="kr-heat-detail" aria-live="polite">종목을 누르면 정규장 종가와 등락률이 표시됩니다.</div><details class="kr-metadata"><summary>정규장 종가 · 숫자로 보기</summary><table class="kr-table"><thead><tr><th>종목</th><th>종가(원)</th><th>등락률</th><th>추정 시총(억원)</th></tr></thead><tbody>${table}</tbody></table></details></article>`;
    }).join('');
    return `<p class="kr-note">선별 종목만 표시합니다. 면적은 11/18 종가 × 확인된 상장주식수로 계산한 추정 시총, 색은 전일 종가 대비 등락률입니다. 주식수는 11/6 보관값을 사용하되, SK하이닉스는 소각 후 공시 수를 적용했습니다.</p><div class="kr-grid" data-kr-heat-sample="${REPORTED_HEATMAP_DATE}">${cards}</div><details class="kr-history-disclosure"><summary>11/18 정규장 종가 출처</summary><p class="kr-note"><a href="https://www.newspim.com/news/view/20261118001065" target="_blank" rel="noopener noreferrer">뉴스핌 코스피 마감</a> · <a href="https://markets.hankyung.com/indices/kosdaq" target="_blank" rel="noopener noreferrer">한국경제 코스닥 마감</a> · <a href="https://www.papertrailkr.com/ko/posts/2026-11-18-dip-why-samchundang-pharm-fell-14-6-while/" target="_blank" rel="noopener noreferrer">삼천당제약 등락 확인</a> · <a href="https://snowshagal.com/market/2026-11-18/" target="_blank" rel="noopener noreferrer">11/18 코스피 종가 비교</a> · <a href="https://www.sec.gov/Archives/edgar/data/2120882/000119312526461909/d166755d6k.htm" target="_blank" rel="noopener noreferrer">SK하이닉스 소각 후 주식수(6-K)</a></p></details>`;
  }
  function currentHeatmapsSection() {
    const date=currentDomesticDate(), section=payload?.heatmaps, mapDate=section?.asOf;
    if(hasCapHeatmap(date,section))return heatmapsSection();
    const sample=date===REPORTED_HEATMAP_DATE&&['KOSPI','KOSDAQ'].every(m=>reportedHeatmapRows(m).length===REPORTED_HEATMAP[m].length);
    const archived=isDate(date)&&hasCapHeatmap(mapDate,section)&&mapDate<date;
    const note=`<p class="kr-note" role="note"><strong>${esc(date||'최신 거래일')} 시장 전체 히트맵 미확인.</strong></p>`;
    const external='<p class="kr-note" aria-label="외부 지수 구성종목 히트맵">외부 원본 · 지수 구성종목만: <a href="https://etfshopping.com/treemap" target="_blank" rel="noopener noreferrer">코스피200 ↗</a> · <a href="https://etfshopping.com/treemap/kosdaq-150" target="_blank" rel="noopener noreferrer">코스닥150 ↗</a> <small>외부 페이지의 종가 기준일을 확인하세요.</small></p>';
    if(!sample&&archived)return heatmapsSection('',note+external);
    const archive=archived?`<details class="kr-history-disclosure" id="kr-heat-archive-disclosure"${heatArchiveOpen?' open':''}><summary>${esc(mapDate)} 보관 시장 지도 · 참고용</summary>${heatmapsSection('', '', 'kr-heatmaps-archive')}</details>`:'';
    return `<section class="kr-section kr-heatmaps" id="kr-heatmaps" aria-labelledby="kr-heatmaps-title"><div class="kr-section-head"><div><h3 id="kr-heatmaps-title">KOSPI · KOSDAQ 히트맵</h3>${sample?`<p>${esc(date)} 정규장 마감 · 코스피·코스닥 각 6종목</p>`:''}</div>${sample?'<div class="kr-heat-legend"><span>−5% 이하</span><i></i><span>+5% 이상</span></div>':''}</div>${note}${sample?reportedHeatmap():''}${external}${archive}</section>`;
  }
  function currentSectorReturnsSection() {
    const entry=latestBrief(), section=payload?.sectorReturns||entry?.sectors, today=currentDomesticDate();
    const date=section?.asOf||(!payload?.sectorReturns?entry?.date:null);
    if(!isDate(today)||!isDate(date)||date===today)return sectorReturnsSection();
    return `<section class="kr-section" aria-label="당일 업종별 수익률"><div class="kr-section-head"><div><h3>업종별 수익률</h3><p>${esc(today)} 기준 1일·1주·1개월 비교표는 확인되지 않았습니다.</p></div></div><details class="kr-history-disclosure"><summary>이전 ${esc(date)} 기준 업종별 수익률 · 참고용</summary>${sectorReturnsSection()}</details></section>`;
  }
  function heatLabelSize(width,height) {
    return {font:Math.max(8,Math.min(18,Math.floor(Math.min(width/5,height/4)))),tiny:width<18||height<16,short:height<32};
  }
  function layoutHeatmap(map) {
    const width=map.clientWidth,height=map.clientHeight;if(!width||!height)return;
    const rows=map.dataset.krHeatLayer==='sample'?reportedHeatmapRows(map.dataset.krHeatMarket):heatmapView(map.dataset.krHeatMarket).rows;
    const layout=groupedTreemap(rows,width/height),groups=new Map(layout.groups.map(group=>[group.id,group])),byCode=new Map(layout.tiles.map(row=>[row.code,row]));
    map.querySelectorAll('[data-kr-industry]').forEach(element=>{const group=groups.get(element.dataset.krIndustry);if(!group)return;Object.assign(element.style,{left:group.x+'%',top:group.y+'%',width:group.width+'%',height:group.height+'%'});element.classList.toggle('compact',group.width*width/100<55||group.height*height/100<44);});
    map.querySelectorAll('[data-kr-code]').forEach(tile=>{const row=byCode.get(tile.dataset.krCode);if(!row)return;const group=groups.get(row.industryId),groupLabel=group.width*width/100>=55&&group.height*height/100>=44,header=groupLabel&&Math.abs(row.y-group.y)<.00001?18:0,size=heatLabelSize(row.width*width/100,row.height*height/100-header);Object.assign(tile.style,{left:row.x+'%',top:row.y+'%',width:row.width+'%',height:row.height+'%',fontSize:size.font+'px',paddingTop:header+'px'});tile.classList.toggle('tiny',size.tiny);tile.classList.toggle('short',size.short);});
  }
  function bindHeatmaps() {
    const archive=document.querySelector?.('#kr-heat-archive-disclosure');
    if(archive)archive.ontoggle=()=>{heatArchiveOpen=archive.open;if(archive.open)archive.querySelectorAll('[data-kr-heat-market]').forEach(layoutHeatmap);};
    heatObserver?.disconnect();heatObserver=typeof ResizeObserver==='function'?new ResizeObserver(entries=>entries.forEach(entry=>layoutHeatmap(entry.target))):null;
    document.querySelectorAll('[data-kr-heat-market]').forEach(map=>{layoutHeatmap(map);heatObserver?.observe(map);});
    document.querySelectorAll('[data-kr-heat-scope]').forEach(select=>select.onchange=()=>{heatState[select.dataset.krHeatScope].scope=select.value;render();});
    document.querySelectorAll('[data-kr-heat-expand]').forEach(button=>button.onclick=()=>{const state=heatState[button.dataset.krHeatExpand];state.expanded=!state.expanded;render();});
    document.querySelectorAll('[data-kr-heat-detail]').forEach(tile=>{const show=()=>{const detail=tile.closest('.kr-card')?.querySelector('.kr-heat-detail');if(detail)detail.textContent=tile.dataset.krHeatDetail;};tile.onpointerenter=show;tile.onfocus=show;tile.onclick=show;tile.onkeydown=event=>{if(!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown','Home','End'].includes(event.key))return;event.preventDefault();const peers=[...tile.parentElement.querySelectorAll('[data-kr-heat-detail]')],index=peers.indexOf(tile),next=event.key==='Home'?0:event.key==='End'?peers.length-1:Math.max(0,Math.min(peers.length-1,index+(['ArrowLeft','ArrowUp'].includes(event.key)?-1:1)));tile.tabIndex=-1;peers[next].tabIndex=0;peers[next].focus({preventScroll:true});};});
  }
  function flowTotals(rows,range) {
    const selected=rangeRows(rows,range,true),expected=FLOW_SESSIONS[range]||21;
    return {rows:selected,expected,start:selected[0]?.date,end:selected.at(-1)?.date,totals:['foreign','institution'].map(key=>{const values=selected.map(row=>row[key]).filter(finite),complete=selected.length===expected&&values.length===selected.length;return {key,count:values.length,complete,value:values.length?values.reduce((sum,value)=>sum+value,0):null};})};
  }
  function flowTotalsSummary(market,rows,range) {
    const model=flowTotals(rows,range),partial=model.totals.some(total=>!total.complete);
    return `<div class="kr-flow-totals" data-kr-flow-totals="${market}"><div class="kr-flow-total-heading"><strong>선택 기간 누적 순매수</strong><span>${model.start?esc(model.start+' → '+model.end)+' · '+model.rows.length+'개 거래일 관측':'확인된 관측 없음'}</span></div><div class="kr-flow-total-grid">${model.totals.map(total=>`<div><small>${NAMES[total.key]}${finite(total.value)&&!total.complete?' · 확인분 부분합':''}</small><strong class="${finite(total.value)?rounded(total.value)>0?'up':rounded(total.value)<0?'down':'':'muted'}">${finite(total.value)?signedInteger(total.value)+'<em>억원</em>':'미확인'}</strong><span>${total.count}/${model.expected}개 관측 확인</span></div>`).join('')}</div>${partial?'<p>미확인 관측이 있어 전체 기간의 확정 합계가 아닙니다. 확인된 값만 더했으며 미확인을 0으로 채우지 않았습니다.</p>':'<p>아래 차트·일별 표와 같은 관측의 합계입니다. 양수는 순매수, 음수는 순매도입니다.</p>'}</div>`;
  }
  // Original five-session comparison; dated 15:40 observations, not an official final history.
  const NEAR_CLOSE_FLOW = Object.freeze({
    dates: ['2026-11-12','2026-11-13','2026-11-16','2026-11-17','2026-11-18'],
    markets: {KOSPI:[[3705,-6910],[-5475,22],[-13771,-4647],[-14430,5435],[-3274,5117]],KOSDAQ:[[-3534,437],[-751,1262],[-2122,-1542],[-896,-249],[-449,1766]]},
    sourceFiles: ['2026111216223630K_02_02','2026111316113363K_02_01','2026111616305082K_02_02','2026111715441649K_02_04','2026111816124993K_02_03']
  });
  function nearCloseFlowSection() {
    const dat=NEAR_CLOSE_FLOW, date=currentDomesticDate();
    if(date!==dat.dates.at(-1))return '';
    const groups=['KOSPI','KOSDAQ'].map(market=>{
      let foreign=0,institution=0;
      const cumul=dat.markets[market].map(([f,i],ix)=>({date:dat.dates[ix],foreign:foreign+=f,institution:institution+=i}));
      const tile=(key,value)=>'<div><small>'+NAMES[key]+'</small><strong class="'+(value>0?'up':value<0?'down':'muted')+'">'+signedInteger(value)+'<em>억원</em></strong></div>';
      return '<article class="kr-card"><div class="kr-card-head"><h4>'+market+'</h4><span class="kr-badge">5거래일 누적</span></div><div class="kr-card-body"><div class="kr-flow-totals"><div class="kr-flow-total-heading"><strong>5거래일 누적 순매수</strong></div><div class="kr-flow-total-grid">'+tile('foreign',foreign)+tile('institution',institution)+'</div></div>'+chart('flow-near-'+market,cumul,['foreign','institution'],'3Y',market+' 11월 12~18일 누적 순매수 · 15:40 잠정',true,{tableOpen:true,isolatedPoints:['foreign','institution']})+'</div></article>';
    }).join('');
    const src=dat.sourceFiles.map((file,index)=>'<a href="https://www.samsungpop.com/common.do?cmd=down&amp;contentType=application%2Fpdf&amp;fileName=4020%2F'+file+'.pdf&amp;inlineYn=Y&amp;saveKey=research.pdf" target="_blank" rel="noopener noreferrer">'+dat.dates[index]+' 관측 ↗</a>').join(' · ');
    return '<section class="kr-section" id="kr-flow-near-close" aria-labelledby="kr-flow-near-title"><div class="kr-section-head"><div><h3 id="kr-flow-near-title">투자자별 누적 순매수</h3><p>11/12–11/18 · 매일 15:40 KST KRX 관측 · 잠정 · 억원</p></div></div><div class="kr-grid">'+groups+'</div><p class="kr-note">외국인·기관 현물 순매수만 5거래일 합산했습니다. 15:40 스냅샷 기준으로, 최종 확정 합계가 아니며, 아래 보관 차트와 연결하지 않았습니다.</p><details class="kr-metadata"><summary>관측 출처 · 확인 범위</summary><p>삼성증권의 각 거래일 15:40 KRX 집계에서 두 시장의 현물 순매수만 골라 계산했습니다. 집계 시각이 다른 위의 당일 잠정 수치와는 차이가 날 수 있습니다.</p>'+src+'</details></section>';
  }
  function flowSection() {
    const latest=nearCloseFlowSection();
    const dates=['KOSPI','KOSDAQ'].map(m=>list(payload.flows?.markets?.[m]?.rows).at(-1)?.date||'미확인');
    return `<section class="kr-section" aria-labelledby="kr-flows-title"><div class="kr-section-head"><div><h3 id="kr-flows-title">투자자별 일별 순매수</h3><p><strong>추이 마지막 관측일: ${dates[0]===dates[1]?esc(dates[0]):`KOSPI ${esc(dates[0])} · KOSDAQ ${esc(dates[1])}`}</strong> · 당일 잠정 수급 미포함</p><p>외국인·기관만 표시 · 양수 순매수 / 음수 순매도 · 억원 · 최근 ${FLOW_SESSIONS[flowRange]}개 거래일 관측 (1주 5 · 1개월 21 · 3개월 63 · 6개월 126 · 1년 252)</p></div>${ranges('flow',flowRange)}</div><div class="kr-grid">${['KOSPI','KOSDAQ'].map(market=>{const section=payload.flows?.markets?.[market]||{};return `<article class="kr-card"><div class="kr-card-head"><h4>${market}</h4><span class="kr-badge">일별 · 억원</span></div><div class="kr-card-body">${flowTotalsSummary(market,section.rows,flowRange)}${chart('flow-'+market,section.rows,['foreign','institution'],flowRange,market+' 투자자별 순매수')}</div>${meta(section)}</article>`;}).join('')}</div>${latest?`<details class="kr-history-disclosure" id="kr-flow-provisional"><summary>${esc(currentDomesticDate())}까지 5거래일 잠정 수급 · 별도 참고</summary>${latest}</details>`:''}</section>`;
  }
  function futuresFlowSummary(section, range) {
    const rows=rangeRows(section.rows,range,true),expected=FLOW_SESSIONS[range]||21,known=rows.filter(row=>finite(row.foreign));
    const flagged=rows.filter(row=>row.sourceBalanceWarning),qualityWarning=flagged.length?`<div class="kr-warn">선택 구간 중 ${flagged.length}일 원자료 집계 주의: ${flagged.map(row=>esc(row.date)).join(', ')}. 전체 투자자 순매수 합계가 0과 달라 원인을 확정하지 못했습니다. 외국인 값은 공급사 보고값 그대로이며 누적값 해석에 주의하세요.</div>`:'';
    const total=known.length?known.reduce((sum,row)=>sum+row.foreign,0):null,complete=known.length===expected&&rows.length===expected,unit=section.unit||'계약';
    const metric=(label,value,note)=>`<div><small>${esc(label)}</small><strong class="${finite(value)?rounded(value)>0?'up':rounded(value)<0?'down':'':'muted'}">${finite(value)?signedInteger(value)+'<em>'+esc(unit)+'</em>':'미확인'}</strong><span>${esc(note)}</span></div>`;
    return `<div class="kr-flow-totals" data-kr-futures-totals><div class="kr-flow-total-heading"><strong>선택 기간 누적 순매수</strong><span>${rows.length?esc(rows[0].date+' → '+rows.at(-1).date)+' · '+rows.length+'개 거래일 관측':'확인된 관측 없음'}</span></div><div class="kr-flow-total-grid">${metric(complete?'외국인':'외국인 · 확인분 부분합',total,known.length+'/'+expected+'개 관측 확인')}</div><p>${complete?'아래 일별 값의 합계입니다.':'미확인 관측을 0으로 채우지 않습니다. 전체 요청 기간의 확정 합계가 아닙니다.'} 순매수는 매수−매도이며, 외국인의 보유 잔고나 미결제약정이 아닙니다.</p>${qualityWarning}</div>`;
  }
  function futuresSection() {
    const section=payload?.futures;if(!section)return '';
    const flow=section.foreignFlows||{},scope=part=>[part.product,part.contractScope,part.sessionScope].filter(Boolean).join(' · ');
    return `<section class="kr-section" id="kr-futures" aria-labelledby="kr-futures-title"><div class="kr-section-head"><div><h3 id="kr-futures-title">KOSPI 200 선물 · 외국인 수급</h3><p>최근 ${FLOW_SESSIONS[futuresRange]}개 거래일 관측 · 1주 5 / 1개월 21 / 3개월 63 / 6개월 126 / 1년 252 · 실제 확인 날짜 표시</p></div>${ranges('futures',futuresRange)}</div><article class="kr-card"><div class="kr-card-head"><h4>외국인 일별 순매수 · NAVER 집계</h4><span class="kr-badge">${esc(flow.unit||'계약')}</span></div><div class="kr-card-body"><p class="kr-note">${esc(scope(flow))}${list(flow.scopeUnconfirmed).length?'<br>포함 범위 미확인: '+esc(flow.scopeUnconfirmed.join(' / ')):''}</p>${list(flow.rows).length?futuresFlowSummary(flow,futuresRange)+chart('futures-foreign',flow.rows,['foreign'],futuresRange,'KOSPI 200 선물 외국인 일별 순매수',true,{unit:flow.unit||'계약',tradingSessions:true}):empty(flow.note)}</div>${meta(flow)}</article></section>`;
  }
  function rankingTable(section, limit, valueLabel) {
    const rows=list(rankMarket==='ALL'?section?.rows:section?.byMarket?.[rankMarket]).slice(0,limit);
    if(!rows.length)return empty(section?.note||'이 날짜의 전체시장 순위 자료를 확보하지 못했습니다.');
    return `<div class="kr-table-wrap" tabindex="0" role="region" aria-label="${esc(valueLabel)} 순위표"><table class="kr-table"><caption>${esc(rankMarket==='ALL'?(section?.coverage?.universe||'KOSPI + KOSDAQ'):rankMarket+' · 해당 시장 내 순위')} · ${esc(valueLabel)} · 억원${section?.status==='partial'?' · 부분 자료':''}</caption><thead><tr><th scope="col">순위</th><th scope="col">종목</th><th scope="col">시장</th><th scope="col">${esc(valueLabel)}</th></tr></thead><tbody>${rows.map((row,i)=>`<tr><td>${i+1}</td><td>${esc(row.name)}<small>${esc(row.code)}</small></td><td>${esc(row.market||'미확인')}</td><td>${valueLabel==='거래대금'?`<span class="kr-value">${integer(row.value)}</span>`:signed(row.value)}</td></tr>`).join('')}</tbody></table></div>`;
  }
  function selectedSection(group) {return selected==='1m'?payload[group]?.monthly:selected==='5d'?payload[group]?.aggregate5d:payload[group]?.daily?.[selected];}
  // Resolve each daily panel independently: a newer empty release must not hide a verified snapshot.
  // Keep the actual source date and object unchanged; never backfill data under the requested date.
  function latestDailySnapshot(group, key, requestedDate) {
    const usable=section=>section?.status!=='unavailable'&&list(section?.rows).some(row=>group==='themes'
      ? ['foreign','institution'].some(investor=>finite(row[investor])||(row.coverage?.[investor]?.availableCount>0&&finite(row.coverage[investor].knownSubtotalEok)))
      : finite(row.value));
    const candidates=Object.entries(payload?.[group]?.daily||{}).filter(([date])=>isDate(date)&&(!isDate(requestedDate)||date<=requestedDate))
      .map(([date,entry])=>({date,section:key?entry?.[key]:entry})).filter(({date,section})=>usable(section)&&section.coverage?.end===date);
    return candidates.sort((a,b)=>b.date.localeCompare(a.date))[0]||{date:null,section:null};
  }
  function turnoverScope(section) {
    if(!list(section?.rows).length)return '';
    const regular=section.coverage?.regularSessionOnlyVerified===true,after=section.coverage?.sourceTradeSession==='AFTER_MARKET'||/애프터마켓.*마감|애프터마켓.*종료/.test(section.note||'');
    return `<p class="kr-note" data-kr-turnover-scope>공급사 거래대금 스냅샷${after?' · 애프터마켓 종료 후 조회 (AFTER_MARKET)':''} · ${regular?'정규장 단독 집계 확인':'정규장 단독 집계 여부 미확인'}</p>`;
  }
  function delayedSnapshotNote(snapshot, requestedDate, label) {
    return snapshot.date&&isDate(requestedDate)&&snapshot.date<requestedDate
      ? `<p class="kr-warn" data-kr-delayed-snapshot>${esc(requestedDate)} ${esc(label)} 미확보 · 최근 확인된 ${esc(snapshot.date)} 자료를 표시합니다. 오늘 자료가 아닙니다.</p>`:'';
  }
  function selectionLabel() {const period=selected==='1m'?payload.rankings?.monthly:payload.rankings?.aggregate5d, start=period?.start||period?.startDate||period?.foreign?.coverage?.start, end=period?.end||period?.endDate||period?.foreign?.coverage?.end;return ['1m','5d'].includes(selected)?`${selected==='1m'?'월간':'최근 5거래일'} 합계 (${start||list(payload.rankings?.dates).slice().sort()[0]||'?'} ~ ${end||list(payload.rankings?.dates).slice().sort().at(-1)||'?'})`:selected||'날짜 미확인';}
  function themeCell(row, investor, max) {
    const cell=row.coverage?.[investor]||{}, total=row[investor], count=cell.availableCount??0, expected=cell.expectedCount??row.memberCount;
    if(finite(total)&&cell.status==='complete')return `<span class="kr-theme-bar ${total>0?'up':total<0?'down':''}"><i style="width:${Math.abs(total)/max*100}%"></i>${signed(total)}</span><small>전체 합계 · ${esc(count)}/${esc(expected)}개</small>`;
    const subtotal=cell.knownSubtotalEok;
    return `${finite(subtotal)&&count>0?`<span class="kr-theme-partial"><span class="kr-partial-label">부분합</span> ${signed(subtotal)}</span>`:'<span class="muted">미확인</span>'}<small>${esc(count)}/${esc(expected)}개 확인${finite(subtotal)&&count>0?' · 전체 합계 미확인':''}</small>`;
  }
  function themeLabel(row) {
    const capDate=row.marketCapAsOf||payload.themes?.marketCapAsOf;
    const groups=['KOSPI','KOSDAQ'].map(market=>{const candidates=list(row.members).filter(m=>m.market===market&&finite(m.marketCapKRW)).sort((a,b)=>b.marketCapKRW-a.marketCapKRW||String(a.code).localeCompare(String(b.code))),members=list(row.displayMembersByMarket?.[market]||candidates).slice(0,3);return `<small class="kr-theme-members" title="${esc(market+' 구성종목 시총 상위 최대 3개 · '+(capDate||'기준일 미확인'))}"><b>${market}</b> (${members.length?members.map(m=>esc(m.name)).join(' / '):'해당 구성종목 없음'})</small>`;}).join('');
    return `${esc(row.name)}${groups}`;
  }
  function themesSection() {
    const daily=!['5d','1m'].includes(selected),snapshot=daily?latestDailySnapshot('themes',null,selected):null,section=(daily?snapshot.section:selectedSection('themes'))||{note:selectedSection('themes')?.note}, rows=list(section.rows).map(row=>({...list(payload.themes?.baskets).find(b=>b.id===row.id),...row})), max=Math.max(1,...rows.flatMap(r=>[r.foreign,r.institution]).filter(finite).map(Math.abs));
    const membershipDate=section.membershipAsOf||payload.themes?.membershipAsOf, capDate=section.marketCapAsOf||payload.themes?.marketCapAsOf, capPolicy=section.marketCapPolicy||payload.themes?.marketCapPolicy;
    return `<article class="kr-card"><div class="kr-card-head"><h4>테마별 수급</h4><span class="kr-badge">${esc(section.coverage?.start||'')}${section.coverage?.end&&section.coverage.end!==section.coverage.start?' ~ '+esc(section.coverage.end):''} · 억원</span></div><div class="kr-card-body">${daily?delayedSnapshotNote(snapshot,selected,'테마 순매수금액'):''}<p class="kr-note">${esc(payload.themes?.methodology||'업종과 테마의 분류·구성 종목·집계 범위는 아래 확인 범위를 참고하세요.')}</p>${section.coverage?.note?`<p class="kr-note">확인 범위: ${esc(section.coverage.note)}</p>`:''}${rows.length?`<p class="kr-theme-key">괄호: KOSPI·KOSDAQ 각각 시총 상위 최대 3개${capDate?' · 시총 '+esc(capDate):''}${membershipDate?' · 구성 '+esc(membershipDate):''}</p>${capPolicy?`<p class="kr-note">시총 기준: ${esc(capPolicy)}</p>`:''}<p class="kr-note">부분합은 확인된 종목만의 금액입니다. 누락 종목에 따라 방향·크기가 달라질 수 있어 테마 순위를 매기지 않습니다. 테마 간 중복 편입이 있으므로 서로 합산할 수 없습니다.</p><div class="kr-table-wrap" tabindex="0" role="region" aria-label="업종 테마별 순매수 표"><table class="kr-table kr-theme-table"><thead><tr><th scope="col">업종 / 테마 (시장별 시총 상위 3종목)</th><th scope="col">외국인</th><th scope="col">기관</th><th scope="col">전체 구성</th></tr></thead><tbody>${rows.map(row=>`<tr><th scope="row">${themeLabel(row)}</th><td>${themeCell(row,'foreign',max)}</td><td>${themeCell(row,'institution',max)}</td><td><span class="kr-theme-count">${esc(row.memberCount??'?')}종목</span></td></tr>`).join('')}</tbody></table></div>`:empty(section.note||payload.themes?.note)}</div>${meta(section,'테마 중복 편입 가능')}${rows.length?`<details class="kr-metadata kr-theme-definitions"><summary>테마 전체 구성·NAVER 분류 기준 보기</summary><p>대기업의 관련 사업 노출도 포함됩니다. 로봇·휴머노이드에는 공급사 분류에 따라 삼성전자·현대차·기아 등이 포함됩니다. 시장별 시총 상위 최대 3개는 별도 검증일의 고정 스냅샷이며 수급 갱신일과 다를 수 있습니다.</p>${rows.map(row=>`<details><summary>${esc(row.name)} · ${esc(row.memberCount)}종목</summary><p>${esc(row.scopeNote||'분류 기준 미확인')}</p><p>${sourceLinks(list(row.sourceCategories).map(s=>s.id))}</p><p>${list(row.members).map(m=>esc(m.name)+' ('+esc(m.code)+')').join(' · ')}</p></details>`).join('')}</details>`:''}</article>`;
  }
  function currentThemesSection() {
    const date=currentDomesticDate(), daily=!['5d','1m'].includes(selected);
    const end=daily?latestDailySnapshot('themes',null,date).date:selectedSection('themes')?.coverage?.end;
    if(isDate(date)&&end===date&&(!daily||selected===date))return themesSection();
    return `<article class="kr-card"><div class="kr-card-head"><h4>테마별 수급</h4></div><p class="kr-note">${esc(date||'최신 거래일')} 기준 테마 수급을 확인하지 못했습니다. 이전 거래일의 집계는 당일에 표시하지 않습니다.</p></article>`;
  }
  function rankingsSection() {
    const data=selectedSection('rankings')||{}, dates=list(payload.rankings?.dates).filter(isDate).slice().sort().reverse(), turnoverSnapshot=latestDailySnapshot('rankings','tradedValue',dates[0]),turnover=turnoverSnapshot.section||{note:payload.rankings?.daily?.[dates[0]]?.tradedValue?.note};
    return `<section class="kr-section" aria-labelledby="kr-rankings-title"><div class="kr-section-head"><div><h3 id="kr-rankings-title">업종 · 종목 수급</h3><p>${esc(selectionLabel())} · 각 표의 실제 집계일을 확인하세요. 테마 수급·거래대금은 종목 순매수와 기준일이 다를 수 있습니다.</p></div><div class="kr-controls" role="group" aria-label="수급 집계 기간">${[['day','1일'],['5d','주간'],['1m','월간']].map(([key,label])=>`<button type="button" data-kr-period="${key}" aria-pressed="${key==='day'?!['5d','1m'].includes(selected):selected===key}">${label}</button>`).join('')}</div></div>${payload.rankings?.note?`<p class="kr-note">${esc(payload.rankings.note)}</p>`:''}${currentThemesSection()}<div class="kr-section-head" style="margin-top:18px"><span class="kr-note">종목 순위 시장</span><div class="kr-controls" role="group" aria-label="종목 순위 시장">${[['ALL','통합'],['KOSPI','KOSPI'],['KOSDAQ','KOSDAQ']].map(([key,label])=>`<button type="button" data-kr-rank-market="${key}" aria-pressed="${rankMarket===key}">${label}</button>`).join('')}</div></div><div class="kr-grid" style="margin-top:14px">${['foreign','institution'].map(key=>`<article class="kr-card"><div class="kr-card-head"><h4>${NAMES[key]} 순매수 상위 15</h4><span class="kr-badge">${esc(selected==='1m'?'1개월 합계':selected==='5d'?'5일 합계':selected)}</span></div>${rankingTable(data[key],15,'순매수')}${meta(data[key])}</article>`).join('')}</div><article class="kr-card" style="margin-top:14px"><div class="kr-card-head"><h4>거래대금 상위 20</h4><span class="kr-badge">${esc(turnoverSnapshot.date||dates[0]||'미확인')} · ${turnoverSnapshot.date?'최신 확인 자료':'자료 미확보'}</span></div>${delayedSnapshotNote(turnoverSnapshot,dates[0],'거래대금 순위')}${turnoverScope(turnoverSnapshot.section)}${rankingTable(turnover,20,'거래대금')}${meta(turnover)}</article></section>`;
  }
  function currentRankingsSection() {
    const date=currentDomesticDate(), requested=selectedSection('rankings');
    const current=isDate(date)&&['foreign','institution','tradedValue'].every(k=>requested?.[k]?.coverage?.end===date&&list(requested[k].rows).length);
    if(current)return rankingsSection();
    const links=date==='2026-11-18'?'<p class="kr-note">연합뉴스 · KRX 2026-11-18 15:30 KST 원문: <a href="https://www.yna.co.kr/view/AKR20261118138900008" target="_blank" rel="noopener noreferrer">KOSPI 외국인 ↗</a> · <a href="https://www.yna.co.kr/view/AKR20261118138600008" target="_blank" rel="noopener noreferrer">KOSPI 기관 ↗</a> · <a href="https://www.yna.co.kr/view/AKR20261118138800008" target="_blank" rel="noopener noreferrer">KOSDAQ 외국인 ↗</a> · <a href="https://www.yna.co.kr/view/AKR20261118138700008" target="_blank" rel="noopener noreferrer">KOSDAQ 기관 ↗</a></p>':'';
    return `<section class="kr-section" aria-labelledby="kr-rankings-title"><div class="kr-section-head"><div><h3 id="kr-rankings-title">업종 · 종목 수급</h3><p>${esc(date||'최신 거래일')} 기준 종목 순위를 확인하지 못했습니다.</p></div></div>${currentThemesSection()}<p class="kr-note">외국인 순매수 상위 15 · 기관 순매수 상위 15 · 종목별 거래대금 상위 20: 이전 거래일 순위를 당일에 표시하지 않습니다.</p>${links}</section>`;
  }
  function currentMoversSection() {
    const date=currentDomesticDate(), source=moversPeriod==='week'?payload?.indexMovers?.aggregate5d:moversPeriod==='month'?payload?.indexMovers?.monthly:payload?.indexMovers?.daily?.[date];
    const part=source?.[selectedIndex], end=part?.comparisonEnd||part?.coverage?.end||part?.coverage?.priceAsOf;
    if(isDate(date)&&end===date&&(list(part.gainers).length||list(part.losers).length))return moversSection(date);
    return `<section class="kr-section" aria-labelledby="kr-movers-title"><div class="kr-section-head"><div><h3 id="kr-movers-title">지수 구성종목 상승률 · 하락률</h3><p>${esc(date||'최신 거래일')} 기준 구성종목 등락률 순위는 확인되지 않았습니다.</p></div></div></section>`;
  }
  function currentHighsSection() {
    const entry=latestBrief(),date=currentDomesticDate(), screening=payload?.highsScreen||entry?.highs;
    const asOf=screening?.asOf||(!payload?.highsScreen&&screening?entry?.date:null);
    if(isDate(date)&&asOf===date)return highsSection();
    return `<section class="kr-section" id="kr-highs" aria-labelledby="kr-highs-title"><div class="kr-section-head"><div><h3 id="kr-highs-title">52주 신고가 · 고가 근접 기업</h3><p>${esc(date||'최신 거래일')} 기준 전체 선별 목록은 확인되지 않았습니다.</p></div></div>${standaloneCloseBreakout(entry)}</section>`;
  }
  function moversSection(dayOverride) {
    const requestedDay=dayOverride||(['5d','1m'].includes(selected)?list(payload.rankings?.dates).slice().sort().at(-1):selected);
    const day=payload.indexMovers?.daily?.[requestedDay]?requestedDay:Object.keys(payload.indexMovers?.daily||{}).sort().at(-1);
    const section=(moversPeriod==='month'?payload.indexMovers?.monthly:moversPeriod==='week'?payload.indexMovers?.aggregate5d:payload.indexMovers?.daily?.[day])?.[selectedIndex]||{}, universeTitle=selectedIndex+(section.coverage?.universeType==='etf-proxy'?' 추종ETF 구성종목':''), periodLabel={day:'일별 등락률',week:'5거래일 수익률',month:'1개월 수익률'}[moversPeriod], pct=value=>finite(value)?`<span class="kr-value ${value>0?'up':value<0?'down':''}">${value>0?'+':''}${fmt(value,2)}%</span>`:'<span class="muted">미확인</span>';
    const table=(key,label)=>{const rows=list(section[key]).slice(0,10);return `<article class="kr-card"><div class="kr-card-head"><h4>${universeTitle} ${label} 상위 10</h4><span class="kr-badge">${periodLabel}</span></div>${rows.length?`<div class="kr-table-wrap" tabindex="0" role="region" aria-label="${selectedIndex} ${label} 순위표"><table class="kr-table"><caption>${esc(section.coverage?.universe||selectedIndex+' 확인된 구성종목')} · %</caption><thead><tr><th scope="col">순위</th><th scope="col">종목</th><th scope="col">${periodLabel}</th></tr></thead><tbody>${rows.map((row,i)=>`<tr><td>${i+1}</td><td>${esc(row.name)}<small>${esc(row.code)}</small></td><td>${pct(row.changePct)}</td></tr>`).join('')}</tbody></table></div>`:empty(section.note||'이 날짜의 지수 구성종목별 수익률을 확보하지 못했습니다.')}</article>`;};
    return `<section class="kr-section" aria-labelledby="kr-movers-title"><div class="kr-section-head"><div><h3 id="kr-movers-title">지수 구성종목 상승률 · 하락률</h3><p>${esc(section.comparisonStart&&section.comparisonEnd?section.comparisonStart+' → '+section.comparisonEnd:day||'기준일 미확인')} · 1일은 확인된 날짜만 연동 · 주간·월간은 지수 분석의 최신 확인일 기준</p></div><div class="kr-controls" role="group" aria-label="등락률 지수 선택">${['KOSPI200','KOSDAQ150'].map(key=>`<button type="button" data-kr-index="${key}" aria-pressed="${selectedIndex===key}">${key==='KOSPI200'?'KOSPI 200':'KOSDAQ 150'}</button>`).join('')}</div><div class="kr-controls" role="group" aria-label="등락률 기간 선택">${[['day','1일'],['week','주간'],['month','월간']].map(([key,label])=>`<button type="button" data-kr-movers-period="${key}" aria-pressed="${moversPeriod===key}">${label}</button>`).join('')}</div></div>${section.coverage?.universeType==='etf-proxy'?'<p class="kr-warn">운용사 추종 ETF의 공개 구성종목 기준입니다. 공식 지수의 과거 시점 구성종목 전수 순위와 다를 수 있습니다.</p>':''}${section.scopeLabel?`<p class="${section.status==='partial'?'kr-warn':'kr-note'}">${esc(section.scopeLabel)}${list(section.missingConstituents).length?' · 미확인: '+list(section.missingConstituents).map(row=>esc(row.name+' ('+row.code+')')).join(', '):''}</p>`:''}${payload.indexMovers?.note?`<p class="kr-note">${esc(payload.indexMovers.note)}</p>`:''}<div class="kr-grid">${table('gainers','상승률')}${table('losers','하락률')}</div>${meta(section,selectedIndex)}</section>`;
  }
  // Official FreeSIS headline values in million KRW; independent of the per-market series.
  function officialLiquiditySummary() {
    const verified={date:'2026-11-17', officialInvestorDeposits:86622814, officialMarginLoans:26333855};
    const released=payload?.liquidity?.validationSummary?.latestOfficialRelease;
    const latest=isDate(released?.date)&&released.date>verified.date&&released.unit==='million KRW'&&['officialInvestorDeposits','officialMarginLoans'].every(k=>Number.isSafeInteger(released[k])&&released[k]>0)?released:verified;
    if(!isDate(currentDomesticDate())||latest.date>currentDomesticDate())return '';
    return `<div class="kr-card" data-kr-official-liquidity="${latest.date}"><div class="kr-card-head"><h4>금융투자협회 공식 전체 잔고</h4><span class="kr-badge">${latest.date} 기준</span></div><div class="kr-table-wrap" tabindex="0"><table class="kr-table"><caption>시장 전체 · 억원 · 아래 시장별 시계열과 별도</caption><tbody><tr><th scope="row">투자자예탁금</th><td>${integer(latest.officialInvestorDeposits/100)}</td></tr><tr><th scope="row">신용거래융자</th><td>${integer(latest.officialMarginLoans/100)}</td></tr></tbody></table></div><details class="kr-history-disclosure"><summary>공표 기준과 근거</summary><p class="kr-note">공식 합계는 시장별 잔고에 나눠 넣지 않았습니다. <a href="https://freesis.kofia.or.kr/stat/main.do" target="_blank" rel="noopener noreferrer">금융투자협회 FreeSIS</a></p></details></div>`;
  }
  function liquiditySection() {
    const series=payload.liquidity?.series||{};
    return `<section class="kr-section" aria-labelledby="kr-liquidity-title"><div class="kr-section-head"><div><h3 id="kr-liquidity-title">투자자예탁금 · 신용융자 잔고</h3><p>예탁금은 증시 전체 합계 · 신용융자는 KOSPI / KOSDAQ 구분 · 억원</p></div>${ranges('liquidity',liquidityRange)}</div>${officialLiquiditySummary()}<p class="kr-note">이전 검증 시계열 · 아래 각 차트의 기준일 확인</p>${summary()}${payload.liquidity?.note?`<p class="kr-note">${esc(payload.liquidity.note)}</p>`:''}<article class="kr-card"><div class="kr-card-head"><h4>투자자예탁금</h4><span class="kr-badge">시장 전체 · 억원</span></div><div class="kr-card-body">${chart('deposits',list(series.deposits?.rows).map(r=>({date:r.date,deposits:r.value})),['deposits'],liquidityRange,'시장 전체 투자자예탁금',false)}</div>${meta(series.deposits)}</article><div class="kr-grid kr-credit-grid" style="margin-top:14px">${['creditKOSPI','creditKOSDAQ'].map(key=>`<article class="kr-card"><div class="kr-card-head"><h4>${NAMES[key]} 잔고</h4><span class="kr-badge">억원</span></div><div class="kr-card-body">${chart(key,list(series[key]?.rows).map(r=>({date:r.date,[key]:r.value})),[key],liquidityRange,NAMES[key]+' 잔고',false)}</div>${meta(series[key])}</article>`).join('')}</div></section>`;
  }
  function summary() {
    const series=payload.liquidity?.series||{};
    const cards=['deposits','creditKOSPI','creditKOSDAQ'].map(key=>{const section=series[key]||{}, latest=list(section.rows).filter(r=>finite(r.value)).at(-1);return `<article class="kr-summary-card"><small>${NAMES[key]}${key==='deposits'?' · 시장 전체':''}</small><strong>${latest?integer(latest.value)+'억원':'미확인'}</strong><p>${latest?latest.date+' 기준':'검증된 관측값 없음'}</p></article>`;});
    return `<div class="kr-summary kr-balance-summary">${cards.join('')}</div>`;
  }
  // Move existing nodes, preserving every explanation and source link. Data tables stay beside charts.
  function collectExplanations(target, open=false) {
    const notes=Array.from(target.querySelectorAll?.('.kr-metadata:not(.kr-heat-numbers), .kr-source-list, .kr-statusline, .kr-page-footer')||[]);
    if(!notes.length)return;
    const disclosure=document.createElement('details');
    disclosure.id='kr-explanations';disclosure.className='kr-explanations';disclosure.open=open;
    disclosure.innerHTML='<summary><span class="kr-explanations-closed">설명·출처 보기</span><span class="kr-explanations-open">설명·출처 접기</span></summary><div class="kr-explanations-body"></div>';
    const body=disclosure.lastElementChild,groups=new Map();
    notes.forEach(note=>{
      const section=note.closest('.kr-section');
      let group=groups.get(section);
      if(!group){
        group=document.createElement('section');group.className='kr-explanation-group';
        const title=document.createElement('h4');title.textContent=section?.querySelector('h3')?.textContent||'공통 안내·전체 출처';
        group.append(title);body.append(group);groups.set(section,group);
      }
      const cardTitle=note.closest('.kr-card')?.querySelector('h4')?.textContent;
      if(cardTitle&&note.matches('.kr-metadata')){
        const summary=note.querySelector('summary');if(summary)summary.prepend(cardTitle+' · ');
      }
      group.append(note);
    });
    target.append(disclosure);
  }
  function render() {
    const target=el('kr-content');if(!target)return;
    const explanationsOpen=!!target.querySelector?.('#kr-explanations')?.open;
    const active=document.activeElement,focusAttribute=['data-kr-range','data-kr-period','data-kr-index','data-kr-movers-period','data-kr-rank-market','data-kr-sector-sort'].find(key=>active?.hasAttribute?.(key)),focusSelector=focusAttribute?'['+focusAttribute+'="'+active.getAttribute(focusAttribute)+'"]'+(active.dataset?.range?'[data-range="'+active.dataset.range+'"]':''):['kr-date','kr-analysis-date'].includes(active?.id)||active?.id?.startsWith('kr-heat-')?'#'+active.id:null;
    renderMarketHeader();
    if(loading&&!payload){target.innerHTML='<div class="kr-empty kr-loading">국내 시장 데이터를 불러오는 중입니다.</div>';return;}
    if(!payload){target.innerHTML=analysisControls()+closeSection()+unusualMoversSection()+analysisSources()+'<div class="kr-empty" role="alert"><div>국내 수급·자금 데이터 파일을 불러오지 못했습니다. 아래 시황·참고 자료는 각각 표시된 기존 기준일의 자료입니다.<br><button type="button" class="button" id="kr-retry">다시 불러오기</button></div></div>'+sectorReturnsSection()+highsSection()+earningsSection();collectExplanations(target,explanationsOpen);el('kr-retry').onclick=load;bindSectorSorting();bindAnalysisControls();return;}
    charts=new Map();
    const dates=list(payload.rankings?.dates).filter(isDate).slice().sort().reverse();if(!['5d','1m'].includes(selected))selected=dates[0]||'';
    target.innerHTML=(failed?'<div class="kr-warn">새로고침 실패 · 마지막으로 확인한 자료를 표시합니다.</div>':'')+(payload.refresh?.failures?.length?`<div class="kr-warn">일부 데이터 갱신에 실패해 이전 관측값을 보존했습니다. 각 항목의 실제 기준일을 확인하세요.</div>`:'')+analysisControls()+freshnessSection()+currentHeatmapsSection()+closeSection()+marketTurnoverSection()+dailyFlowSummary()+flowSection()+`<p class="kr-statusline">금액·지수·가격은 반올림 표시하며 원자료·계산값의 정밀도는 유지합니다. 일별 자료의 최신 관측일과 공개 시차는 항목별로 다릅니다.${payload.requestedWindow?' 조회 목표: '+esc(payload.requestedWindow.start)+' ~ '+esc(payload.requestedWindow.end)+'.':''}</p>`+futuresSection()+currentSectorReturnsSection()+currentRankingsSection()+currentMoversSection()+currentHighsSection()+unusualMoversSection()+liquiditySection()+earningsSection()+analysisSources()+`<details class="kr-source-list"><summary>전체 출처 · 데이터 제약</summary><ol>${list(payload.sources).map(s=>`<li>${safe(s.url)?`<a href="${esc(safe(s.url))}" target="_blank" rel="noopener noreferrer">${esc(s.title||s.id)} ↗</a>`:esc(s.title||s.id)}${s.note?' · '+esc(s.note):''}</li>`).join('')}</ol><ul>${list(payload.limitations).map(note=>`<li>${esc(note)}</li>`).join('')}</ul><p>수집 시각: ${esc(payload.updatedAt||'미확인')}</p></details><p class="kr-page-footer">공개 자료 기반 개인 연구용 대시보드입니다. 실시간 시세나 투자 권유가 아닙니다. 미확인 값은 0이 아니며, 테마는 서로 중복될 수 있어 합산하면 전체시장과 일치하지 않습니다.</p>`;
    collectExplanations(target,explanationsOpen);
    document.querySelectorAll('[data-kr-range]').forEach(button=>button.onclick=()=>{if(button.dataset.krRange==='flow')flowRange=button.dataset.range;else if(button.dataset.krRange==='futures')futuresRange=button.dataset.range;else liquidityRange=button.dataset.range;render();});
    document.querySelectorAll('[data-kr-period]').forEach(button=>button.onclick=()=>{rankDatePinned=false;selected=button.dataset.krPeriod==='day'?dates[0]||'':button.dataset.krPeriod;render();});
    const dateSelect=el('kr-date');if(dateSelect)dateSelect.onchange=event=>{selected=event.target.value;rankDatePinned=true;render();};
    document.querySelectorAll('[data-kr-index]').forEach(button=>button.onclick=()=>{selectedIndex=button.dataset.krIndex;render();});
    document.querySelectorAll('[data-kr-movers-period]').forEach(button=>button.onclick=()=>{moversPeriod=button.dataset.krMoversPeriod;render();});
    document.querySelectorAll('[data-kr-rank-market]').forEach(button=>button.onclick=()=>{rankMarket=button.dataset.krRankMarket;render();});
    bindAnalysisControls();
    bindSectorSorting();
    bindHeatmaps();
    bindCharts();
    if(focusSelector)document.querySelector?.(focusSelector)?.focus({preventScroll:true});
  }
  function bindSectorSorting() {document.querySelectorAll('[data-kr-sector-sort]').forEach(button=>button.onclick=()=>{if(sectorSort===button.dataset.krSectorSort)sectorDescending=!sectorDescending;else{sectorSort=button.dataset.krSectorSort;sectorDescending=true;}render();});}
  function bindCharts() {
    document.querySelectorAll('[data-kr-chart]').forEach(holder=>{
      const model=charts.get(holder.dataset.krChart), svg=holder.querySelector('svg'), output=holder.querySelector('[data-kr-tooltip]'), cursor=holder.querySelector('[data-kr-cursor]');if(!model||!svg)return;
      let index=model.rows.length-1;
      const show=i=>{index=Math.max(0,Math.min(model.rows.length-1,i));output.innerHTML=tooltip(model,model.rows[index]);cursor.setAttribute('x1',model.x(index));cursor.setAttribute('x2',model.x(index));cursor.setAttribute('visibility','visible');};
      svg.onpointermove=event=>{const rect=svg.getBoundingClientRect(),x=(event.clientX-rect.left)/rect.width*model.width;show(Math.round((x-model.left)/(model.width-model.left-model.right)*(model.rows.length-1)));};
      svg.onpointerleave=()=>cursor.setAttribute('visibility','hidden');
      svg.onkeydown=event=>{if(['ArrowLeft','ArrowRight','Home','End'].includes(event.key)){event.preventDefault();show(event.key==='Home'?0:event.key==='End'?model.rows.length-1:index+(event.key==='ArrowLeft'?-1:1));output.setAttribute('aria-live','polite');}};
    });
  }
  async function load() {
    if(loading)return;loading=true;const hadFailure=failed;failed=false;if(!payload)render();
    let changed=false;
    try {const response=await fetch('./data/korea-market.json?ts='+Date.now(),{cache:'no-store'});if(!response.ok)throw new Error('HTTP '+response.status);const next=await response.json();if(next.schemaVersion!==1||!Array.isArray(next.sources)||!next.flows||!next.liquidity)throw new Error('Unsupported Korean market schema');changed=JSON.stringify(payload)!==JSON.stringify(next);payload=next;lastLoaded=Date.now();}
    catch(error){failed=true;console.error('Korean market data:',error);}
    loading=false;if(changed||failed||hadFailure)render();
  }
  function route(){const parts=window.location.hash.slice(1).split('/');if(parts[0]!=='korea')return;selectedBriefDate='';if(!payload&&!loading)load();else{render();if(Date.now()-lastLoaded>=60000)load();}}
  function refresh(){if(document.visibilityState==='hidden'||window.location.hash.split('/')[0]!=='#korea'||Date.now()-lastLoaded<60000)return;load();}
  function boot(){window.addEventListener('hashchange',route);window.addEventListener('terminal-briefing-ready',()=>{if(!loading&&(payload||failed))render();});window.addEventListener('focus',refresh);document.addEventListener('visibilitychange',refresh);if(typeof window.setInterval==='function')window.setInterval(refresh,300000);route();}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot,{once:true});else boot();
}());
