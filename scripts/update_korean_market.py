"""Incrementally refresh verified Korean market series while preserving good data.

Public, unauthenticated read-only requests only. Static ranking/thematic/index
snapshots keep their own real observation dates until independently refreshed.
No missing observations are converted to zero. This script never touches the
company explorer, briefings, or other market tabs.
"""
from __future__ import annotations
import csv
import io
import json
import math
import os
import sys
import tempfile
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

from validate_korean_market import validate
from korean_futures_source import collect_foreign_flows, update_quality, collect_open_interest
from korean_rankings_source import build as collect_rankings, RAW_RESPONSES
from korean_theme_source import build as collect_themes, normalize as normalize_themes

ROOT = Path(__file__).resolve().parents[1]
FILE = ROOT / 'data/korea-market.json'
INSTITUTIONS = ('1000', '2000', '3000', '3100', '4000', '5000', '6000', '7000')
RECENT = 'https://raw.githubusercontent.com/louco999/korea-margin-tracker/main/data/margin_balance.csv'
LATEST = 'https://raw.githubusercontent.com/louco999/korea-margin-tracker/main/data/latest.json'
CHUN = 'https://chunsystem.com/free/chun-index-score'


def fetch(url):
    request = urllib.request.Request(url, headers={'User-Agent': 'GlobalTechTerminal/1.0 (public market statistics)', 'Accept': 'application/json,text/csv'})
    with urllib.request.urlopen(request, timeout=25) as response:
        return response.read().decode('utf-8-sig')


def as_number(value):
    if isinstance(value, bool):
        raise ValueError('boolean is not a monetary value')
    result = float(value)
    if not math.isfinite(result):
        raise ValueError('non-finite monetary value')
    return result


def merge_series(section, rows, cutoff):
    """Merge real observations without silently revising archived snapshots.

    A stored snapshotPolicy marks a deliberately frozen, sourced observation
    shared with the closing archive. Generic collection cannot update that row
    independently of its archive and explanatory notes. Explicit coordinated
    revisions must replace the snapshot outside this generic merge.
    """
    if not rows:
        raise ValueError('empty observation result')
    merged = {row['date']: row for row in section.get('rows', [])}
    for row in rows:
        if merged.get(row['date'], {}).get('snapshotPolicy'):
            continue
        merged[row['date']] = row
    section['rows'] = [row for day, row in sorted(merged.items()) if day >= cutoff]
    section['coverage'].update(start=section['rows'][0]['date'], end=section['rows'][-1]['date'], count=len(section['rows']))
    section['status'] = 'verified'


def collect_flows(market, today):
    result = []
    for page in range(2):
        url = f'https://stock.naver.com/api/domestic/market/trend/daily?tradeType=KRX&marketType={market}&bizdate={today.replace("-", "")}&startIdx={page}&pageSize=30'
        obj = json.loads(fetch(url))
        if not isinstance(obj.get('content'), list) or not obj['content']:
            raise ValueError('daily flow schema/empty content')
        for row in obj['content']:
            day = datetime.strptime(row['bizdate'], '%Y%m%d').date().isoformat()
            if day > today:
                raise ValueError('future observation rejected')
            values = {part['investorGubun']: as_number(part['diffValue']) for part in row['netAmounts']}
            required = {'9000', '9001', '8000', '7100', *INSTITUTIONS}
            if not required.issubset(values):
                raise ValueError('missing investor category; refusing zero fill')
            result.append({'date': day, 'foreign': values['9000']/1e8, 'institution': sum(values[key] for key in INSTITUTIONS)/1e8, 'individual': values['8000']/1e8, 'otherForeign': values['9001']/1e8, 'otherCorporation': values['7100']/1e8, 'source': url})
    dates = [row['date'] for row in result]
    if len(set(dates)) != len(dates):
        raise ValueError('duplicate daily flow observation')
    return sorted(result, key=lambda row: row['date'])


def collect_liquidity():
    """Cross-check each recent market split against independent KOFIA totals."""
    recent = list(csv.DictReader(io.StringIO(fetch(RECENT))))
    latest = json.loads(fetch(LATEST))['as_of']
    balance = json.loads(fetch(CHUN))
    kospi = {row['stdDate']: round(as_number(row['sinyong'])) for row in balance['kospiList'] if row.get('sinyong') is not None}
    kosdaq = {row['stdDate']: round(as_number(row['sinyong'])) for row in balance['kosdaqList'] if row.get('sinyong') is not None}
    rows = {key: [] for key in ('deposits', 'creditKOSPI', 'creditKOSDAQ')}
    confirmed = [row for row in recent if row.get('source') == 'kofia_api' and row['date'] <= latest]
    if not confirmed or latest not in [row['date'] for row in confirmed]:
        raise ValueError('independent latest KOFIA date not confirmed')
    for row in confirmed:
        day = row['date']
        deposits = as_number(row['investor_deposit'])
        total_million = round(as_number(row['margin_loan']) * 1_000_000)
        if deposits <= 0 or total_million <= 0:
            raise ValueError('invalid nonpositive liquidity balance')
        rows['deposits'].append({'date': day, 'value': round(deposits * 10000, 2), 'sourceId': 'kofia-recent-mirror'})
        if day in kospi and day in kosdaq and abs(kospi[day] + kosdaq[day] - total_million) <= 1:
            for key, values in (('creditKOSPI', kospi), ('creditKOSDAQ', kosdaq)):
                if values[day] <= 0:
                    raise ValueError('invalid per-market balance')
                rows[key].append({'date': day, 'value': values[day]/100, 'sourceId': 'chun-crosschecked'})
    return rows


def official_credit_splits(results, release):
    """Keep mirrored market splits behind the latest directly verified total.

    The primary-source job owns deposits. Never infer a missing market or admit
    a new date on the strength of a mirror's latest-date label alone.
    """
    day = release.get('date')
    total = release.get('officialMarginLoans')
    if not day or not isinstance(total, (int, float)) or isinstance(total, bool) or not math.isfinite(total) or total <= 0:
        raise ValueError('Direct official credit date and total required')
    keys = ('creditKOSPI', 'creditKOSDAQ')
    indexed = {key: {row['date']: row for row in results.get(key, [])} for key in keys}
    dates = sorted(set(indexed[keys[0]]) & set(indexed[keys[1]]))
    accepted = {key: [] for key in keys}
    for observed in dates:
        if observed > day: continue
        values = [as_number(indexed[key][observed]['value']) for key in keys]
        if any(value <= 0 for value in values): continue
        # Earlier rows were independently cross-checked by collect_liquidity.
        if observed == day and abs(sum(values)*100-total) > 1.000001: continue
        for key in keys: accepted[key].append(indexed[key][observed])
    return accepted


def atomic_write(payload, target=FILE):
    errors = validate(payload)
    if errors:
        raise ValueError('\n'.join(errors))
    target.parent.mkdir(exist_ok=True, parents=True)
    with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=target.parent, delete=False) as handle:
        json.dump(payload, handle, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
        handle.write('\n')
        name = handle.name
    os.replace(name, target)


def normalize_rank(section):
    section = json.loads(json.dumps(section))
    section['unit'] = '억원'
    section.setdefault('coverage', {})['universe'] = 'KOSPI + KOSDAQ · 보통주 중심, ST 스팩 포함'
    for row in section.get('rows', []):
        row['value'] = round(row['value'] / 1e8, 6)
    for rows in section.get('byMarket', {}).values():
        for row in rows:
            row['value'] = round(row['value'] / 1e8, 6)
    return section


def update_rankings(payload):
    incoming = collect_rankings(refresh=True)
    if incoming['asOf'] > payload['asOf']:
        raise ValueError('rankings newer than confirmed market-flow date')
    for source in incoming['sources']:
        previous = next((s for s in payload['sources'] if s['id'] == source['id']), None)
        if previous is None:
            payload['sources'].append(source)
        else:
            previous.update(source)
    target = payload['rankings']
    for day, section in incoming['rankings']['daily'].items():
        target['daily'][day] = {key: normalize_rank(value) for key, value in section.items()}
    target['note'] = ('최신 일간·주간·월간 순매수는 NAVER의 실제 기간 금액 응답입니다. '
                      '각 표에 공급사가 반환한 시작일·종료일을 표시하며, 일별 순위 상위종목을 더한 값이 아닙니다. '
                      '과거 기사 스냅샷 및 시장 수급 총액과는 집계시점이 다를 수 있습니다.')
    target['dates'] = sorted(target['daily'])[-5:]
    target['daily'] = {day: target['daily'][day] for day in target['dates']}
    for key, source in [('aggregate5d', incoming['rankings']['periods']['week']), ('monthly', incoming['rankings']['periods']['month'])]:
        target[key] = {k: normalize_rank(v) for k, v in source.items()}
        target[key]['tradedValue'] = {'status': 'unavailable', 'rows': [], 'sourceIds': [], 'coverage': {}, 'note': '거래대금 상위20은 최신 거래일 일별 자료만 확인했습니다. 주간·월간 거래대금으로 추정하지 않습니다.'}


def main():
    payload = json.loads(FILE.read_text())
    now = datetime.now(timezone.utc)
    today = now.date().isoformat()
    cutoff = (now.date() - timedelta(days=3*366)).isoformat()
    successes, failures = [], []
    for market in ('KOSPI', 'KOSDAQ'):
        try:
            rows = collect_flows(market, today)
            merge_series(payload['flows']['markets'][market], rows, cutoff)
            successes.append('flows.'+market)
        except Exception as exc:
            failures.append({'section': 'flows.'+market, 'message': f'{type(exc).__name__}: {exc}'})
    if os.environ.get('SKIP_KR_LIQUIDITY') != '1':
        try:
            results = collect_liquidity()
            if os.environ.get('OFFICIAL_KR_LIQUIDITY') == '1':
                release = payload['liquidity'].get('validationSummary', {}).get('latestOfficialRelease', {})
                results = official_credit_splits(results, release)
            for key, rows in results.items():
                if rows:
                    merge_series(payload['liquidity']['series'][key], rows, cutoff)
                    successes.append('liquidity.'+key)
                else:
                    failures.append({'section': 'liquidity.'+key, 'message': '교차검증된 새 잔고 없음. 이전 관측을 보존했습니다.'})
        except Exception as exc:
            failures.append({'section': 'liquidity', 'message': f'{type(exc).__name__}: {exc}'})
    payload['asOf'] = max(payload['flows']['markets'][market]['coverage']['end'] for market in ('KOSPI', 'KOSDAQ'))
    if payload.get('futures'):
        try:
            future_section = payload['futures']['foreignFlows']
            rows = collect_foreign_flows(payload['asOf'])
            merge_series(future_section, rows, cutoff)
            future_section['asOf'] = future_section['rows'][-1]['date']
            update_quality(future_section)
            successes.append('futures.foreignFlows')
        except Exception as exc:
            failures.append({'section': 'futures.foreignFlows', 'message': f'{type(exc).__name__}: {exc}'})
        try:
            oi_section = payload['futures']['openInterest']
            rows = collect_open_interest(payload['asOf'], oi_section['contractCode'], oi_section['contractName'])
            merge_series(oi_section, rows, cutoff)
            oi_section['asOf'] = oi_section['rows'][-1]['date']
            successes.append('futures.openInterest')
        except Exception as exc:
            failures.append({'section': 'futures.openInterest', 'message': f'{type(exc).__name__}: {exc}'})
    try:
        candidate = json.loads(json.dumps(payload))
        update_rankings(candidate)
        payload = candidate
        successes.append('rankings')
    except Exception as exc:
        failures.append({'section': 'rankings', 'message': f'{type(exc).__name__}: {exc}'})
    try:
        themes = collect_themes(responses=RAW_RESPONSES or None)
        if themes['asOf'] != payload['rankings']['dates'][-1]:
            raise ValueError('theme and stock ranking observation dates differ')
        for source in themes['sources']:
            if source['id'] not in {s['id'] for s in payload['sources']}:
                payload['sources'].append(source)
        payload['themes'] = normalize_themes(themes, payload['rankings']['dates'], payload.get('themes'))
        successes.append('themes')
    except Exception as exc:
        failures.append({'section': 'themes', 'message': f'{type(exc).__name__}: {exc}'})
    payload['refresh'] = {'attemptedAt': now.isoformat(), 'status': 'partial' if failures and successes else 'failed' if failures else 'verified', 'refreshedSections': successes, 'failures': failures, 'note': '수급·NAVER 선물 외국인 순매수·고정 12월물 미결제약정·예탁금·신용융자와 순매수 종목을 갱신합니다. 확장 테마의 확인분 수급도 같은 공급사 응답으로 갱신합니다. 구성목록과 시총 순위는 별도 검증 스냅샷의 날짜를 유지합니다. 지수 구성종목 분석은 별도 검증 스냅샷 기준일을 유지합니다.'}
    if successes:
        payload['updatedAt'] = now.isoformat()
        payload['asOf'] = max(payload['flows']['markets'][market]['coverage']['end'] for market in ('KOSPI', 'KOSDAQ'))
        payload['requestedWindow']['end'] = payload['asOf']
    atomic_write(payload)
    print(json.dumps(payload['refresh'], ensure_ascii=False))
    if failures:
        print('Some Korean market fetches failed; previous observations retained. See data refresh status.', file=sys.stderr)


if __name__ == '__main__':
    main()
