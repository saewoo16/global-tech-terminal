"""Shared, offline validation and safe merge helpers for the research feed."""
import datetime as dt
import json
import math
from pathlib import Path

ALIASES = {'NYSE:PSTG': 'NYSE:P', 'NYSE:FI': 'NASDAQ:FISV'}
REVENUE_ONLY = {'EURONEXT:AI', 'XETR:HEN3', 'SIX:VACN', 'EURONEXT:SU'}


def number(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        value = float(value)
        return value if math.isfinite(value) else None
    except (ValueError, TypeError):
        return None


def valid_date(value):
    try:
        return isinstance(value, str) and len(value) == 10 and dt.date.fromisoformat(value) <= dt.datetime.now(dt.timezone.utc).date()
    except ValueError:
        return False


def clean_prices(prices):
    points = {}
    for point in prices or []:
        if not isinstance(point, (list, tuple)) or len(point) != 2:
            continue
        day, close = point
        value = number(close)
        if valid_date(day) and value is not None and value > 0:
            points[day] = value
    return [[day, points[day]] for day in sorted(points)]


def merge_quarters(previous, incoming):
    """Keep source-backed values when a provider omits fields; keep real newest periods.

    Entirely empty provider columns are not a reported quarter. Explicit
    not-disclosed rows may carry revenue but must never acquire invented profit.
    """
    result = {}
    for candidate in list(previous or []) + list(incoming or []):
        if not isinstance(candidate, dict) or not valid_date(candidate.get('date')):
            continue
        if not any(number(candidate.get(field)) is not None for field in ('revenue', 'operatingIncome')):
            continue
        q = dict(candidate)
        for field in ('revenue', 'operatingIncome'):
            q[field] = number(q.get(field))
        old = result.get(q['date'])
        if old:
            # A verified filing wins over a later incomplete aggregation response.
            if old.get('sourceType') == 'filing' and q.get('sourceType') != 'filing':
                q = {**q, **old}
            else:
                for field in ('revenue', 'operatingIncome'):
                    if q.get(field) is None and old.get(field) is not None and not q.get('operatingIncomeNotDisclosed'):
                        q[field] = old[field]
                # Do not give an unverified replacement the previous source citation.
        result[q['date']] = q
    return sorted(result.values(), key=lambda q: q['date'], reverse=True)[:4]


def migrate_symbols(stocks):
    for old, new in ALIASES.items():
        if old in stocks:
            previous = stocks.pop(old)
            if new not in stocks:
                stocks[new] = previous
    return stocks


def annotate(symbol, item):
    p = clean_prices(item.get('prices'))
    item['prices'] = p
    item['priceStatus'] = 'complete' if len(p) >= 2 else 'missing'
    if p:
        item['close'] = p[-1][1]
        item['lastPriceDate'] = p[-1][0]
        item.pop('priceNote', None)
    else:
        item['priceNote'] = '제공사에서 유효한 시세를 확보하지 못했습니다.'
    qs = item.get('quarters', [])
    complete = sum(number(q.get('revenue')) is not None and number(q.get('operatingIncome')) is not None for q in qs)
    item['financialStatus'] = 'complete' if len(qs) == 4 and complete == 4 else 'partial' if qs else 'missing'
    if symbol in REVENUE_ONLY or item.get('quarterlyReporting') == 'not_disclosed':
        item['financialStatus'] = 'not_disclosed'
        item.setdefault('financialNote', '분기 매출은 공시되지만 영업이익은 반기·연간으로만 공시되어 분기 영업이익과 OPM은 N/A입니다.')
    elif item['financialStatus'] == 'missing':
        item.setdefault('financialNote', '검증 가능한 분기 실적을 아직 확보하지 못했습니다.')
    elif item['financialStatus'] == 'partial':
        item.setdefault('financialNote', '일부 분기 또는 영업이익이 제공되지 않아 확인된 값만 표시합니다.')
    elif item.get('financialNote') in ('검증 가능한 분기 실적을 아직 확보하지 못했습니다.', '일부 분기 또는 영업이익이 제공되지 않아 확인된 값만 표시합니다.'):
        item.pop('financialNote', None)
    return item


def write_json(path, obj):
    path = Path(path)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(obj, ensure_ascii=False, separators=(',', ':'), allow_nan=False), encoding='utf-8')
    temp.replace(path)
