/* Source-backed Korean market analysis. Unknown values stay null, never zero. */
(function () {
  'use strict';
  const el = id => document.getElementById(id);
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const list = value => Array.isArray(value) ? value : [];
  const finite = value => typeof value === 'number' && Number.isFinite(value);
  const fmt = (value, digits=0) => finite(value) ? value.toLocaleString('ko-KR',{maximumFractionDigits:digits}) : '미확인';
  const signed = value => finite(value) ? `<span class="kr-value ${value>0?'up':value<0?'down':''}">${value>0?'+':''}${fmt(value,1)}</span>` : '<span class="muted">미확인</span>';
  const safe = value => {try {const url=new URL(value);return ['https:','http:'].includes(url.protocol)&&!url.username&&!url.password?url.href:'';} catch (_) {return '';}};
  const isDate = value => typeof value==='string' && /^\d{4}-\d{2}-\d{2}$/.test(value) && Number.isFinite(Date.parse(value)) && new Date(value).toISOString().slice(0,10)===value;
  const COLORS = {foreign:'#f3b971',institution:'#88a9ff',individual:'#5ad3bd',deposits:'#88a9ff',creditKOSPI:'#f3b971',creditKOSDAQ:'#5ad3bd'};
  const NAMES = {foreign:'외국인',institution:'기관',individual:'개인',deposits:'투자자예탁금',creditKOSPI:'KOSPI 신용융자',creditKOSDAQ:'KOSDAQ 신용융자'};
  let payload=null, loading=false, failed=false, flowRange='3Y', liquidityRange='3Y', selected='', selectedIndex='KOSPI200', moversPeriod='day', rankMarket='ALL', sectorSort='day', sectorDescending=true;
  let charts = new Map();
  function empty(message) {return `<div class="kr-empty">${esc(message||'검증된 자료를 아직 확보하지 못했습니다. 미확인은 0 또는 해당 없음이 아닙니다.')}</div>`;}
  function sourceLinks(ids) {return list(ids).map(id=>list(payload?.sources).find(s=>s.id===id)).filter(Boolean).map(s=>{const href=safe(s.url);return href?`<a href="${esc(href)}" target="_blank" rel="noopener noreferrer">${esc(s.title||s.id)} ↗</a>`:'';}).join(' ');}
  function meta(section, suffix='') {
    const cov=section?.coverage||{}, rows=list(section?.rows), first=cov.start||rows[0]?.date, last=cov.end||rows.at(-1)?.date;
    const dateLabel=first&&last?`${first} ~ ${last}`:last||first||'기준일 미확인';
    const counts=Number.isInteger(cov.sampleCount)?`${fmt(cov.validCount??cov.sampleCount)}/${fmt(cov.sampleCount)}개 종목 확인`:Number.isInteger(cov.count)?`${fmt(cov.count)}개 관측`:rows.length?`${fmt(rows.length)}개 관측`:'';
    return `<details class="kr-metadata"><summary>${esc([dateLabel,counts,suffix,section?.status==='partial'?'일부 확인':section?.status==='unavailable'?'미확보':'','출처·확인 범위'].filter(Boolean).join(' · '))}</summary>${section?.note?`<p>${esc(section.note)}</p>`:''}${cov.note?`<p>${esc(cov.note)}</p>`:''}${cov.actualCountNote?`<p>${esc(cov.actualCountNote)}</p>`:''}${section?.status==='partial'||section?.status==='unavailable'?`<p>수집 상태: ${section.status==='partial'?'일부 확인':'미확보'}. 결측값을 보간하거나 0으로 채우지 않습니다.</p>`:''}${sourceLinks(section?.sourceIds)}</details>`;
  }
  function rangeRows(rows, range) {
    const sorted=list(rows).filter(r=>r&&isDate(r.date)).slice().sort((a,b)=>a.date.localeCompare(b.date));
    if (!sorted.length || range==='3Y') return sorted;
    const start=new Date(sorted.at(-1).date+'T00:00:00Z');
    if (range==='1Y') start.setUTCFullYear(start.getUTCFullYear()-1); else start.setUTCMonth(start.getUTCMonth()-3);
    return sorted.filter(r=>r.date>=start.toISOString().slice(0,10));
  }
  function chartModel(rows, keys, range, includeZero) {
    const filtered=rangeRows(rows,range), values=filtered.flatMap(r=>keys.map(k=>r[k])).filter(finite);
    if(!filtered.length||!values.length) return null;
    let min=Math.min(...values),max=Math.max(...values);
    if(includeZero){min=Math.min(min,0);max=Math.max(max,0);}
    const pad=(max-min||Math.abs(max)||1)*.08;min-=pad;max+=pad;
    const width=620,height=260,left=62,right=12,top=16,bottom=31;
    const x=i=>left+(width-left-right)*(filtered.length===1?.5:i/(filtered.length-1)), y=v=>top+(height-top-bottom)*(max-v)/(max-min);
    const paths=keys.map(key=>{let path='',pen=false;filtered.forEach((r,i)=>{if(!finite(r[key])){pen=false;return;}path+=`${pen?'L':'M'}${x(i).toFixed(2)},${y(r[key]).toFixed(2)} `;pen=true;});return {key,path};});
    return {rows:filtered,keys,min,max,width,height,left,right,top,bottom,x,y,paths};
  }
  function tooltip(model, row) {return `<b>${esc(row.date)}</b>${model.keys.map(key=>`<span style="color:${COLORS[key]||'#88a9ff'}">${esc(NAMES[key]||key)} ${finite(row[key])?fmt(row[key],1)+'억원':'미확인'}</span>`).join('')}`;}
  function chart(id, rows, keys, range, label, includeZero=true) {
    const model=chartModel(rows,keys,range,includeZero);if(!model)return empty();charts.set(id,model);
    const ticks=Array.from({length:5},(_,i)=>model.max-(model.max-model.min)*i/4);
    const dateIndexes=[...new Set([0,Math.floor((model.rows.length-1)/2),model.rows.length-1])];
    const legend=keys.map(key=>`<span><i style="background:${COLORS[key]||'#88a9ff'}"></i>${esc(NAMES[key]||key)}</span>`).join('');
    const lines=ticks.map(value=>`<line class="kr-gridline" x1="${model.left}" x2="${model.width-model.right}" y1="${model.y(value)}" y2="${model.y(value)}"/><text x="${model.left-8}" y="${model.y(value)+3}" text-anchor="end">${fmt(value)}</text>`).join('');
    const dates=dateIndexes.map((i,n)=>`<text x="${model.x(i)}" y="${model.height-8}" text-anchor="${n===0?'start':n===dateIndexes.length-1?'end':'middle'}">${model.rows[i].date}</text>`).join('');
    const paths=model.paths.map(p=>`<path d="${p.path}" fill="none" stroke="${COLORS[p.key]||'#88a9ff'}" stroke-width="1.4" vector-effect="non-scaling-stroke"/>`).join('');
    const zero=includeZero&&model.min<=0&&model.max>=0?`<line class="kr-zero" x1="${model.left}" x2="${model.width-model.right}" y1="${model.y(0)}" y2="${model.y(0)}"/>`:'';
    return `<div class="kr-legend">${legend}</div><div class="kr-chart" data-kr-chart="${id}"><svg viewBox="0 0 ${model.width} ${model.height}" role="img" aria-label="${esc(label)}. ${model.rows[0].date}부터 ${model.rows.at(-1).date}, ${model.rows.length}개 일별 관측, 단위 억원. 아래 일별 표에서도 확인 가능합니다." tabindex="0">${lines}${zero}${dates}${paths}${model.rows.length===1?keys.filter(key=>finite(model.rows[0][key])).map(key=>`<circle cx="${model.x(0)}" cy="${model.y(model.rows[0][key])}" r="3" fill="${COLORS[key]}"/>`).join(''):''}<line data-kr-cursor x1="0" x2="0" y1="16" y2="229" stroke="#9bb0d1" stroke-dasharray="3 3" visibility="hidden"/></svg><div class="kr-tooltip" data-kr-tooltip aria-live="off">${tooltip(model,model.rows.at(-1))}</div></div><details class="kr-chart-table"><summary>일별 데이터 표 · ${model.rows.length}개 관측</summary><div class="kr-table-wrap" tabindex="0" role="region" aria-label="${esc(label)} 일별 표"><table class="kr-table"><thead><tr><th scope="col">날짜</th>${keys.map(key=>`<th scope="col">${esc(NAMES[key]||key)} · 억원</th>`).join('')}</tr></thead><tbody>${model.rows.slice().reverse().map(row=>`<tr><td>${row.date}</td>${keys.map(key=>`<td>${includeZero?signed(row[key]):fmt(row[key],1)}</td>`).join('')}</tr>`).join('')}</tbody></table></div></details>`;
  }
  function ranges(kind, active) {return `<div class="kr-controls" role="group" aria-label="${kind==='flow'?'투자자 순매수':'예탁금·신용잔고'} 차트 기간">${['3M','1Y','3Y'].map(value=>`<button type="button" data-kr-range="${kind}" data-range="${value}" aria-pressed="${active===value}">${{ '3M':'3개월','1Y':'1년','3Y':'3년'}[value]}</button>`).join('')}</div>`;}
  function latestBrief() {return list(window.TerminalBriefingData?.entries).filter(entry=>entry?.market==='KR'&&isDate(entry.date)).sort((a,b)=>b.date.localeCompare(a.date))[0]||null;}
  function briefSourceLinks(ids, entry) {return list(ids).map(id=>list(entry?.sources).find(source=>source.id===id)).filter(Boolean).map(source=>safe(source.url)?`<a href="${esc(safe(source.url))}" target="_blank" rel="noopener noreferrer" title="${esc(source.note||'')}">${esc(source.title||source.id)} ↗</a>`:'').join(' ');}
  function briefSources(entry, ids, note) {return `<details class="kr-metadata"><summary>${esc(entry?.date||'')} 기준 · 출처·확인 범위</summary>${note?`<p>${esc(note)}</p>`:''}${briefSourceLinks([...new Set(ids)],entry)}</details>`;}
  function pct(value) {return finite(value)?`<span class="kr-value ${value>0?'up':value<0?'down':''}">${value>0?'+':''}${fmt(value,2)}%</span>`:'<span class="muted">미확인</span>';}
  function closeSection() {
    const entry=latestBrief();
    if(!entry)return `<section class="kr-section" id="kr-close"><div class="kr-section-head"><h3>국내 시장 마감</h3></div>${empty(window.TerminalBriefingData?.failed?'마감 브리핑 파일을 불러오지 못했습니다. 아래 수급·자금 자료는 별도로 표시합니다.':'마감 브리핑을 불러오는 중입니다.')}</section>`;
    const stories=list(entry.summary), follow=stories.filter(story=>/휴장일 후속/.test(story.title||'')), close=stories.filter(story=>!/휴장일 후속/.test(story.title||''));
    const ids=[...stories.flatMap(story=>list(story.sourceIds)),...list(entry.indices).flatMap(row=>list(row.sourceIds))];
    return `<section class="kr-section kr-close" id="kr-close" aria-labelledby="kr-close-title"><div class="kr-close-top"><div><div class="eyebrow">KOREA MARKET CLOSE · ${entry.date}</div><h3 id="kr-close-title">${esc(entry.title||'국내 시장 마감')}</h3><p>한국 현지 ${entry.date} 마감 기준 · 이후 소식은 별도 표시</p></div><div class="kr-close-indices">${list(entry.indices).map(index=>`<article><small>${esc(index.name)}</small><strong>${fmt(index.close,2)}</strong>${pct(index.changePct)}</article>`).join('')}</div></div><div class="kr-close-points">${close.map(story=>`<article><h4>${esc(story.title)}</h4><p>${esc(story.text)}</p></article>`).join('')}</div>${follow.length?`<details class="kr-holiday"><summary>휴장일 후속 소식 · ${follow.length}건</summary><p class="kr-note">아래 소식은 ${entry.date} 마감 이후 정보입니다. 새로운 국내 거래일 수치가 아닙니다.</p>${follow.map(story=>`<article><h4>${esc(story.title)}</h4><p>${esc(story.text)}</p></article>`).join('')}</details>`:''}${briefSources(entry,ids,'마감 시황은 기존 검증 브리핑을 함께 사용합니다. 아래 일별 수급은 별도의 NAVER 최신 일별 표이며 마감 기사와 집계시각이 다를 수 있습니다.')}</section>`;
  }
  function dailyFlowSummary() {
    return `<section class="kr-section" aria-labelledby="kr-daily-flow-title"><div class="kr-section-head"><div><h3 id="kr-daily-flow-title">당일 시장 수급</h3><p>각 시장의 최신 확인 거래일 · 아래 3년 차트와 같은 NAVER KRX 자료 · 억원</p></div></div><div class="kr-grid">${['KOSPI','KOSDAQ'].map(market=>{const section=payload.flows?.markets?.[market]||{},row=list(section.rows).at(-1);return `<article class="kr-card"><div class="kr-card-head"><h4>${market}</h4><span class="kr-badge">${esc(row?.date||'미확인')}</span></div><div class="kr-daily-values">${['foreign','institution','individual'].map(key=>`<div><small>${NAMES[key]}</small><strong>${signed(row?.[key])}</strong></div>`).join('')}</div>${meta(section,'최신 일별 순매수')}</article>`;}).join('')}</div></section>`;
  }
  function sectorReturnsSection() {
    const entry=latestBrief(),section=entry?.sectors||{},rows=list(section.rows),groups=[...new Set(rows.map(row=>row.group||'업종 비교'))];
    const sorted=groups.flatMap(group=>rows.filter(row=>(row.group||'업종 비교')===group).sort((a,b)=>finite(a[sectorSort])&&finite(b[sectorSort])?(sectorDescending?b[sectorSort]-a[sectorSort]:a[sectorSort]-b[sectorSort]):finite(a[sectorSort])?-1:finite(b[sectorSort])?1:0));
    const headings=[['day','1일'],['week','1주'],['month','1개월']].map(([key,label])=>`<th scope="col" aria-sort="${sectorSort===key?(sectorDescending?'descending':'ascending'):'none'}"><button type="button" data-kr-sector-sort="${key}">${label}${sectorSort===key?(sectorDescending?' ↓':' ↑'):' ↕'}</button></th>`).join('');
    let previous='';
    const body=sorted.map((row,i)=>{const group=row.group||'업종 비교',separator=group!==previous?`<tr class="kr-group-row"><th colspan="5">${esc(group)}</th></tr>`:'';previous=group;const holding=row.holdings, names=holding?.status==='verified'&&list(holding.top5).length===5?list(holding.top5).map(item=>esc(item.shortName||item.name)).join(' / '):'상위 5종목 미확인';return separator+`<tr><td>${i+1}</td><td title="${esc(row.benchmark||row.name)}">${esc(row.name)}<small>${esc(row.ticker)}${row.instrumentType==='etf'?'('+names+')':row.benchmark?' · '+esc(row.benchmark):''}</small></td><td>${pct(row.day)}</td><td>${pct(row.week)}</td><td>${pct(row.month)}</td></tr>`;}).join('');
    const ids=rows.flatMap(row=>[...list(row.sourceIds),...list(row.holdings?.sourceIds)]);
    const holdingDates=rows.filter(row=>row.instrumentType==='etf').map(row=>`${row.ticker} ${row.benchmark||row.name}: ${row.holdings?.asOf||'보유내역 기준일 미확인'}`).join(' · ');
    return `<section class="kr-section" id="kr-sector-returns" aria-labelledby="kr-sector-return-title"><div class="kr-section-head"><div><h3 id="kr-sector-return-title">업종별 수익률</h3><p>${esc(entry?.date||'미확인')} 마감 기준 · ETF·대표 종목 바스켓 ${rows.length}개 · 열 제목으로 정렬</p></div></div><article class="kr-card">${rows.length?`<div class="kr-table-wrap" tabindex="0" role="region" aria-label="국내 업종별 1일 1주 1개월 수익률"><table class="kr-table kr-sector-return-table"><caption>ETF는 실제 편입비중이 반영된 가격수익률 · 대표 3사 바스켓만 동일가중 · 괄호는 ETF 상위 5개 보유종목</caption><thead><tr><th scope="col">#</th><th scope="col">업종 / 비교지표</th>${headings}</tr></thead><tbody>${body}</tbody></table></div>`:empty('검증된 국내 업종 수익률을 불러오지 못했습니다.')}${briefSources(entry,ids,[section.methodology,(section.note||'').replace('실제 보유내역 기준일과 출처를 각 행에 표시합니다.','실제 보유내역 기준일과 출처는 이 펼침 정보에 표시합니다.'),holdingDates].filter(Boolean).join(' '))}</article></section>`;
  }
  function highsSection() {
    const entry=latestBrief(),section=entry?.highs||{},rows=list(section.rows),coverage=entry?.screeningCoverage||{};
    const ids=rows.flatMap(row=>list(row.sourceIds));
    return `<section class="kr-section" id="kr-highs" aria-labelledby="kr-highs-title"><div class="kr-section-head"><div><h3 id="kr-highs-title">52주 신고가 기업</h3><p>${esc(entry?.date||'미확인')} 기준 · ${esc(section.caption||'검증 범위 미확인')}</p></div></div><p class="kr-note">${esc(section.criteria||'')} 종가 신고가·사상 최고가를 뜻하지 않습니다.</p><div class="kr-highs-coverage">${[['선별 기업',coverage.selected],['당일 일봉 확인',coverage.dailyValid],['52주 이력 확인',coverage.full52WeekHistory],['검증 제외',coverage.missingCount]].map(([label,value])=>`<span>${label} <b>${fmt(value)}</b></span>`).join('')}</div><div class="kr-grid">${rows.length?rows.map(row=>`<article class="kr-card"><div class="kr-card-head"><h4>${esc(row.name)} <small class="muted">${esc(row.ticker)}</small></h4>${pct(row.changePct)}</div><div class="kr-card-body"><p class="kr-note">${esc(row.kind)}</p><p>${esc(row.reason)}</p></div></article>`).join(''):empty('확인된 신고가 목록이 없습니다. 미확인은 해당 사례가 없다는 뜻이 아닙니다.')}</div>${briefSources(entry,ids,section.note)}</section>`;
  }
  function flowSection() {
    return `<section class="kr-section" aria-labelledby="kr-flows-title"><div class="kr-section-head"><div><h3 id="kr-flows-title">투자자별 일별 순매수</h3><p>양수는 순매수, 음수는 순매도 · 억원 · 선에 마우스를 올리거나 좌우 방향키로 날짜 확인</p></div>${ranges('flow',flowRange)}</div><div class="kr-grid">${['KOSPI','KOSDAQ'].map(market=>{const section=payload.flows?.markets?.[market]||{};return `<article class="kr-card"><div class="kr-card-head"><h4>${market}</h4><span class="kr-badge">일별 · 억원</span></div><div class="kr-card-body">${chart('flow-'+market,section.rows,['foreign','institution','individual'],flowRange,market+' 투자자별 순매수')}</div>${meta(section)}</article>`;}).join('')}</div></section>`;
  }
  function rankingTable(section, limit, valueLabel) {
    const rows=list(rankMarket==='ALL'?section?.rows:section?.byMarket?.[rankMarket]).slice(0,limit);
    if(!rows.length)return empty(section?.note||'이 날짜의 전체시장 순위 자료를 확보하지 못했습니다.');
    return `<div class="kr-table-wrap" tabindex="0" role="region" aria-label="${esc(valueLabel)} 순위표"><table class="kr-table"><caption>${esc(rankMarket==='ALL'?(section?.coverage?.universe||'KOSPI + KOSDAQ'):rankMarket+' · 해당 시장 내 순위')} · ${esc(valueLabel)} · 억원${section?.status==='partial'?' · 부분 자료':''}</caption><thead><tr><th scope="col">순위</th><th scope="col">종목</th><th scope="col">시장</th><th scope="col">${esc(valueLabel)}</th></tr></thead><tbody>${rows.map((row,i)=>`<tr><td>${i+1}</td><td>${esc(row.name)}<small>${esc(row.code)}</small></td><td>${esc(row.market||'미확인')}</td><td>${valueLabel==='거래대금'?`<span class="kr-value">${fmt(row.value,1)}</span>`:signed(row.value)}</td></tr>`).join('')}</tbody></table></div>`;
  }
  function selectedSection(group) {return selected==='1m'?payload[group]?.monthly:selected==='5d'?payload[group]?.aggregate5d:payload[group]?.daily?.[selected];}
  function selectionLabel() {const period=selected==='1m'?payload.rankings?.monthly:payload.rankings?.aggregate5d, start=period?.start||period?.startDate||period?.foreign?.coverage?.start, end=period?.end||period?.endDate||period?.foreign?.coverage?.end;return ['1m','5d'].includes(selected)?`${selected==='1m'?'월간':'최근 5거래일'} 합계 (${start||list(payload.rankings?.dates).slice().sort()[0]||'?'} ~ ${end||list(payload.rankings?.dates).slice().sort().at(-1)||'?'})`:selected||'날짜 미확인';}
  function themesSection() {
    const section=selectedSection('themes')||{}, rows=list(section.rows), max=Math.max(1,...rows.flatMap(r=>[r.foreign,r.institution]).filter(finite).map(Math.abs));
    const bar=value=>finite(value)?`<span class="kr-theme-bar ${value>0?'up':value<0?'down':''}"><i style="width:${Math.abs(value)/max*100}%"></i>${signed(value)}</span>`:'<span class="muted">미확인</span>';
    return `<article class="kr-card"><div class="kr-card-head"><h4>테마별 대표 종목 수급</h4><span class="kr-badge">${esc(section.coverage?.start||'')}${section.coverage?.end&&section.coverage.end!==section.coverage.start?' ~ '+esc(section.coverage.end):''} · 억원</span></div><div class="kr-card-body"><p class="kr-note">${esc(payload.themes?.methodology||'업종과 테마의 분류·구성 종목·집계 범위는 아래 확인 범위를 참고하세요.')}</p>${section.coverage?.note?`<p class="kr-note">확인 범위: ${esc(section.coverage.note)}</p>`:''}${rows.length?`<div class="kr-table-wrap" tabindex="0" role="region" aria-label="업종 테마별 순매수 표"><table class="kr-table kr-theme-table"><thead><tr><th scope="col">#</th><th scope="col">업종 / 테마</th><th scope="col">외국인</th><th scope="col">기관</th><th scope="col">확인 범위</th></tr></thead><tbody>${rows.map((row,i)=>`<tr><td>${i+1}</td><td>${esc(row.name)}${list(row.members).length?`<small>(${list(row.members).map(m=>esc(m.name)).join(' / ')})</small>`:''}</td><td>${bar(row.foreign)}${!finite(row.foreign)&&row.coverage?.foreign?`<small>${row.coverage.foreign.availableCount}/${row.memberCount}개 확인</small>`:''}</td><td>${bar(row.institution)}${!finite(row.institution)&&row.coverage?.institution?`<small>${row.coverage.institution.availableCount}/${row.memberCount}개 확인</small>`:''}</td><td><small>${esc(row.note||((row.memberCount??'?')+'개 종목'))}</small></td></tr>`).join('')}</tbody></table></div>`:empty(section.note||payload.themes?.note)}</div>${meta(section,'테마 중복 편입 가능')}</article>`;
  }
  function rankingsSection() {
    const data=selectedSection('rankings')||{}, dates=list(payload.rankings?.dates).filter(isDate).slice().sort().reverse(), turnover=payload.rankings?.daily?.[dates[0]]?.tradedValue;
    return `<section class="kr-section" aria-labelledby="kr-rankings-title"><div class="kr-section-head"><div><h3 id="kr-rankings-title">업종 · 종목 수급</h3><p>${esc(selectionLabel())} · 날짜 선택은 아래 업종·순매수 종목에 적용됩니다. 거래대금은 별도 최신 거래일 기준입니다.</p></div><div class="kr-controls" role="group" aria-label="수급 집계 기간">${[['day','1일'],['5d','주간'],['1m','월간']].map(([key,label])=>`<button type="button" data-kr-period="${key}" aria-pressed="${key==='day'?!['5d','1m'].includes(selected):selected===key}">${label}</button>`).join('')}</div><div class="kr-controls"><label for="kr-date">일별 기준일<select id="kr-date"${dates.length&&!['5d','1m'].includes(selected)?'':' disabled'}>${dates.length?dates.map(date=>`<option value="${date}"${selected===date?' selected':''}>${date}</option>`).join(''):'<option>확인된 거래일 없음</option>'}</select></label></div></div>${payload.rankings?.note?`<p class="kr-note">${esc(payload.rankings.note)}</p>`:''}${themesSection()}<div class="kr-section-head" style="margin-top:18px"><span class="kr-note">종목 순위 시장</span><div class="kr-controls" role="group" aria-label="종목 순위 시장">${[['ALL','통합'],['KOSPI','KOSPI'],['KOSDAQ','KOSDAQ']].map(([key,label])=>`<button type="button" data-kr-rank-market="${key}" aria-pressed="${rankMarket===key}">${label}</button>`).join('')}</div></div><div class="kr-grid" style="margin-top:14px">${['foreign','institution'].map(key=>`<article class="kr-card"><div class="kr-card-head"><h4>${NAMES[key]} 순매수 상위 10</h4><span class="kr-badge">${esc(selected==='1m'?'1개월 합계':selected==='5d'?'5일 합계':selected)}</span></div>${rankingTable(data[key],10,'순매수')}${meta(data[key])}</article>`).join('')}</div><article class="kr-card" style="margin-top:14px"><div class="kr-card-head"><h4>거래대금 상위 20</h4><span class="kr-badge">${esc(dates[0]||'미확인')} · 최신 거래일</span></div>${rankingTable(turnover,20,'거래대금')}${meta(turnover)}</article></section>`;
  }
  function moversSection() {
    const requestedDay=['5d','1m'].includes(selected)?list(payload.rankings?.dates).slice().sort().at(-1):selected;
    const day=payload.indexMovers?.daily?.[requestedDay]?requestedDay:Object.keys(payload.indexMovers?.daily||{}).sort().at(-1);
    const section=(moversPeriod==='month'?payload.indexMovers?.monthly:moversPeriod==='week'?payload.indexMovers?.aggregate5d:payload.indexMovers?.daily?.[day])?.[selectedIndex]||{}, universeTitle=selectedIndex+(section.coverage?.universeType==='etf-proxy'?' 추종ETF 구성종목':''), periodLabel={day:'일별 등락률',week:'5거래일 수익률',month:'1개월 수익률'}[moversPeriod], pct=value=>finite(value)?`<span class="kr-value ${value>0?'up':value<0?'down':''}">${value>0?'+':''}${fmt(value,2)}%</span>`:'<span class="muted">미확인</span>';
    const table=(key,label)=>{const rows=list(section[key]).slice(0,10);return `<article class="kr-card"><div class="kr-card-head"><h4>${universeTitle} ${label} 상위 10</h4><span class="kr-badge">${periodLabel}</span></div>${rows.length?`<div class="kr-table-wrap" tabindex="0" role="region" aria-label="${selectedIndex} ${label} 순위표"><table class="kr-table"><caption>${esc(section.coverage?.universe||selectedIndex+' 확인된 구성종목')} · %</caption><thead><tr><th scope="col">순위</th><th scope="col">종목</th><th scope="col">${periodLabel}</th></tr></thead><tbody>${rows.map((row,i)=>`<tr><td>${i+1}</td><td>${esc(row.name)}<small>${esc(row.code)}</small></td><td>${pct(row.changePct)}</td></tr>`).join('')}</tbody></table></div>`:empty(section.note||'이 날짜의 지수 구성종목별 수익률을 확보하지 못했습니다.')}</article>`;};
    return `<section class="kr-section" aria-labelledby="kr-movers-title"><div class="kr-section-head"><div><h3 id="kr-movers-title">지수 구성종목 상승률 · 하락률</h3><p>${esc(section.comparisonStart&&section.comparisonEnd?section.comparisonStart+' → '+section.comparisonEnd:day||'기준일 미확인')} · 1일은 확인된 날짜만 연동 · 주간·월간은 지수 분석의 최신 확인일 기준</p></div><div class="kr-controls" role="group" aria-label="등락률 지수 선택">${['KOSPI200','KOSDAQ150'].map(key=>`<button type="button" data-kr-index="${key}" aria-pressed="${selectedIndex===key}">${key==='KOSPI200'?'KOSPI 200':'KOSDAQ 150'}</button>`).join('')}</div><div class="kr-controls" role="group" aria-label="등락률 기간 선택">${[['day','1일'],['week','주간'],['month','월간']].map(([key,label])=>`<button type="button" data-kr-movers-period="${key}" aria-pressed="${moversPeriod===key}">${label}</button>`).join('')}</div></div>${section.coverage?.universeType==='etf-proxy'?'<p class="kr-warn">운용사 추종 ETF의 공개 구성종목 기준입니다. 공식 지수의 과거 시점 구성종목 전수 순위와 다를 수 있습니다.</p>':''}${payload.indexMovers?.note?`<p class="kr-note">${esc(payload.indexMovers.note)}</p>`:''}<div class="kr-grid">${table('gainers','상승률')}${table('losers','하락률')}</div>${meta(section,selectedIndex)}</section>`;
  }
  function liquiditySection() {
    const series=payload.liquidity?.series||{};
    return `<section class="kr-section" aria-labelledby="kr-liquidity-title"><div class="kr-section-head"><div><h3 id="kr-liquidity-title">투자자예탁금 · 신용융자 잔고</h3><p>예탁금은 증시 전체 합계 · 신용융자는 KOSPI / KOSDAQ 구분 · 억원</p></div>${ranges('liquidity',liquidityRange)}</div>${summary()}${payload.liquidity?.note?`<p class="kr-note">${esc(payload.liquidity.note)}</p>`:''}<article class="kr-card"><div class="kr-card-head"><h4>투자자예탁금</h4><span class="kr-badge">시장 전체 · 억원</span></div><div class="kr-card-body">${chart('deposits',list(series.deposits?.rows).map(r=>({date:r.date,deposits:r.value})),['deposits'],liquidityRange,'시장 전체 투자자예탁금',false)}</div>${meta(series.deposits)}</article><div class="kr-grid kr-credit-grid" style="margin-top:14px">${['creditKOSPI','creditKOSDAQ'].map(key=>`<article class="kr-card"><div class="kr-card-head"><h4>${NAMES[key]} 잔고</h4><span class="kr-badge">억원</span></div><div class="kr-card-body">${chart(key,list(series[key]?.rows).map(r=>({date:r.date,[key]:r.value})),[key],liquidityRange,NAMES[key]+' 잔고',false)}</div>${meta(series[key])}</article>`).join('')}</div></section>`;
  }
  function summary() {
    const series=payload.liquidity?.series||{};
    const cards=['deposits','creditKOSPI','creditKOSDAQ'].map(key=>{const section=series[key]||{}, latest=list(section.rows).filter(r=>finite(r.value)).at(-1);return `<article class="kr-summary-card"><small>${NAMES[key]}${key==='deposits'?' · 시장 전체':''}</small><strong>${latest?fmt(latest.value/10000,2)+'조원':'미확인'}</strong><p>${latest?latest.date+' 기준':'검증된 관측값 없음'}</p></article>`;});
    return `<div class="kr-summary kr-balance-summary">${cards.join('')}</div>`;
  }
  function render() {
    const target=el('kr-content');if(!target)return;
    if(loading){target.innerHTML='<div class="kr-empty kr-loading">국내 시장 데이터를 불러오는 중입니다.</div>';return;}
    if(failed||!payload){target.innerHTML=closeSection()+'<div class="kr-empty" role="alert"><div>국내 수급·자금 데이터 파일을 불러오지 못했습니다. 마감 시황·업종 수익률·신고가는 별도 브리핑 자료입니다.<br><button type="button" class="button" id="kr-retry">다시 불러오기</button></div></div>'+sectorReturnsSection()+highsSection();el('kr-retry').onclick=load;bindSectorSorting();return;}
    charts=new Map();
    const dates=list(payload.rankings?.dates).filter(isDate).slice().sort().reverse();if(!['5d','1m'].includes(selected)&&!dates.includes(selected))selected=dates[0]||'';
    el('kr-asof').innerHTML=`<span>자료 기준일</span><strong>${esc(payload.asOf||'미확인')}</strong><span>항목별 실제 관측일은 아래 표시</span>`;
    target.innerHTML=(payload.refresh?.failures?.length?`<div class="kr-warn">일부 데이터 갱신에 실패해 이전 관측값을 보존했습니다. 각 항목의 실제 기준일을 확인하세요.</div>`:'')+closeSection()+dailyFlowSummary()+`<p class="kr-statusline">일별 자료 · 최신 관측일과 공개 시차는 항목별로 다릅니다.${payload.requestedWindow?' 조회 목표: '+esc(payload.requestedWindow.start)+' ~ '+esc(payload.requestedWindow.end)+'.':''}</p>`+flowSection()+sectorReturnsSection()+rankingsSection()+moversSection()+highsSection()+liquiditySection()+`<details class="kr-source-list"><summary>전체 출처 · 데이터 제약</summary><ol>${list(payload.sources).map(s=>`<li>${safe(s.url)?`<a href="${esc(safe(s.url))}" target="_blank" rel="noopener noreferrer">${esc(s.title||s.id)} ↗</a>`:esc(s.title||s.id)}${s.note?' · '+esc(s.note):''}</li>`).join('')}</ol><ul>${list(payload.limitations).map(note=>`<li>${esc(note)}</li>`).join('')}</ul><p>수집 시각: ${esc(payload.updatedAt||'미확인')}</p></details><p class="kr-page-footer">공개 자료 기반 개인 연구용 대시보드입니다. 실시간 시세나 투자 권유가 아닙니다. 미확인 값은 0이 아니며, 테마는 서로 중복될 수 있어 합산하면 전체시장과 일치하지 않습니다.</p>`;
    document.querySelectorAll('[data-kr-range]').forEach(button=>button.onclick=()=>{if(button.dataset.krRange==='flow')flowRange=button.dataset.range;else liquidityRange=button.dataset.range;render();});
    document.querySelectorAll('[data-kr-period]').forEach(button=>button.onclick=()=>{selected=button.dataset.krPeriod==='day'?dates[0]||'':button.dataset.krPeriod;render();});
    const dateSelect=el('kr-date');if(dateSelect)dateSelect.onchange=event=>{selected=event.target.value;render();};
    document.querySelectorAll('[data-kr-index]').forEach(button=>button.onclick=()=>{selectedIndex=button.dataset.krIndex;render();});
    document.querySelectorAll('[data-kr-movers-period]').forEach(button=>button.onclick=()=>{moversPeriod=button.dataset.krMoversPeriod;render();});
    document.querySelectorAll('[data-kr-rank-market]').forEach(button=>button.onclick=()=>{rankMarket=button.dataset.krRankMarket;render();});
    bindSectorSorting();
    bindCharts();
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
    loading=true;failed=false;render();
    try {const response=await fetch('./data/korea-market.json?ts='+Date.now());if(!response.ok)throw new Error('HTTP '+response.status);const next=await response.json();if(next.schemaVersion!==1||!Array.isArray(next.sources)||!next.flows||!next.liquidity)throw new Error('Unsupported Korean market schema');payload=next;}
    catch(error){failed=true;console.error('Korean market data:',error);}
    loading=false;render();
  }
  function route(){if(window.location.hash.split('/')[0]==='#korea'&&!payload&&!loading)load();}
  function boot(){window.addEventListener('hashchange',route);window.addEventListener('terminal-briefing-ready',()=>{if(!loading&&(payload||failed))render();});route();}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot,{once:true});else boot();
}());
