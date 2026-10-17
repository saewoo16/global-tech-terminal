"""Broader source-defined theme universes with independently labeled amount coverage.

Membership and market-cap ranking are verified, dated snapshots. Flow refreshes
never silently change those dates or treat uncovered stocks as zero.
"""
import concurrent.futures
import copy
import datetime
import json
import urllib.request
from decimal import Decimal
from pathlib import Path

R = Path(__file__).resolve().parents[1] / 'data'
PERIODS = {'1d': ('DAY', '일간'), '1w': ('WEEK', '주간'), '1m': ('MONTH', '월간')}
INVESTORS = {'foreign': 'FOREIGNER', 'institution': 'ORGANIZATION'}


def build(refresh=False, previous=None, responses=None):
    membership = json.loads((R / 'korea-theme-membership.json').read_text())
    definitions = json.loads((R / 'korea-theme-definitions.json').read_text())
    assert membership['schemaVersion'] == 2
    assert definitions == {b['name']: b['memberCodes'] for b in membership['themes']}
    if responses is None:
        def fetch(job):
            market, investor, period = job
            url = ('https://stock.naver.com/api/domestic/market/trend/trendForeignOrg'
                   f'?investorType={investor}&tradeType=KRX&marketType={market}'
                   f'&startIdx=0&pageSize=100&periodType={period}')
            with urllib.request.urlopen(url, timeout=40) as response:
                data = json.load(response)
            return f'{market}_{investor}_{period}', {'url': url, 'data': data}
        jobs = [(m, i, p[0]) for m in ('KOSPI', 'KOSDAQ')
                for i in INVESTORS.values() for p in PERIODS.values()]
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            responses = dict(pool.map(fetch, jobs))
    sources = {s['id']: copy.deepcopy(s) for s in membership['sources']}
    flows, periods = {}, {}
    for key, (api_period, label) in PERIODS.items():
        dates = set()
        for investor, api_investor in INVESTORS.items():
            rows = {}
            for market in ('KOSPI', 'KOSDAQ'):
                obj = responses[f'{market}_{api_investor}_{api_period}']
                for side in ('buyRankList', 'sellRankList'):
                    for raw in obj['data']['sections'][side]:
                        if raw['type'] != 'ST':
                            continue
                        code = raw['itemcode']
                        assert code not in rows, ('duplicate amount code', code)
                        amount = raw['accTradeAmount']
                        assert not isinstance(amount, bool)
                        number = Decimal(str(amount))
                        assert number.is_finite() and number == number.to_integral_value()
                        sid = f'naver-{market.lower()}-{investor}-{api_period.lower()}-{raw["bizdateTo"]}'
                        rows[code] = {'code': code, 'netBuyKRW': int(number), 'sourceId': sid}
                        dates.add((raw['bizdateFrom'], raw['bizdateTo']))
                        sources[sid] = {'id': sid, 'title': f'NAVER {market} {label} {investor} 순매수·순매도 금액',
                                        'url': obj['url'], 'note': 'KRX 조회, 매수·매도 각 상위100. 실제 기간 순매수대금(원). 순위 밖 금액은 미확인.'}
            assert rows, ('empty amount response', key, investor)
            flows[key, investor] = rows
        assert len(dates) == 1, ('Mixed provider period windows', key, dates)
        start, end = next(iter(dates))
        iso = lambda value: datetime.datetime.strptime(value, '%Y%m%d').date().isoformat()
        periods[key] = {'apiPeriod': api_period, 'label': label, 'from': iso(start), 'to': iso(end)}
    assert len({p['to'] for p in periods.values()}) == 1, 'Mixed provider as-of dates'
    result = {k: copy.deepcopy(membership[k]) for k in ('basketDefinitionVersion', 'classificationType', 'membershipAsOf', 'marketCapAsOf', 'marketCapPolicy', 'marketCapDateEvidence', 'membershipCounts', 'notes')}
    result.update({'schemaVersion': 2, 'asOf': periods['1d']['to'],
                   'collectedAt': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                   'periods': periods, 'sources': list(sources.values()), 'baskets': [],
                   'membershipVerification': 'provider_full_constituent_lists_count_matched'})
    for definition in membership['themes']:
        basket = copy.deepcopy(definition)
        members = [copy.deepcopy(membership['members'][c]) for c in definition['memberCodes']]
        members.sort(key=lambda m: (-m['marketCapKRW'], m['code']))
        basket.update({'members': members, 'displayMembers': members[:3], 'marketCapAsOf': membership['marketCapAsOf'], 'flows': {}})
        for key in PERIODS:
            basket['flows'][key] = {}
            for investor in INVESTORS:
                available = flows[key, investor]
                components = [copy.deepcopy(available.get(m['code'], {'code': m['code'], 'netBuyKRW': None, 'sourceId': None})) for m in members]
                known = [r for r in components if r['netBuyKRW'] is not None]
                missing = [r['code'] for r in components if r['netBuyKRW'] is None]
                subtotal = sum(r['netBuyKRW'] for r in known) if known else None
                total = None if missing else subtotal
                basket['flows'][key][investor] = {'status': 'missing_constituent_amounts' if missing else 'complete',
                    'netBuyKRW': total, 'netBuyEok': None if total is None else total / 1e8,
                    'knownSubtotalKRW': subtotal, 'knownSubtotalEok': None if subtotal is None else subtotal / 1e8,
                    'rank': None, 'availableCount': len(known), 'expectedCount': len(members),
                    'missingMembers': missing, 'memberFlows': components,
                    'sourceIds': sorted({r['sourceId'] for r in known})}
        result['baskets'].append(basket)
    return result


def normalize(result, dates, previous=None):
    """Share full constituent evidence once, keeping per-period exact amount audits."""
    version = result['basketDefinitionVersion']
    def absent(day):
        return {'status': 'unavailable', 'rows': [], 'sourceIds': [], 'coverage': {'start': day, 'end': day},
                'note': '이 날짜의 확장 테마 수급은 미확보입니다. 최신 1일·주간·월간으로 전환해 주세요.'}
    def period(key):
        info = result['periods'][key]
        rows, ids = [], set()
        complete = {i: 0 for i in INVESTORS}
        for basket in result['baskets']:
            row = {'id': basket['id'], 'name': basket['name'], 'memberCount': basket['memberCount'], 'coverage': {}}
            for investor in INVESTORS:
                cell = copy.deepcopy(basket['flows'][key][investor])
                row[investor] = cell['netBuyEok']
                row['coverage'][investor] = cell
                ids.update(cell['sourceIds'])
                complete[investor] += cell['status'] == 'complete'
            rows.append(row)
        count = len(rows)
        return {'status': 'verified' if all(v == count for v in complete.values()) else 'partial',
                'rows': rows, 'sourceIds': sorted(ids), 'basketDefinitionVersion': version,
                'membershipAsOf': result['membershipAsOf'], 'marketCapAsOf': result['marketCapAsOf'],
                'coverage': {'start': info['from'], 'end': info['to'], 'count': count,
                             'note': f"전체 금액 확보: 외국인 {complete['foreign']}/{count} · 기관 {complete['institution']}/{count}개 테마. 나머지는 확인분 부분합."},
                'note': 'NAVER 공개 테마·업종 전체 목록의 합집합에서 테마 내 중복을 제거했습니다. 구성종목 한 개라도 금액이 미확인이면 전체 합계는 비우고 확인된 종목의 부분합을 따로 표시합니다. 매수·매도 각 상위100 API 한계로 누락은 0이 아니며 부분합의 방향도 전체와 다를 수 있습니다. 현재 구성으로 기간 수급을 집계하며 과거 편입·편출은 소급 복원하지 않습니다.'}
    daily = {day: value for day, value in (previous or {}).get('daily', {}).items() if value.get('basketDefinitionVersion') == version}
    daily[result['asOf']] = period('1d')
    catalog = [{k: copy.deepcopy(b[k]) for k in ('id', 'name', 'memberCount', 'members', 'displayMembers', 'marketCapAsOf', 'sourceCategories', 'scopeNote', 'excludedMembers', 'providerUnionCount')} for b in result['baskets']]
    metadata = {k: copy.deepcopy(result[k]) for k in ('basketDefinitionVersion', 'membershipAsOf', 'marketCapAsOf', 'marketCapPolicy', 'marketCapDateEvidence', 'membershipCounts', 'membershipVerification')}
    return {**metadata, 'unit': '억원', 'dates': dates, 'daily': {d: daily.get(d, absent(d)) for d in dates},
            'aggregate5d': period('1w'), 'monthly': period('1m'), 'baskets': catalog,
            'methodology': 'NAVER 테마·업종 분류를 기준으로 범위를 확장했습니다. 수급은 전체 구성종목을 대상으로 확인하며, 괄호에는 시총 상위 3개만 표시합니다. 대기업·사업노출 기업도 포함하며 순수 테마 전문기업만의 집계가 아닙니다.',
            'classification': result['classificationType'], 'notes': result['notes']}
