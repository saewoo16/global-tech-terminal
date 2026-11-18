const assert = require('node:assert/strict');
const fs = require('node:fs');

const html = fs.readFileSync('index.html', 'utf8');
assert.match(html, /id="short-tab"[^>]*data-view="short"[^>]*aria-controls="short-panel"[^>]*>공매도<\/button>/);
assert.match(html, /short-balance\.css\?v=20261116-krx-links/);
assert.doesNotMatch(html, /short-balance\.js|korean_short_balance\.json|short-balance-evidence\//);

const wholePanel = html.match(/<section id="short-panel"[^>]*role="tabpanel"[^>]*aria-labelledby="short-tab"[^>]*>([\s\S]*?)<section id="korea-panel"/)[1];
const story = wholePanel.match(/<section class="short-card" id="short-reported-market-20261117"[\s\S]*?<\/section>/)[0];
assert.match(story,/11월 17일 공매도 거래대금/);
assert.match(story,/1조 2,151억원/);
assert.match(story,/82\.62%/);
assert.match(story,/https:\/\/www\.fnnews\.com\/news\/202611181529418114/);
assert.match(story,/순보유잔고 비중이나 11월 18일 거래비중 순위가 아닙니다/);
assert.equal((story.match(/<a\b/g)||[]).length,1);
assert.doesNotMatch(story,/<script|<input|<iframe|<table/);
const panel = wholePanel.replace(story,'');
const iframe = panel.match(/<iframe\b[^>]*><\/iframe>/g);
assert.equal(iframe.length,1);
assert.match(iframe[0], /src="\.\/assets\/short-local-viewer\.html" sandbox="allow-scripts" loading="lazy" referrerpolicy="no-referrer"/);
assert.doesNotMatch(panel.replace(iframe[0],''), /<(?:script|iframe|table|svg|canvas|button|form|input)\b|\bsrc\s*=|\bfetch\s*\(|short-refresh|short-content/i);
assert.match(panel, /회사별 조회/);
assert.match(panel, /공매도가 많은 종목/);
assert.match(panel, /일부 화면은 KRX 로그인이 필요합니다/);

const links = [...panel.matchAll(/<a href="([^"]+)" target="_blank" rel="noopener noreferrer">([^<]+)<\/a><p>([^<]+)<\/p>/g)];
assert.equal((panel.match(/<a\b/g) || []).length, links.length);
assert.deepEqual(links.map(([, href, label, caption]) => {
  const url = new URL(href);
  assert.equal(url.origin, 'https://data.krx.co.kr');
  assert.match(label, /↗$/);
  return [url.pathname, url.searchParams.get('screenId') || url.searchParams.get('menuId'), caption];
}), [
  ['/comm/srt/srtLoader/index.cmd', 'MDCSTAT300', '종목명 또는 종목코드로 검색해 거래량·거래대금과 순보유잔고를 함께 봅니다.'],
  ['/comm/srt/srtLoader/index.cmd', 'MDCSTAT305', '‘개별추이’에서 종목과 기간을 선택해 잔고 변화를 봅니다.'],
  ['/contents/MDC/MDI/mdiLoader/index.cmd', 'MDC02030204', '공매도 거래대금이 전체 거래대금에서 차지하는 비중 순입니다. 공매도 거래대금 자체의 순위는 아닙니다.'],
  ['/contents/MDC/MDI/mdiLoader/index.cmd', 'MDC02030201', '‘전종목’에서 시장과 날짜를 선택해 종목별 공매도 거래대금을 비교합니다.'],
  ['/contents/MDC/MDI/mdiLoader/index.cmd', 'MDC02030304', '상장주식수 대비 공매도 순보유잔고 수량의 비중 순입니다. 당일 공매도 거래와는 별개입니다.'],
  ['/contents/MDC/MDI/mdiLoader/index.cmd', 'MDC02030303', '종목을 검색해 공시 기준을 충족한 대량보유자를 확인합니다.'],
]);
require('./test_short_local_viewer_vm.cjs');
require('./test_short_local_csv.cjs');
