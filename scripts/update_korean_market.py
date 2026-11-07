"""Incrementally refresh verified Korean market series while preserving good data.

Public, unauthenticated read-only requests only. Static ranking/thematic/index
snapshots keep their own real observation dates until independently refreshed.
No missing observations are converted to zero. This script never touches the
company explorer, briefings, or other market tabs.
"""
from __future__ import annotations
import copy
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
from urllib.parse import parse_qsl, urlsplit, urlunsplit

from validate_korean_market import validate, valid_date, number
from manage_briefings import validate_document, valid_url
from korean_futures_source import collect_foreign_flows, update_quality, collect_open_interest
from korean_rankings_source import build as collect_rankings, RAW_RESPONSES
from korean_theme_source import build as collect_themes, normalize as normalize_themes

ROOT = Path(__file__).resolve().parents[1]
FILE = ROOT / 'data/korea-market.json'
ARCHIVE = ROOT / 'data/briefings.json'
FLOW_MARKETS = ('KOSPI', 'KOSDAQ')
FLOW_FIELDS = ('foreign', 'institution', 'individual', 'otherForeign', 'otherCorporation')
MAX_FLOW_CONFLICTS = 20
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


def _dated_rows(rows, label):
    if not isinstance(rows, list):
        raise ValueError(f'{label}: rows must be an array')
    indexed = {}
    for row in rows:
        if not isinstance(row, dict) or not valid_date(row.get('date')):
            raise ValueError(f'{label}: invalid observation date')
        if row['date'] in indexed:
            raise ValueError(f'{label}: duplicate observation date {row["date"]}')
        indexed[row['date']] = row
    return indexed


def merge_series(section, rows, cutoff, *, protected_dates=()):
    """Preserve whole protected rows, including history outside the rolling window.

    Archive-derived dates are supplied by the cash-flow caller. Existing explicit
    snapshot policies remain protected for every series. Validate and build a
    candidate before changing the caller's section, including its coverage.
    """
    if not rows:
        raise ValueError('empty observation result')
    if not valid_date(cutoff):
        raise ValueError('invalid history cutoff')
    merged = _dated_rows(section.get('rows', []), 'stored series')
    incoming = _dated_rows(rows, 'incoming series')
    protected = set(protected_dates) | {day for day, row in merged.items() if row.get('snapshotPolicy')}
    if not protected.issubset(merged):
        raise ValueError('protected observation missing from stored series')
    for day, row in incoming.items():
        if day not in protected:
            merged[day] = row
    kept = [row for day, row in sorted(merged.items()) if day >= cutoff or day in protected]
    if not kept:
        raise ValueError('history cutoff would remove every observation')
    coverage = dict(section['coverage'])
    coverage.update(start=kept[0]['date'], end=kept[-1]['date'], count=len(kept))
    section.update(rows=kept, coverage=coverage, status='verified')


def _source_ids(owner):
    ids = owner.get('sourceIds', [])
    if not isinstance(ids, list) or any(not isinstance(sid, str) or not sid for sid in ids):
        raise ValueError('malformed cash-flow sourceIds')
    if len(set(ids)) != len(ids):
        raise ValueError('duplicate cash-flow sourceIds')
    if 'sourceId' in owner:
        sid = owner['sourceId']
        if not isinstance(sid, str) or not sid:
            raise ValueError('malformed cash-flow sourceId')
        ids = [*ids, sid] if sid not in ids else ids
    return ids


def _flow_source_scope(url, market):
    if not valid_url(url):
        raise ValueError('unsafe or missing cash-flow source URL')
    parsed = urlsplit(url)
    if parsed.hostname == 'stock.naver.com' and parsed.path == '/api/domestic/market/trend/daily':
        pairs = parse_qsl(parsed.query, keep_blank_values=True)
        query = dict(pairs)
        if len(query) != len(pairs) or query.get('tradeType') != 'KRX' or query.get('marketType') != market:
            raise ValueError('cash-flow source market/tradeType mismatch')
        bizdate = query.get('bizdate', '')
        if len(bizdate) != 8 or not valid_date(f'{bizdate[:4]}-{bizdate[4:6]}-{bizdate[6:]}'):
            raise ValueError('invalid cash-flow source query date')
        if any(not query.get(key, '').isdigit() for key in ('startIdx', 'pageSize')) or int(query['pageSize']) < 1:
            raise ValueError('invalid cash-flow source pagination')
        # A rolling endpoint's query window and page are not its observation date.
        # Legacy rows may reference a later retrieval of the same dated values.
        for key in ('bizdate', 'startIdx', 'pageSize'):
            query.pop(key, None)
        return (parsed.scheme, parsed.netloc, parsed.path, tuple(sorted(query.items())))
    return urlunsplit(parsed)


def _timestamp(value):
    try:
        stamp = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if stamp.tzinfo is None:
            raise ValueError('timezone required')
        return stamp
    except (AttributeError, TypeError, ValueError) as exc:
        raise ValueError('cash-flow observation timestamp needs an ISO timezone') from exc


def _observation_times(row, sources=()):
    """Prefer explicit observation times, using retrieval only as legacy evidence.

    A subsequent retrieval is a separate event when observedAt is known. Check
    every supplied timestamp's format without requiring those events to coincide.
    """
    for owner in (row, *sources):
        for name in ('observedAt', 'retrievedAt'):
            if name in owner:
                _timestamp(owner[name])
    for name in ('observedAt', 'retrievedAt'):
        if name in row:
            return {_timestamp(row[name])}
        recorded = {_timestamp(source[name]) for source in sources if name in source}
        if recorded:
            return recorded
    return set()


def archived_flow_dates(payload, archive):
    """Validate every sourced KR archive row before permitting any refresh.

    Partial briefs and rows lacking snapshotPolicy still define published
    observations. Never reconstruct missing rows or repair an existing mismatch
    here. Missing legacy row timestamps are left missing, not backfilled.
    """
    validate_document(archive)
    if not any(entry['market'] == 'KR' for entry in archive['entries']):
        raise ValueError('KR cash-flow archive is missing')
    flows = payload['flows']
    if flows.get('unit') != '억원':
        raise ValueError('cash-flow unit must be 억원')
    sources = payload.get('sources', [])
    source_index = {source['id']: source for source in sources}
    if len(source_index) != len(sources):
        raise ValueError('duplicate stored source IDs')
    stored = {market: _dated_rows(flows['markets'][market]['rows'], market) for market in FLOW_MARKETS}
    protected = {market: set() for market in FLOW_MARKETS}
    for entry in archive['entries']:
        if entry['market'] != 'KR':
            continue
        section = entry.get('flows', {})
        # Flows are optional in partial briefs. No section (or an empty object)
        # makes no cash-flow claim and must not unprotect existing observations.
        if section == {}:
            continue
        if not isinstance(section, dict) or not isinstance(section.get('rows'), list):
            raise ValueError('KR archive cash-flow rows are missing')
        if section.get('unit') != flows['unit']:
            raise ValueError(f'{entry["date"]}: archive cash-flow unit mismatch')
        archive_sources = {source['id']: source for source in entry['sources']}
        section_ids = _source_ids(section)
        if section_ids and not section['rows']:
            raise ValueError(f'{entry["date"]}: sourced archive cash-flow rows are missing')
        seen = set()
        for row in section['rows']:
            market, day = row.get('market'), entry['date']
            if market not in stored or market in seen:
                raise ValueError(f'{day}: invalid or duplicate archive cash-flow market')
            seen.add(market)
            if row.get('date', day) != day:
                raise ValueError(f'{market} {day}: archive observation date mismatch')
            for owner in (row, flows['markets'][market]):
                if owner.get('unit', flows['unit']) != flows['unit']:
                    raise ValueError(f'{market} {day}: cash-flow unit mismatch')
            current = stored[market].get(day)
            if current is None:
                raise ValueError(f'{market} {day}: archived observation missing from stored series')
            if current.get('unit', flows['unit']) != flows['unit']:
                raise ValueError(f'{market} {day}: stored cash-flow unit mismatch')
            for field in FLOW_FIELDS:
                if field not in row:
                    if field in FLOW_FIELDS[:3]:
                        raise ValueError(f'{market} {day}: archive category missing: {field}')
                    continue
                value = row[field]
                if value is not None and not number(value):
                    raise ValueError(f'{market} {day}: invalid archive category: {field}')
                if field not in current or (current[field] is not None and not number(current[field])) or current[field] != value:
                    raise ValueError(f'{market} {day}: archive cash-flow mismatch: {field}')
            ids = _source_ids(row) or section_ids
            if not ids or any(sid not in archive_sources for sid in ids):
                raise ValueError(f'{market} {day}: missing or unknown archive cash-flow sources')
            # Section-level references usually cover both markets. Select the
            # matching provider scope without mistaking the other market for it.
            matching = []
            for sid in ids:
                source = archive_sources[sid]
                try:
                    scope = _flow_source_scope(source['url'], market)
                except ValueError:
                    # Only a valid reference to the other market can be skipped.
                    # Malformed URLs or NXT scope must never disappear silently.
                    other_market = next(item for item in FLOW_MARKETS if item != market)
                    _flow_source_scope(source['url'], other_market)
                    if sid in _source_ids(row):
                        raise
                    continue
                matching.append((sid, source, scope))
            if not matching:
                raise ValueError(f'{market} {day}: archive source market mismatch')
            scopes = {scope for _, _, scope in matching}
            current_ids = _source_ids(current)
            if any(sid not in ids or sid not in source_index for sid in current_ids):
                raise ValueError(f'{market} {day}: stored/archive source ID mismatch')
            current_urls = ([current['source']] if 'source' in current else []) + [source_index[sid]['url'] for sid in current_ids]
            if not current_urls:
                current_urls = [source_index[sid]['url'] for sid in _source_ids(flows['markets'][market]) if sid in source_index]
                # A section may cite historical snapshots in both markets.
                current_urls = [url for url in current_urls if any(url == source['url'] for _, source, _ in matching)]
            if not current_urls or any(_flow_source_scope(url, market) not in scopes for url in current_urls):
                raise ValueError(f'{market} {day}: stored/archive source provenance mismatch')
            if 'source' in row and _flow_source_scope(row['source'], market) not in scopes:
                raise ValueError(f'{market} {day}: archive row source mismatch')
            expected_times = _observation_times(row, [source for _, source, _ in matching])
            actual_times = _observation_times(current, [source_index[sid] for sid in current_ids])
            if expected_times and actual_times and expected_times.isdisjoint(actual_times):
                raise ValueError(f'{market} {day}: stored/archive observation timestamp mismatch')
            protected[market].add(day)
    if not all(protected.values()):
        raise ValueError('KR cash-flow archive must retain sourced observations for each market')
    return protected


def merge_flow_observations(section, rows, cutoff, protected_dates):
    """Return a complete market candidate and bounded, explicitly unapplied revisions."""
    old = _dated_rows(section['rows'], 'stored cash flows')
    incoming = _dated_rows(rows, 'incoming cash flows')
    frozen = set(protected_dates) | {day for day, row in old.items() if row.get('snapshotPolicy')}
    conflicts = []
    applied = []
    for day, row in sorted(incoming.items()):
        for field in FLOW_FIELDS:
            if field not in row or not number(row[field]):
                raise ValueError(f'{day}: collected cash-flow category missing or invalid: {field}')
        if not valid_url(row.get('source')):
            raise ValueError(f'{day}: collected cash-flow source missing')
        _timestamp(row.get('retrievedAt'))
        if day in frozen:
            previous = old.get(day)
            if previous is None:
                raise ValueError(f'{day}: protected cash-flow observation missing')
            changed = [field for field in FLOW_FIELDS if field not in previous or previous[field] != row[field]]
            if changed:
                conflicts.append({'date': day, 'action': 'not_applied', 'reason': 'published_snapshot_preserved',
                    'unit': '억원', 'source': row['source'], 'retrievedAt': row['retrievedAt'],
                    'changedFields': changed,
                    'incomingValues': {field: row[field] for field in FLOW_FIELDS},
                    'preservedValues': {field: previous[field] for field in FLOW_FIELDS if field in previous}})
        elif row != old.get(day) and day >= cutoff:
            applied.append(day)
    candidate = copy.deepcopy(section)
    merge_series(candidate, rows, cutoff, protected_dates=protected_dates)
    if not applied:
        candidate['status'] = section['status']
    if any(row.get(field) is None for row in candidate['rows'] if row['date'] in frozen for field in FLOW_FIELDS):
        candidate['status'] = 'partial'
    return candidate, {'appliedObservationDates': applied, 'preservedDates': sorted(set(incoming) & frozen),
        'notAppliedCount': len(conflicts), 'notApplied': conflicts[-MAX_FLOW_CONFLICTS:],
        'omittedOlderConflicts': max(0, len(conflicts) - MAX_FLOW_CONFLICTS)}


def collect_flows(market, today):
    result = []
    for page in range(2):
        url = f'https://stock.naver.com/api/domestic/market/trend/daily?tradeType=KRX&marketType={market}&bizdate={today.replace("-", "")}&startIdx={page}&pageSize=30'
        obj = json.loads(fetch(url))
        retrieved_at = datetime.now(timezone.utc).isoformat()
        if not isinstance(obj.get('content'), list) or not obj['content']:
            raise ValueError('daily flow schema/empty content')
        for row in obj['content']:
            day = datetime.strptime(row['bizdate'], '%Y%m%d').date().isoformat()
            if day > today:
                raise ValueError('future observation rejected')
            values = {part['investorGubun']: as_number(part['diffValue']) for part in row['netAmounts']}
            if len(values) != len(row['netAmounts']):
                raise ValueError('duplicate investor category')
            required = {'9000', '9001', '8000', '7100', *INSTITUTIONS}
            if not required.issubset(values):
                raise ValueError('missing investor category; refusing zero fill')
            result.append({'date': day, 'foreign': values['9000']/1e8, 'institution': sum(values[key] for key in INSTITUTIONS)/1e8, 'individual': values['8000']/1e8, 'otherForeign': values['9001']/1e8, 'otherCorporation': values['7100']/1e8, 'source': url, 'retrievedAt': retrieved_at})
    dates = [row['date'] for row in result]
    if len(set(dates)) != len(dates):
        raise ValueError('duplicate daily flow observation')
    return sorted(result, key=lambda row: row['date'])


def direct_official_credit_splits(balance, release):
    """Verify actual same-day market splits against a directly observed official total.

    This narrow path is independent of delayed CSV mirrors. It neither estimates
    a missing market nor revises deposits, dates, or any other market panel.
    """
    empty = {'creditKOSPI': [], 'creditKOSDAQ': []}
    if not release: return empty
    day = release.get('date')
    datetime.strptime(day, '%Y-%m-%d')
    if release.get('url') != 'https://freesis.kofia.or.kr/stat/main.do' or release.get('unit') != 'million KRW':
        raise ValueError('Direct official FreeSIS total with explicit units required')
    def whole(value):
        number = as_number(value)
        if number <= 0 or not number.is_integer(): raise ValueError('Positive integer million-KRW balance required')
        return int(number)
    total = whole(release.get('officialMarginLoans'))
    values = {}
    for market in ('KOSPI', 'KOSDAQ'):
        matches = [row for row in balance.get('kospiList' if market == 'KOSPI' else 'kosdaqList', []) if row.get('stdDate') == day]
        if len(matches) > 1: raise ValueError('Duplicate same-day market credit observations')
        if not matches: return empty
        values[market] = whole(matches[0].get('sinyong'))
    if abs(sum(values.values()) - total) > 1: return empty
    return {'credit'+market: [{'date': day, 'value': value/100, 'rawMillionKRW': value,
        'sourceId': 'chun-crosschecked', 'verificationMethod': 'same-day direct official KOFIA total',
        'officialSourceUrl': release['url'], 'officialMarginLoansMillionKRW': total,
        'splitMinusOfficialMillionKRW': sum(values.values())-total}]
        for market, value in values.items()}


def _collect_mirrored_liquidity(balance):
    """Cross-check each recent market split against independent KOFIA totals."""
    recent = list(csv.DictReader(io.StringIO(fetch(RECENT))))
    latest = json.loads(fetch(LATEST))['as_of']
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


def collect_liquidity(official_release=None):
    balance = json.loads(fetch(CHUN))
    direct = direct_official_credit_splits(balance, official_release)
    try:
        rows = _collect_mirrored_liquidity(balance)
    except Exception:
        if not all(direct.values()): raise
        # Only the directly verified two-market observation survives mirror failure.
        rows = {'deposits': [], 'creditKOSPI': [], 'creditKOSDAQ': []}
    for key, observations in direct.items():
        combined = {row['date']: row for row in rows[key]}
        combined.update({row['date']: row for row in observations})
        rows[key] = [row for _, row in sorted(combined.items())]
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


def merge_daily_rankings(existing, incoming, day):
    """Keep independently verified, timestamped closing observations intact.

    A later provider aggregation is not a correction of a published press
    snapshot. Revisions to those snapshots need coordinated source review;
    generic refreshes may still fill other sections and add later sessions.
    """
    merged = json.loads(json.dumps(existing))
    for key, value in incoming.items():
        previous = existing.get(key, {})
        coverage = previous.get('coverage', {})
        frozen = previous.get('snapshotPolicy') or (
            previous.get('status') == 'verified'
            and previous.get('sourceIds')
            and coverage.get('start') == coverage.get('end') == day
            and str(coverage.get('snapshotAt', '')).startswith(day + 'T')
        )
        if not frozen:
            merged[key] = normalize_rank(value)
    return merged


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
        target['daily'][day] = merge_daily_rankings(target['daily'].get(day, {}), section, day)
    target['note'] = ('최신 일간·주간·월간 순매수는 NAVER의 실제 기간 금액 응답입니다. '
                      '각 표에 공급사가 반환한 시작일·종료일을 표시하며, 일별 순위 상위종목을 더한 값이 아닙니다. '
                      '과거 기사 스냅샷 및 시장 수급 총액과는 집계시점이 다를 수 있습니다.')
    # Daily observations are an archive, not the provider's rolling week window.
    # Keep all source-dated snapshots; the UI independently selects the latest.
    target['dates'] = sorted(target['daily'])
    target['daily'] = {day: target['daily'][day] for day in target['dates']}
    for key, source in [('aggregate5d', incoming['rankings']['periods']['week']), ('monthly', incoming['rankings']['periods']['month'])]:
        target[key] = {k: normalize_rank(v) for k, v in source.items()}
        target[key]['tradedValue'] = {'status': 'unavailable', 'rows': [], 'sourceIds': [], 'coverage': {}, 'note': '거래대금 상위20은 최신 거래일 일별 자료만 확인했습니다. 주간·월간 거래대금으로 추정하지 않습니다.'}


def main():
    payload = json.loads(FILE.read_text())
    # Fail before collection or any write if the published archive is absent,
    # malformed, or already disagrees with the cash-flow series.
    protected = archived_flow_dates(payload, json.loads(ARCHIVE.read_text()))
    now = datetime.now(timezone.utc)
    today = now.date().isoformat()
    cutoff = (now.date() - timedelta(days=3*366)).isoformat()
    successes, failures, flow_observations = [], [], {}
    for market in FLOW_MARKETS:
        try:
            rows = collect_flows(market, today)
            candidate, diagnostics = merge_flow_observations(payload['flows']['markets'][market], rows, cutoff, protected[market])
            payload['flows']['markets'][market] = candidate
            flow_observations[market] = diagnostics
            if diagnostics['appliedObservationDates']:
                successes.append('flows.'+market)
        except Exception as exc:
            failures.append({'section': 'flows.'+market, 'message': f'{type(exc).__name__}: {exc}'})
    if os.environ.get('SKIP_KR_LIQUIDITY') != '1':
        try:
            release = payload['liquidity'].get('validationSummary', {}).get('latestOfficialRelease', {}) if os.environ.get('OFFICIAL_KR_LIQUIDITY') == '1' else None
            results = collect_liquidity(official_release=release)
            if release is not None:
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
    payload['refresh'] = {'attemptedAt': now.isoformat(), 'status': 'partial' if failures and successes else 'failed' if failures else 'verified', 'refreshedSections': successes, 'failures': failures, 'cashFlowObservations': flow_observations, 'note': '브리핑에 보존된 수급은 원래 값·출처·관측시각을 유지합니다. 재조회 차이는 cashFlowObservations.notApplied에만 기록하며 새 확정치로 적용하지 않습니다. 수급·NAVER 선물 외국인 순매수·고정 12월물 미결제약정·예탁금·신용융자와 순매수 종목을 갱신합니다. 확장 테마의 확인분 수급도 같은 공급사 응답으로 갱신합니다. 구성목록과 시총 순위는 별도 검증 스냅샷의 날짜를 유지합니다. 지수 구성종목 분석은 별도 검증 스냅샷 기준일을 유지합니다.'}
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
