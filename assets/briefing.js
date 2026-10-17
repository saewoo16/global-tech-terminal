/* A source-backed daily archive. Missing evidence is never rendered as zero. */
(function () {
  'use strict';
  const el = id => document.getElementById(id);
  const text = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const list = value => Array.isArray(value) ? value.filter(v => v !== null && v !== undefined) : [];
  const number = value => typeof value === 'number' && Number.isFinite(value);
  const format = value => number(value) ? value.toLocaleString('ko-KR', {maximumFractionDigits:2}) : '미확인';
  const date = value => typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value) && Number.isFinite(Date.parse(value)) && new Date(value).toISOString().slice(0,10) === value;
  const safe = value => { try { const url = new URL(value); return ['https:','http:'].includes(url.protocol) && !url.username && !url.password ? url.href : ''; } catch (_) { return ''; } };
  const pct = value => number(value) ? `<span class="brief-return ${value > 0 ? 'up' : value < 0 ? 'down' : ''}">${value > 0 ? '+' : ''}${value.toFixed(2)}%</span>` : '<span class="muted">미확인</span>';
  let entries = [], market = 'US', selectedDate = '', loading = true, failed = false, activeView = 'explorer', sortKey = 'day', sortDesc = true;
  function citations(ids, entry) {
    return list(ids).map(id => list(entry.sources).find(source => source.id === id)).filter(Boolean).map(source => {
      const url = safe(source.url);
      return url ? `<a href="${text(url)}" target="_blank" rel="noopener noreferrer" title="${text(source.title)}">[${list(entry.sources).indexOf(source)+1}] ↗</a>` : '';
    }).filter(Boolean).join(' · ');
  }
  function citationLine(ids, entry) { const links = citations(ids, entry); return links ? `<span class="brief-citations">${links}</span>` : ''; }
  function note(value) { return value ? `<p class="brief-note">${text(value)}</p>` : ''; }
  function blank(value) { return `<div class="brief-empty">${text(value || '이 항목은 아직 검증된 자료가 없습니다. 미확인을 “해당 없음”으로 간주하지 않습니다.')}</div>`; }
  function details(id, title, caption, body, open = false) { return `<details class="brief-detail" id="${id}"${open ? ' open' : ''}><summary><span><span class="detail-title">${title}</span><span class="detail-caption">${text(caption)}</span></span></summary><div class="detail-body">${body}</div></details>`; }
  function holdingsLabel(row, entry) {
    if (row.instrumentType !== 'etf') return '';
    const holdings = row.holdings || {}, top = list(holdings.top5);
    if (holdings.status !== 'verified' || top.length !== 5 || !date(holdings.asOf)) {
      return '<span class="brief-holdings muted">(상위 5종목 미확인)</span>';
    }
    return `<span class="brief-holdings">(${top.map(item => text(item.shortName || item.name)).join(' / ')})</span>`;
  }
  function sectorSection(entry) {
    const section = entry.sectors || {}, rows = list(section.rows);
    const groups = [...new Set(rows.map(row=>row.group || '대표 업종'))];
    const sorted = groups.flatMap(group=>rows.filter(row=>(row.group || '대표 업종')===group).sort((a,b)=>number(a[sortKey])&&number(b[sortKey])?(sortDesc?b[sortKey]-a[sortKey]:a[sortKey]-b[sortKey]):number(a[sortKey])?-1:number(b[sortKey])?1:0));
    const head = [['day','1일'],['week','1주'],['month','1개월']].map(([key,label])=>`<th scope="col" aria-sort="${sortKey===key?(sortDesc?'descending':'ascending'):'none'}"><button class="sort-button" data-sector-sort="${key}" title="${label} 수익률로 정렬">${label}${sortKey===key?(sortDesc?' ↓':' ↑'):' ↕'}</button></th>`).join('');
    let previousGroup = null;
    const tableRows = sorted.map(row=>{const group=row.group || '대표 업종';const separator=groups.length>1&&group!==previousGroup?`<tr class="sector-separator"><th scope="rowgroup" colspan="5">${text(group)}</th></tr>`:'';previousGroup=group;return separator+`<tr><td>${text(row.name)}${row.instrumentType === 'etf' ? `<small class="brief-etf-label">${text(row.ticker)}${holdingsLabel(row,entry)}</small>` : `<small>${text(row.ticker)}</small>${row.benchmark ? `<small class="brief-benchmark">${text(row.benchmark)}</small>` : ''}`}</td><td>${pct(row.day)}</td><td>${pct(row.week)}</td><td>${pct(row.month)}</td><td>${citationLine(row.sourceIds,entry) || '<span class="muted">미확인</span>'}</td></tr>`;}).join('');
    const body = note(section.methodology) + note(typeof section.note === 'string' ? section.note.replace('기준일과 출처를 각 행에 표시합니다.', '기준일과 출처는 하단 출처 목록에서 확인할 수 있습니다.') : section.note) + (rows.length ? `<div class="tablewrap" tabindex="0" role="region" aria-label="업종별 수익률 표, 가로로 스크롤 가능"><table class="brief-table"><caption>ETF·종목 바스켓 · % · 열 제목을 누르면 정렬 · 미확인은 0이 아닙니다</caption><thead><tr><th scope="col">업종 / ETF</th>${head}<th scope="col">출처</th></tr></thead><tbody>${tableRows}</tbody></table></div>` : blank(section.emptyMessage));
    return details('brief-sectors','업종별 수익률', rows.length ? `${rows.length}개 비교지표 · 1일 / 1주 / 1개월` : '수익률 검증 대기', body, true);
  }
  function storySection(entry, key) {
    const section = entry[key] || {}, rows = list(section.rows), isHigh = key === 'highs';
    const body = note(section.criteria) + note(section.note) + (rows.length ? `<div class="brief-story-grid">${rows.map(row => `<article class="brief-story"><h4>${text(row.name)} <span class="brief-ticker">${text(row.ticker)}</span></h4><div class="story-meta">${number(row.changePct) ? pct(row.changePct) : ''}${row.kind ? `<span class="pill">${text(row.kind)}</span>` : ''}${number(row.marketCapUSD) ? `<span class="pill">시총 $${format(row.marketCapUSD/1e9)}B</span>` : ''}</div>${volumeMetrics(row)}${row.reason ? `<p>${text(row.reason)}</p>` : ''}${citationLine(row.sourceIds,entry)}</article>`).join('')}</div>` : blank(section.emptyMessage));
    return details('brief-'+key,isHigh ? '신고가 · 주목 종목' : '이례적 상승 · 하락', section.caption || (rows.length ? `${rows.length}개 확인 사례 · 원인과 출처` : '전체 스크리닝 미완료 · 확인된 결과만 표시'),body);
  }
  function flowsSection(entry) {
    const section = entry.flows || {}, rows = list(section.rows);
    if (!rows.length) return '';
    const signed = value => number(value) ? `<span class="brief-return ${value>0?'up':value<0?'down':''}">${value>0?'+':''}${format(value)}</span>` : '미확인';
    const body = note(section.asOf) + note(section.note) + `<div class="tablewrap" tabindex="0" role="region" aria-label="투자자별 순매수 표, 가로로 스크롤 가능"><table class="brief-table"><caption>순매수 · ${text(section.unit || '단위 미확인')} · 양수는 순매수, 음수는 순매도</caption><thead><tr><th scope="col">시장</th><th scope="col">외국인</th><th scope="col">기관</th><th scope="col">개인</th></tr></thead><tbody>${rows.map(row=>`<tr><td>${text(row.market)}</td><td>${signed(row.foreign)}</td><td>${signed(row.institution)}</td><td>${signed(row.individual)}</td></tr>`).join('')}</tbody></table></div>`+citationLine(section.sourceIds,entry);
    return details('brief-flows','외국인 · 기관 수급', '시장별 순매수 · '+text(section.unit || '단위 미확인'),body);
  }
  function volumeMetrics(row) {
    const fields = [['당일 거래량',row.volumeCurrent],['전일 거래량',row.volumePrevious]];
    if (!fields.some(([,value])=>number(value)) && !number(row.volumeChangePct)) return '';
    return `<div class="earnings-metrics">${fields.map(([label,value])=>`<div class="earnings-metric"><small>${label}</small><strong>${number(value)?format(value)+'주':'미확인'}</strong></div>`).join('')}<div class="earnings-metric"><small>전일 대비 거래량</small><strong>${pct(row.volumeChangePct)}</strong></div></div>`;
  }
  function earningsSection(entry) {
    const section = entry.earnings || {}, rows = list(section.rows);
    const body = note(section.note) + (rows.length ? `<div class="brief-story-grid">${rows.map(row => `<article class="brief-story"><h4>${text(row.name)} <span class="brief-ticker">${text(row.ticker)}</span></h4>${row.period ? `<span class="pill">${text(row.period)}</span>` : ''}${row.summary ? `<p>${text(row.summary)}</p>` : ''}${list(row.metrics).length ? `<div class="earnings-metrics">${list(row.metrics).map(metric => `<div class="earnings-metric"><small>${text(metric.label)}</small><strong>${text(metric.value)}</strong></div>`).join('')}</div>` : ''}${list(row.callHighlights).length ? `<strong class="call-heading">실적 발표 · 컨퍼런스콜 핵심</strong><ul>${list(row.callHighlights).map(line => `<li>${text(line)}</li>`).join('')}</ul>` : '<p>컨퍼런스콜 원문 요약은 아직 검증하지 않았습니다.</p>'}${citationLine(row.sourceIds,entry)}</article>`).join('')}</div>` : blank(section.emptyMessage));
    return details('brief-earnings','실적 · 컨퍼런스콜', rows.length ? `${rows.length}개 기업 · 실적 수치와 경영진 발언` : '실적 및 발언 검증 대기',body);
  }
  function sourceSection(entry) {
    const sources = list(entry.sources), limitations = list(entry.limitations);
    return `<details class="brief-sources" id="brief-sources"><summary>출처와 확인 범위 · ${sources.length}개 자료</summary>${sources.length ? `<ol>${sources.map(source => {const url = safe(source.url);return `<li>${url ? `<a href="${text(url)}" target="_blank" rel="noopener noreferrer">${text(source.title || source.id)} ↗</a>` : text(source.title || source.id)}${source.note ? ' · '+text(source.note) : ''}</li>`;}).join('')}</ol>` : note('출처 자료가 등록되지 않았습니다.')}${limitations.length ? `<ul class="brief-limitations">${limitations.map(value => `<li>${text(value)}</li>`).join('')}</ul>` : ''}</details>`;
  }
  function render() {
    const expanded = [...document.querySelectorAll('#brief-content details')].map(item=>[item.id,item.open]);
    const dates = [...new Set(entries.filter(entry => entry.market === market).map(entry => entry.date))].sort().reverse();
    if (!dates.includes(selectedDate)) selectedDate = dates[0] || '';
    el('brief-date').innerHTML = dates.length ? dates.map(value => `<option value="${value}">${value}</option>`).join('') : '<option value="">브리핑 없음</option>';
    el('brief-date').value = selectedDate; el('brief-date').disabled = !dates.length;
    document.querySelectorAll('[data-brief-market]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.briefMarket === market)));
    const entry = entries.find(item => item.market === market && item.date === selectedDate);
    if (loading) {el('brief-content').innerHTML = blank('마감 브리핑을 불러오는 중입니다.');return;}
    if (failed) {el('brief-content').innerHTML = '<div class="brief-empty" role="alert"><h3>브리핑 파일을 불러오지 못했습니다.</h3><p>잠시 후 다시 시도해 주세요. 기업 탐색은 계속 사용할 수 있습니다.</p><button class="button" id="brief-retry">다시 불러오기</button></div>';el('brief-retry').onclick=load;return;}
    if (!entry) {el('brief-content').innerHTML=blank(`${market === 'US' ? '미국' : '한국'} 시장의 검증된 마감 브리핑이 아직 없습니다. 다른 시장을 선택해 주세요.`);return;}
    const complete = entry.status === 'complete', published = typeof entry.publishedAt === 'string' ? entry.publishedAt : '';
    const summary = list(entry.summary), indices = list(entry.indices);
    el('brief-content').innerHTML = `<div class="brief-status"><span class="status-badge ${complete ? '' : 'partial'}">${complete ? '검증 자료 게시' : '확인된 자료부터 게시'}</span><span>${market === 'US' ? '미국 현지' : '한국 현지'} ${text(entry.date)} 마감 기준</span>${published ? `<span>게시 ${text(published)}</span>` : ''}</div><section class="brief-hero" aria-labelledby="brief-title"><div class="eyebrow">${market === 'US' ? 'US' : 'KOREA'} MARKET CLOSE</div><h3 id="brief-title">${text(entry.title || '시장 마감 브리핑')}</h3>${summary.length ? `<div class="brief-points">${summary.map(point => `<article class="brief-point"><h4>${text(point.title)}</h4><p>${text(point.text)}</p>${citationLine(point.sourceIds,entry)}</article>`).join('')}</div>` : note('핵심 요약을 아직 검증하지 않았습니다.')}</section>${indices.length ? `<div class="index-grid" aria-label="주요 지수 종가">${indices.map(index => `<article class="index-card"><span class="index-name">${text(index.name)}</span><strong>${format(index.close)}</strong><span class="index-change">${pct(index.changePct)}</span>${citationLine(index.sourceIds,entry)}</article>`).join('')}</div>` : ''}<p class="brief-note brief-scope">업종은 명시한 ETF·대표 종목 바스켓 기준 · 스크리닝과 콜의 확인 범위는 각 항목에 표시합니다.</p>${flowsSection(entry)}${sectorSection(entry)}${storySection(entry,'movers')}${storySection(entry,'highs')}${earningsSection(entry)}${list(entry.watchlist).length ? `<section class="brief-watch"><h3>다음 거래일 체크</h3><ul>${list(entry.watchlist).map(item => `<li>${text(item)}</li>`).join('')}</ul></section>` : ''}${sourceSection(entry)}<p class="brief-footer">공개 자료를 바탕으로 작성한 개인 연구용 브리핑입니다. 실시간 시세나 투자 권유가 아닙니다. 빈 항목은 미확인이며, 전체 시장에 해당 사례가 없다는 뜻이 아닙니다.</p>`;
    expanded.forEach(([id,open])=>{if(id && el(id))el(id).open=open;});
    document.querySelectorAll('[data-sector-sort]').forEach(button=>button.onclick=()=>{if(sortKey===button.dataset.sectorSort)sortDesc=!sortDesc;else{sortKey=button.dataset.sectorSort;sortDesc=true;}render();const target=document.querySelector(`[data-sector-sort="${sortKey}"]`);if(target)target.focus();});
  }
  function view(name) {
    activeView = name === 'briefing' ? 'briefing' : 'explorer';
    const briefing = activeView === 'briefing';
    el('explorer-panel').hidden = briefing; el('briefing-panel').hidden = !briefing;
    document.querySelectorAll('[data-view]').forEach(button => {const selected=button.dataset.view === activeView;button.setAttribute('aria-selected',String(selected));button.tabIndex=selected?0:-1;});
    // Chart.js cannot measure a hidden canvas; resize after returning to explorer.
    if (!briefing && typeof window.requestAnimationFrame === 'function') window.requestAnimationFrame(() => { if (typeof chart !== 'undefined' && chart && typeof chart.resize === 'function') chart.resize(); });
  }
  function route() {
    const parts = window.location.hash.slice(1).split('/');
    if (parts[0] === 'briefing') { if (['US','KR'].includes(parts[1])) market=parts[1];selectedDate=date(parts[2])?parts[2]:selectedDate;view('briefing');render(); }
    else view('explorer');
  }
  function navigate(name) { const hash = name === 'briefing' ? '#briefing/'+market+(selectedDate?'/'+selectedDate:'') : '#explorer'; if (window.location.hash === hash) route(); else window.location.hash=hash; }
  async function load() {
    loading=true;failed=false;render();
    try { const response=await fetch('./data/briefings.json?ts='+Date.now()); if (!response.ok) throw new Error('HTTP '+response.status);const payload=await response.json(); if (payload.schemaVersion !== 1 || !Array.isArray(payload.entries)) throw new Error('Unsupported briefing schema');entries=payload.entries.filter(entry => entry && ['US','KR'].includes(entry.market) && date(entry.date)); }
    catch(error) {failed=true;console.error('Briefing data:',error);}
    loading=false;route();if(activeView!=='briefing')render();
  }
  function boot() {
    const tabs=[...document.querySelectorAll('[data-view]')];
    tabs.forEach((button,index) => {button.onclick=()=>navigate(button.dataset.view);button.onkeydown=event=>{let target=null;if(event.key==='ArrowRight')target=tabs[(index+1)%tabs.length];if(event.key==='ArrowLeft')target=tabs[(index+tabs.length-1)%tabs.length];if(event.key==='Home')target=tabs[0];if(event.key==='End')target=tabs[tabs.length-1];if(target){event.preventDefault();target.focus();navigate(target.dataset.view);}};});
    document.querySelectorAll('[data-brief-market]').forEach(button=>button.onclick=()=>{market=button.dataset.briefMarket;render();navigate('briefing');});
    el('brief-date').onchange=event=>{selectedDate=event.target.value;render();navigate('briefing');};
    window.addEventListener('hashchange',route);route();load();
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot,{once:true});else boot();
}());
