"""Validate/import independently verified KRX whole-universe outstanding balances.

--entry accepts a normalized evidence-backed snapshot, NOT trading flow, lending,
large-holder counts or an authentication response. No network/login is attempted.
KRW is stored as exact integer strings; displayed ratios preserve source precision.
"""
import argparse
import copy
import json
import re
from datetime import date, datetime, timedelta
from decimal import Decimal
from fractions import Fraction
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
MARKETS = ['KOSPI', 'KOSDAQ']
METRIC = 'net-short-outstanding-balance'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def day(value):
    require(isinstance(value, str) and re.fullmatch(r'\d{4}-\d{2}-\d{2}', value), 'Invalid date')
    return date.fromisoformat(value)


def timestamp(value):
    require(isinstance(value, str), 'observedAt required')
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    require(result.tzinfo is not None, 'observedAt must include timezone')
    return result


def amount(value, positive=False):
    require(isinstance(value, str) and re.fullmatch(r'0|[1-9]\d*', value), 'KRW must be exact nonnegative integer string')
    require(not positive or int(value) > 0, 'Market capitalization must be positive')
    return Decimal(value)


def observation(row, sources):
    balance, cap = amount(row.get('balanceKRW')), amount(row.get('marketCapKRW'), True)
    ratio = row.get('ratioPct')
    require(isinstance(ratio, str) and re.fullmatch(r'\d+(?:\.\d+)?', ratio), 'ratioPct must preserve decimal source precision')
    decimals = len(ratio.split('.')[1]) if '.' in ratio else 0
    # Compare rounded-source tolerance with integers, avoiding Decimal context
    # rounding at the exact half-unit boundary for large KRW totals.
    scale = 10 ** decimals
    source_scaled = int(ratio.replace('.', ''))
    difference = abs(source_scaled * int(cap) - int(balance) * 100 * scale)
    require(2 * difference <= int(cap), 'Ratio inconsistent with same-date balance/market cap')
    if 'balanceShares' in row or 'listedShares' in row:
        quantity, listed = amount(row.get('balanceShares')), amount(row.get('listedShares'), True)
        require(int(balance) * int(listed) == int(quantity) * int(cap), 'Amount/share ratio mismatch')
    timestamp(row.get('observedAt'))
    ids = row.get('sourceIds')
    require(isinstance(ids, list) and ids and all(i in sources for i in ids), 'Valid sourceIds required')


def ranking_codes(rows):
    """Exact amount/ratio top15 union, stable code tie-breaks."""
    amount_top = sorted(rows, key=lambda r: (-int(r['balanceKRW']), r['code']))[:15]
    ratio_top = sorted(rows, key=lambda r: (-Fraction(int(r['balanceKRW']), int(r['marketCapKRW'])), r['code']))[:15]
    return {r['code'] for r in amount_top + ratio_top}


def validate(payload):
    require(payload.get('schemaVersion') == 1, 'Unsupported schemaVersion')
    require(payload.get('metric') == METRIC and payload.get('unit') == 'KRW', 'Only outstanding net short balance KRW supported')
    require(payload.get('investorSplit') == 'unavailable', 'Issuer investor-type balance split is not verified')
    timestamp(payload.get('observedAt'))
    coverage = payload.get('coverage', {})
    require(coverage.get('markets') == MARKETS, 'Combined KOSPI/KOSDAQ universe required')
    rows = payload.get('rows')
    require(isinstance(rows, list), 'rows array required')
    sources = {}
    for source in payload.get('sources', []):
        source_id = source.get('id')
        require(isinstance(source_id, str) and source_id and source_id not in sources, 'Unique source ID required')
        url = urlparse(source.get('url', ''))
        require(url.scheme == 'https' and (url.hostname == 'krx.co.kr' or (url.hostname or '').endswith('.krx.co.kr')) and not url.username and not url.password, 'Official KRX source URL required')
        require(bool(source.get('title')), 'Source title required')
        timestamp(source.get('observedAt'))
        sources[source_id] = source
    require(sources, 'Official source metadata required')
    if payload.get('status') == 'unavailable':
        require(not rows and payload.get('asOf') is None and coverage.get('complete') is False and coverage.get('count') == 0, 'Unavailable must not contain rankings/date claims')
        require(bool(payload.get('note')), 'Unavailable reason required')
        return payload
    require(payload.get('status') == 'verified', 'Unknown status')
    as_of = day(payload.get('asOf'))
    require(timestamp(payload['observedAt']).date() >= as_of, 'Snapshot observation predates balance date')
    require(coverage.get('complete') is True and coverage.get('scope') == 'whole-market' and bool(coverage.get('evidenceNote')), 'Whole-market coverage verification required')
    require(coverage.get('count') == len(rows) and len(rows) >= 30, 'Full universe row count required, not top15-only data')
    counts, seen = dict.fromkeys(MARKETS, 0), set()
    for row in rows:
        require(isinstance(row.get('code'), str) and re.fullmatch(r'[0-9A-Z]{6}', row['code']) and row['code'] not in seen, 'Unique six-character KRX security code required')
        seen.add(row['code'])
        require(row.get('market') in MARKETS and bool(row.get('name')), 'Market and issuer name required')
        counts[row['market']] += 1
        observation(row, sources)
        require(timestamp(row['observedAt']).date() >= as_of, 'Issuer observation predates balance date')
        history = row.get('history', [])
        require(isinstance(history, list), 'history array required')
        dates = []
        for point in history:
            current = day(point.get('date'))
            require(current <= as_of, 'History date after asOf')
            observation(point, sources)
            require(timestamp(point['observedAt']).date() >= current, 'Historical observation predates balance date')
            dates.append(current)
            if current == as_of:
                require(all(point[k] == row[k] for k in ('balanceKRW', 'marketCapKRW', 'ratioPct')), 'Current history must equal snapshot')
        require(dates == sorted(set(dates)), 'History dates must be unique and sorted')
    require(all(counts.values()) and coverage.get('countByMarket') == counts, 'Both market coverage counts must match')
    if coverage.get('historyScope') == 'current-ranking-union':
        selected = ranking_codes(rows)
        require(coverage.get('historySecurityCount') == len(selected), 'Historical selection count mismatch')
        require(all(not r.get('history') for r in rows if r['code'] not in selected), 'Only selected ranking-union histories may be embedded')
    return payload


def change(row, as_of, days):
    """Calendar week/month proxy: actual most recent observation on/before target.
    Missing or zero baseline returns None, never a fabricated percent change.
    """
    target = day(as_of) - timedelta(days=days)
    candidates = [p for p in row.get('history', []) if day(p['date']) <= target]
    if not candidates:
        return None
    base = max(candidates, key=lambda p: p['date'])
    if amount(base['balanceKRW']) == 0:
        return None
    return {'date': base['date'], 'pct': str((amount(row['balanceKRW']) / amount(base['balanceKRW']) - 1) * 100)}


def merge(old, incoming):
    validate(incoming)
    if old is not None:
        validate(old)
        require(incoming['status'] == 'verified' or old['status'] != 'verified', 'Never replace verified data with collection failure')
        if old['status'] == incoming['status'] == 'verified':
            require(incoming['asOf'] >= old['asOf'], 'Do not regress snapshot date')
            # Retain historical observations unless independently reverified corrections supplied.
            result = copy.deepcopy(incoming)
            source_map = {s['id']: s for s in old['sources']}
            for source in incoming['sources']:
                require(source['id'] not in source_map or source_map[source['id']] == source, 'Use a new source ID for revised evidence')
                source_map[source['id']] = source
            result['sources'] = list(source_map.values())
            previous = {r['code']: r for r in old['rows']}
            for row in result['rows']:
                prior = previous.get(row['code'])
                if not prior:
                    continue
                history = {p['date']: p for p in prior.get('history', [])}
                history[old['asOf']] = {k: prior[k] for k in ('balanceKRW', 'marketCapKRW', 'ratioPct', 'observedAt', 'sourceIds')}
                history[old['asOf']]['date'] = old['asOf']
                for field in ('balanceShares', 'listedShares'):
                    if field in prior:
                        history[old['asOf']][field] = prior[field]
                history.update({p['date']: p for p in row.get('history', [])})
                if old['asOf'] == result['asOf']:
                    history.pop(old['asOf'], None)
                row['history'] = [history[d] for d in sorted(history)]
            if result['coverage'].get('historyScope') == 'current-ranking-union':
                selected = ranking_codes(result['rows'])
                for row in result['rows']:
                    if row['code'] not in selected:
                        row['history'] = []
                result['coverage']['historySecurityCount'] = len(selected)
            return validate(result)
    return incoming


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--entry', help='Independently verified normalized official snapshot JSON')
    parser.add_argument('--path', default=str(ROOT / 'data/korean_short_balance.json'))
    args = parser.parse_args()
    path = Path(args.path)
    old = json.loads(path.read_text()) if path.exists() else None
    if not args.entry:
        validate(old or {})
        print('Short balance snapshot validated (status: ' + old['status'] + ').')
        return
    result = merge(old, json.loads(Path(args.entry).read_text()))
    if result == old:
        print('No changed verified short balance data.')
        return
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    tmp.replace(path)
    print('Verified short balance snapshot imported.')


if __name__ == '__main__':
    main()
