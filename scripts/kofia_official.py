"""Strict parser for official FreeSIS headline statistics (no estimated splits)."""
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
import re
import urllib.request

URL = 'https://freesis.kofia.or.kr/stat/main.do'
RULE_URL = 'https://www.kofia.or.kr/voc/m_113/view.do?answer_seq=2298&voc_id=3009'

class VisibleText(HTMLParser):
    def __init__(self):
        super().__init__(); self.parts = []; self.hidden = 0
    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'): self.hidden += 1
    def handle_endtag(self, tag):
        if tag in ('script', 'style'): self.hidden = max(0, self.hidden - 1)
    def handle_data(self, text):
        if not self.hidden: self.parts.append(text)

def parse(html, observed_at):
    observed = datetime.fromisoformat(observed_at.replace('Z', '+00:00'))
    if observed.tzinfo is None: raise ValueError('Observation must include timezone')
    parser = VisibleText(); parser.feed(html)
    text = ' '.join(' '.join(parser.parts).split())
    announcements = re.findall(r'\[(\d{4}-\d{2}-\d{2})\]\s*신용공여통계관리\s*통계가 발표되었습니다', text)
    if len(set(announcements)) != 1: raise ValueError('Missing or ambiguous official statistical date')
    day = datetime.strptime(announcements[0], '%Y-%m-%d').date()
    local_day = observed.astimezone(timezone(timedelta(hours=9))).date()
    if day > local_day or local_day - day > timedelta(days=14):
        raise ValueError('Future or stale official statistical date')
    values = {}
    for label, key in [('투자자예탁금', 'officialInvestorDeposits'), ('신용융자', 'officialMarginLoans')]:
        matches = re.findall(re.escape(label) + r'\s*백만원\s*\|\s*(\d{1,2})/(\d{1,2})\s+([\d,]+)(?![\d,.])', text)
        if len(matches) != 1: raise ValueError('Missing or ambiguous headline: ' + label)
        month, date, number = matches[0]
        if (int(month), int(date)) != (day.month, day.day): raise ValueError('Headline and announcement dates differ')
        if not re.fullmatch(r'(?:[1-9]\d{0,2}(?:,\d{3})+|[1-9]\d*)', number): raise ValueError('Invalid balance')
        values[key] = int(number.replace(',', ''))
    return {'schemaVersion': 1, 'date': day.isoformat(), 'retrievedAt': observed.isoformat(),
            'url': URL, 'acquisition': 'Official FreeSIS HTML headline', 'unit': 'million KRW',
            **values, 'publicationTimeRule': 'Credit balances next day15:00–18:00; exact deposits release time unverified',
            'ruleSource': RULE_URL}

def response_diagnostic(raw, headers):
    """Bounded diagnostics for this unauthenticated public statistics response.

    No headers containing cookies or credentials are logged. Long opaque values,
    query strings, and input values are redacted from the short HTML excerpts.
    """
    import hashlib
    text = raw.decode(headers.get_content_charset() or 'utf-8', errors='replace')
    def excerpt(value):
        value = re.sub(r'(?i)(value\s*=\s*)[\"\'][^\"\']*[\"\']', r'\1"[redacted]"', value)
        value = re.sub(r'(?i)(https?://[^\s\"\'<>?]+)\?[^\s\"\'<>]*', r'\1?[redacted]', value)
        value = re.sub(r'[A-Za-z0-9_+/=.-]{32,}', '[opaque-redacted]', value)
        return ' '.join(value.split())
    return {'bytes': len(raw), 'contentLength': headers.get('Content-Length'),
            'contentType': headers.get('Content-Type'), 'contentEncoding': headers.get('Content-Encoding'),
            'sha256': hashlib.sha256(raw).hexdigest(), 'hasHtmlEnd': '</html>' in text.lower(),
            'hasBodyEnd': '</body>' in text.lower(), 'hasDepositLabel': '투자자예탁금' in text,
            'hasCreditLabel': '신용융자' in text, 'hasAnnouncement': '신용공여통계관리' in text,
            'prefix': excerpt(text[:400]), 'tail': excerpt(text[-400:])}

def collect(observed_at):
    """Try the official HTTPS and public HTTP endpoints, never disable TLS checks.

    The HTTP alternative is public, unauthenticated market data only. Store its
    actual acquisition URL; never call an incomplete response verified.
    """
    import hashlib
    errors = []
    for url in (URL, URL.replace('https://', 'http://')):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'GlobalTechTerminal/1.0', 'Accept': 'text/html'})
            with urllib.request.urlopen(req, timeout=90) as response:
                if response.status != 200: raise ValueError('Official source did not return HTTP200')
                raw = response.read()
                # Diagnostics only: unchanged strict validation below still decides acceptance.
                import json
                print('FreeSIS response diagnostic: ' + json.dumps(response_diagnostic(raw, response.headers), ensure_ascii=False))
                expected = response.headers.get('Content-Length')
                if expected is not None and len(raw) != int(expected): raise ValueError('Incomplete official response')
                html = raw.decode(response.headers.get_content_charset() or 'utf-8')
                if '</html>' not in html.lower(): raise ValueError('Incomplete official HTML')
                release = parse(html, observed_at)
                release.update(acquisitionUrl=url, transport='https' if url.startswith('https:') else 'http',
                               sourceSha256=hashlib.sha256(raw).hexdigest())
                return release
        except Exception as exc:
            errors.append(type(exc).__name__ + ': ' + str(exc))
    raise ValueError('Official FreeSIS acquisition failed: ' + '; '.join(errors))

def apply(payload, release):
    """Only liquidity and source metadata change; unchanged totals are a true no-op."""
    import copy
    result = copy.deepcopy(payload)
    liquidity = result['liquidity']
    previous = liquidity.get('validationSummary', {}).get('latestOfficialRelease', {})
    if previous.get('date', '') > release['date']: raise ValueError('Official source regressed')
    keys = ('date', 'officialInvestorDeposits', 'officialMarginLoans')
    if all(previous.get(k) == release[k] for k in keys): return result
    source_id = 'kofia-homepage-' + release['date'].replace('-', '')
    source = {'id': source_id, 'title': '금융투자협회 FreeSIS 공식 통계', 'url': URL,
              'retrievedAt': release['retrievedAt']}
    result['sources'] = [s for s in result['sources'] if s['id'] != source_id] + [source]
    section = liquidity['series']['deposits']
    rows = {r['date']: r for r in section['rows']}
    rows[release['date']] = {'date': release['date'], 'value': release['officialInvestorDeposits']/100,
                              'rawMillionKRW': release['officialInvestorDeposits'], 'sourceId': source_id}
    section['rows'] = [row for _, row in sorted(rows.items())]
    section['coverage'].update(start=section['rows'][0]['date'], end=section['rows'][-1]['date'], count=len(section['rows']))
    if source_id not in section['sourceIds']: section['sourceIds'].append(source_id)
    section['sourceStatus'] = 'official'; section['status'] = 'verified'
    section['note'] = f"공식 통계 기준일 {release['date']}. 수집시각 {release['retrievedAt']}. 당일 추정 예탁금을 섞지 않습니다."
    liquidity.setdefault('validationSummary', {})['latestOfficialRelease'] = release
    liquidity['note'] = (f"공식 예탁금·전체 신용융자 기준일 {release['date']}. 전체 신용융자 {release['officialMarginLoans']/100:,.0f}억원. 수집시각 {release['retrievedAt']}. "
                         '시장별 신용잔고는 각각 표시된 검증 기준일을 유지합니다. 공식 총액을 임의로 시장별 배분하지 않습니다.')
    return result
