#!/usr/bin/env python3
"""Import the retained Nov 6 KRX money observations, without network or publication.

The all-market CSV and individually observed missing rows are distinct snapshots.
Absence is never zero. --require-complete rejects any unverified theme member.
The pre-import public daily observation is immutable evidence, not a bad source.
"""
import argparse
import copy
import csv
import datetime as dt
import hashlib
import io
import json
import re
from pathlib import Path

from korean_rankings_source import preferred

ROOT = Path(__file__).resolve().parents[1]
DAY = '2026-11-06'
STAMP = '20261106'
EVIDENCE = ROOT / 'data/korea-krx-evidence-20261106'
PUBLIC = EVIDENCE / 'previous-public-daily-snapshot.json'
WHO = {'foreign': '외국인', 'institution': '기관합계'}
INDIVIDUAL_URL = 'https://data.krx.co.kr/contents/MDC/MDI/mdiLoader/index.cmd?menuId=MDC0201020302'
INVESTOR_ROWS = ['금융투자', '보험', '투신', '사모', '은행', '기타금융', '연기금 등',
                 '기관합계', '기타법인', '개인', '외국인', '기타외국인', '전체']
FINAL_NOTE = ('KRX states regular-market data are scheduled after 15:45 KST and final data '
              'including after-hours after 20:00 KST. Nov 6 was queried on Nov 8. '
              'These are actual observations after the scheduled time, not a provider final-status flag.')
SCOPE_NOTE = ('11/6 하루 KRX 공식 원 단위 실제 순매수대금이며 11/8 관측값입니다. '
              '외국인은 기타외국인을 제외하고 기관은 기관합계입니다. NXT는 포함하지 않습니다. '
              'KRX 안내상 시간외 포함 최종 매매내역 제공 예정은 당일 20시이며, '
              '예정시각 경과만으로 별도 최종확정 플래그를 부여하지 않습니다.')


def digest(obj):
    return hashlib.sha256(json.dumps(obj, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def write(path, obj, compact=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, allow_nan=False,
                               **({'separators': (',', ':')} if compact else {'indent': 2})) + '\n')


def integer(value):
    if not re.fullmatch(r'-?(?:\d+|\d{1,3}(?:,\d{3})+)', value):
        raise ValueError(f'Not an explicit integer: {value!r}')
    return int(value.replace(',', ''))


def observed(value):
    parsed = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
    assert parsed.tzinfo and parsed.date().isoformat() == '2026-11-08', value
    return value


def load_bulk(folder, manifest):
    assert manifest['asOf'] == manifest['start'] == manifest['end'] == DAY
    assert manifest['market'] == 'ALL' and manifest['unit'] == 'KRW'
    assert manifest['sourceScreen'] == '12010' and manifest['encoding'] == 'CP949'
    result = {}
    for who, investor in manifest['investors'].items():
        assert who in WHO
        assert investor['investorCode'] == {'foreign': '9000', 'institution': '7050'}[who]
        data = (folder / investor['file']).read_bytes()
        assert hashlib.sha256(data).hexdigest() == investor['sha256']
        rows = list(csv.DictReader(io.StringIO(data.decode('cp949'))))
        assert len(rows) == investor['rowCount']
        source_id = f'krx-{who}-csv-{STAMP}'
        amounts = {}
        for row in rows:
            code = row['종목코드']
            assert code not in amounts
            values = [integer(row['거래대금_' + k]) for k in ('매도', '매수', '순매수')]
            volume = [integer(row['거래량_' + k]) for k in ('매도', '매수', '순매수')]
            assert all(v >= 0 for v in values[:2] + volume[:2]), (who, code, 'negative gross value')
            assert values[1] - values[0] == values[2], (who, code, 'money')
            assert volume[1] - volume[0] == volume[2], (who, code, 'volume')
            amounts[code] = {'code': code, 'name': row['종목명'], 'netBuyKRW': values[2],
                             'netBuyVolume': volume[2], 'sellKRW': values[0], 'buyKRW': values[1],
                             'sourceId': source_id, 'sourceScreen': '12010',
                             'observedAt': observed(investor['observedAt'])}
        result[who] = amounts
    assert set(result) == set(WHO)
    return result


def parse_individual(record):
    assert record['start'] == record['end'] == STAMP
    assert record['money'] == '원' and record['queryType'] == '1'
    assert record['stock'].split('/')[0] == record['code']
    observed(record['observedAt'])
    assert len(record['tables']) == 1
    lines = record['tables'][0].strip().splitlines()
    assert lines[0].split('\t') == ['투자자구분', '매도', '매수', '순매수', '매도', '매수', '순매수']
    assert len(lines) == 14
    rows = {}
    for line in lines[1:]:
        fields = line.split('\t')
        assert len(fields) == 7 and fields[0] not in rows
        values = [integer(v) for v in fields[1:]]
        assert all(values[i] >= 0 for i in (0, 1, 3, 4))
        assert values[1] - values[0] == values[2]
        assert values[4] - values[3] == values[5]
        rows[fields[0]] = values
    assert list(rows) == INVESTOR_ROWS
    assert [sum(rows[name][i] for name in INVESTOR_ROWS[:7]) for i in range(6)] == rows['기관합계']
    assert [sum(rows[name][i] for name in INVESTOR_ROWS[7:12]) for i in range(6)] == rows['전체']
    assert rows['전체'][2] == rows['전체'][5] == 0
    return {who: {'code': record['code'], 'name': record['stock'].split('/', 1)[1],
                  'netBuyKRW': rows[label][5], 'netBuyVolume': rows[label][2],
                  'sellKRW': rows[label][3], 'buyKRW': rows[label][4],
                  'sourceId': f'krx-{who}-individual-{STAMP}', 'sourceScreen': '12009',
                  'observedAt': record['observedAt']}
            for who, label in WHO.items()}


def load_individual(folder):
    merged = {}
    paths = sorted(folder.glob('individual-batch-*.json'))
    if not paths:
        paths = [folder / 'individual-flow-checks.json'] if (folder / 'individual-flow-checks.json').exists() else []
    for path in paths:
        for record in json.loads(path.read_text()):
            parse_individual(record)
            code = record['code']
            assert code not in merged or merged[code] == record, ('Conflicting observations', code)
            merged[code] = record
    return [merged[code] for code in sorted(merged)]


def preserve_public(market):
    if PUBLIC.exists():
        retained = json.loads(PUBLIC.read_text())
        for family in ('rankings', 'themes'):
            assert digest(retained['daily'][family]) == retained['snapshotSHA256'][family]
        return retained
    assert market['themes']['daily'][DAY]['snapshotPolicy'] == 'verified_public_naver_partial_amounts'
    daily = {family: copy.deepcopy(market[family]['daily'][DAY]) for family in ('rankings', 'themes')}
    retained = {'asOf': DAY, 'originalUpdatedAt': market['updatedAt'], 'provider': 'NAVER',
                'note': 'Previously published public-provider daily observation retained verbatim. The later KRX direct observation is a separate source and collection time, not evidence that this source was fabricated.',
                'sourceEvidence': '../korea-money-evidence-20261106.json', 'daily': daily,
                'snapshotSHA256': {k: digest(v) for k, v in daily.items()},
                'originalRefresh': market['refresh'], 'originalLimitations': market['limitations'],
                'originalRankingsNote': market['rankings']['note'],
                'preservedRootSections': {k: digest(v) for k, v in market.items()
                                          if k not in ('rankings', 'themes', 'sources', 'updatedAt', 'refresh', 'limitations')},
                'preservedDailySnapshots': {family: {day: digest(value) for day, value in market[family]['daily'].items() if day != DAY}
                                           for family in ('rankings', 'themes')},
                'preservedPeriods': {family: {period: digest(market[family][period]) for period in ('aggregate5d', 'monthly')}
                                     for family in ('rankings', 'themes')},
                'originalSourcesSHA256': digest(market['sources']), 'originalSourcesCount': len(market['sources'])}
    write(PUBLIC, retained)
    return retained


def build(market, folder, universe, require_complete=False):
    before = copy.deepcopy(market)
    manifest = json.loads((folder / 'source-manifest.json').read_text())
    bulk = load_bulk(folder, manifest)
    individual = load_individual(folder)
    completion_path = folder / 'completion-manifest.json'
    if require_complete:
        assert completion_path.exists(), 'Frozen completion manifest required for a complete import'
    completion = json.loads(completion_path.read_text()) if completion_path.exists() else None
    if completion:
        assert completion['status'] == 'complete' and completion['asOf'] == DAY
        assert completion['sourceScreen'] == '12009' and completion['sourceForm'] == 'MDCSTAT023_FORM'
        assert completion['sourceUrl'] == INDIVIDUAL_URL
        assert completion['actualBrowserUrl'] == manifest['sourceUrl']
        assert completion['individualRecordCount'] == len(individual) == 65
        assert completion['individualObservedAtStart'] == min(r['observedAt'] for r in individual)
        assert completion['individualObservedAtEnd'] == max(r['observedAt'] for r in individual)
        for item in completion['files']:
            data = (folder / item['file']).read_bytes()
            assert hashlib.sha256(data).hexdigest() == item['sha256'], item['file']
            assert len(json.loads(data)) == item['count']
    flows = copy.deepcopy(bulk)
    discrepancies = []
    for record in individual:
        for who, value in parse_individual(record).items():
            code = record['code']
            if code in bulk[who]:
                earlier = bulk[who][code]
                if any(earlier[field] != value[field] for field in ('netBuyKRW', 'netBuyVolume', 'buyKRW', 'sellKRW')):
                    discrepancies.append({'investor': who, 'code': code, 'csv': earlier, 'individual': value,
                                          'resolution': 'Retain original CSV observation; do not silently override a different snapshot.'})
            else:
                flows[who][code] = value
    members = {m['code'] for basket in market['themes']['baskets'] for m in basket['members']}
    assert len(members) == 1065
    stats = {}
    for who in WHO:
        original_missing = sorted(members - bulk[who].keys())
        assert original_missing == manifest['investors'][who]['missingMembers']
        stats[who] = {'rawRows': len(bulk[who]), 'rawCovered': len(members & bulk[who].keys()),
                      'individuallyVerified': len(set(original_missing) & flows[who].keys()),
                      'originalCSVAbsentCodes': original_missing, 'covered': len(members & flows[who].keys()),
                      'expected': len(members), 'missingCodes': sorted(members - flows[who].keys())}
    if completion:
        for who, stat in stats.items():
            declared = completion['coverage'][who]
            assert stat['covered'] == declared['coveredUnique'] == declared['expectedUnique']
            assert stat['rawCovered'] == declared['bulkCoveredUnique']
            assert stat['individuallyVerified'] == declared['individualCoveredUnique']
            assert stat['missingCodes'] == declared['remainingMissing']
            zeros = sum(flows[who][c]['netBuyKRW'] == 0 for c in stat['originalCSVAbsentCodes'])
            assert zeros == declared['individualZeroNetAmounts']
        assert sum(r['code'] in bulk[who] for r in individual for who in WHO) == completion['bulkIndividualCrosschecks']
        assert discrepancies == completion['crossSourceDiscrepancies']
    if require_complete:
        assert all(not s['missingCodes'] for s in stats.values()), stats
        assert {r['code'] for r in individual} >= set().union(*(set(s['originalCSVAbsentCodes']) for s in stats.values()))
    retained = preserve_public(market)
    # Reuse the exact full public response already retained in repository evidence.
    raw_evidence = json.loads((ROOT / 'data/korea-money-evidence-20261106.json').read_text())
    source_universe = next(r for r in raw_evidence['turnoverRawResponses'] if r['file'] == 'universe.json')
    assert universe == {k: v for k, v in source_universe.items() if k != 'file'}
    assert universe['httpStatus'] == 200
    mapping = {r['itemcode']: {k: r[k] for k in ('itemcode', 'itemname', 'type', 'sosok')} for r in universe['payload']}
    assert len(mapping) == len(universe['payload']) == 2878
    eligible = {code: r for code, r in mapping.items() if r['type'] == 'ST' and r['sosok'] in ('0', '1') and not preferred(r)}
    assert len(eligible) == 2610
    times = [i['observedAt'] for i in manifest['investors'].values()] + [r['observedAt'] for r in individual]
    window = {'observedAtStart': min(times), 'observedAtEnd': max(times)}
    sources = []
    for who, label in WHO.items():
        for kind, screen in (('csv', '12010'), ('individual', '12009')):
            used = [v['observedAt'] for v in flows[who].values() if v['sourceScreen'] == screen]
            if not used:
                continue
            sources.append({'id': f'krx-{who}-{kind}-{STAMP}', 'title': f'KRX {screen} {label} 2026-11-06 원 단위 순매수대금',
                            'url': manifest['sourceUrl'] if kind == 'csv' else INDIVIDUAL_URL,
                            'observedAtStart': min(used), 'observedAtEnd': max(used),
                            'note': SCOPE_NOTE})
    theme = copy.deepcopy(retained['daily']['themes'])
    counts = {who: 0 for who in WHO}
    for row in theme['rows']:
        for who in WHO:
            old = row['coverage'][who]
            components = [{key: value for key, value in flows[who].get(r['code'], {'code': r['code'], 'netBuyKRW': None, 'sourceId': None}).items()
                           if key in ('code', 'netBuyKRW', 'sourceId', 'sourceScreen', 'observedAt')}
                          for r in old['memberFlows']]
            known = [r for r in components if r['netBuyKRW'] is not None]
            missing = [r['code'] for r in components if r['netBuyKRW'] is None]
            subtotal = sum(r['netBuyKRW'] for r in known) if known else None
            total = subtotal if not missing else None
            cell = {'status': 'missing_constituent_amounts' if missing else 'complete',
                    'netBuyKRW': total, 'netBuyEok': None if total is None else total / 100000000,
                    'knownSubtotalKRW': subtotal, 'knownSubtotalEok': None if subtotal is None else subtotal / 100000000,
                    'rank': None, 'availableCount': len(known), 'expectedCount': len(components),
                    'missingMembers': missing, 'memberFlows': components,
                    'sourceIds': sorted({r['sourceId'] for r in known})}
            row['coverage'][who] = cell
            row[who] = cell['netBuyEok']
            counts[who] += not missing
    theme.update({'status': 'verified' if all(c == 13 for c in counts.values()) else 'partial',
                  'sourceIds': sorted({sid for row in theme['rows'] for who in WHO for sid in row['coverage'][who]['sourceIds']}),
                  'snapshotPolicy': 'verified_official_krx_daily',
                  'sourceStatus': 'official_krx_observed_after_scheduled_final_time',
                  'coverage': {'start': DAY, 'end': DAY, 'count': 13, **window,
                               'note': f"전체 금액 확보: 외국인 {counts['foreign']}/13 · 기관 {counts['institution']}/13개 테마. 미확인 금액은 null 유지."},
                  'note': SCOPE_NOTE + ' 전종목 CSV 누락은 12009 개별종목에서 실제 확인한 값만 보완했습니다. '
                          '테마 구성·시총 기준은 기존 10/19를 유지하며 KRX 공식 업종분류가 아닙니다. 테마간 중복을 합산할 수 없습니다. '
                          '기존 NAVER 공개 일간 관측은 별도 근거로 보존했고 주·월간은 공급사의 직접 집계값을 유지합니다.'})
    if completion:
        independent = {r['id']: r for r in completion['themes']}
        assert set(independent) == {r['id'] for r in theme['rows']}
        for row in theme['rows']:
            assert row['memberCount'] == independent[row['id']]['expectedCount']
            for who in WHO:
                assert row['coverage'][who]['netBuyKRW'] == independent[row['id']][who + 'NetBuyKRW']
    market['themes']['daily'][DAY] = theme
    rank_audit = {}
    for who in WHO:
        sid = f'krx-{who}-csv-{STAMP}'
        eligible_rows = [r for code, r in bulk[who].items() if code in eligible]
        def rankrow(value):
            return {'code': value['code'], 'name': value['name'], 'market': 'KOSPI' if mapping[value['code']]['sosok'] == '0' else 'KOSDAQ',
                    'value': value['netBuyKRW'] / 100000000, 'valueKRW': value['netBuyKRW'], 'sourceId': sid, 'source': manifest['sourceUrl']}
        ranked = sorted(eligible_rows, key=lambda r: (-r['netBuyKRW'], r['code']))
        by_market = {name: [rankrow(r) for r in ranked if mapping[r['code']]['sosok'] == sosok][:15]
                     for name, sosok in (('KOSPI', '0'), ('KOSDAQ', '1'))}
        assert all(len(rows) == 15 and all(r['valueKRW'] > 0 for r in rows) for rows in by_market.values())
        rank_audit[who] = {'sourceRowCount': len(bulk[who]), 'eligibleSourceRowCount': len(eligible_rows),
                           'unmappedCodes': sorted(set(bulk[who]) - mapping.keys()),
                           'excludedMappedCodes': sorted((set(bulk[who]) & mapping.keys()) - eligible.keys())}
        market['rankings']['daily'][DAY][who] = {
            'status': 'verified', 'unit': '억원', 'rows': [rankrow(r) for r in ranked[:15]],
            'byMarket': by_market, 'sourceIds': [sid], 'snapshotPolicy': 'verified_official_krx_daily',
            'coverage': {'start': DAY, 'end': DAY, 'periodType': 'DAY', 'markets': ['KOSPI', 'KOSDAQ'],
                         'tradeType': 'KRX', 'sourceAmountField': '거래대금_순매수', 'sourceUnit': 'KRW',
                         'observedAt': manifest['investors'][who]['observedAt'],
                         'mappingObservedAt': universe['observedAt'], 'sourceRowCount': len(bulk[who]),
                         'eligibleSourceRowCount': len(eligible_rows), 'eligibleUniverseCount': len(eligible),
                         'excludedUnmappedCount': len(rank_audit[who]['unmappedCodes']),
                         'universe': 'KOSPI/KOSDAQ NAVER ST + 기존 우선주 명칭·코드 제외 필터; ST 스팩 포함'},
            'note': SCOPE_NOTE + ' 순위는 전체시장 CSV에서 NAVER 시장·유형을 대조해 KOSPI·KOSDAQ별 상위15를 선정했습니다. '
                    'ST 스팩 포함, KONEX·ETF·ETN·리츠·외국주식·예탁증권·펀드 제외. 보통주 중심 필터이며 법적 주식종류 전수 검증은 아닙니다.'}
    market['rankings']['note'] = ('11/6 일간 외국인·기관은 11/8 조회한 KRX 공식 원 단위 순매수대금입니다. '
                                 '주간·월간은 NAVER KRX 직접 기간 합산 금액이고 일간 거래대금도 검증된 NAVER 원값을 유지합니다. '
                                 '이전 일별 관측과 기존 11/6 공개 공급사 관측은 각자의 값·출처·시각으로 보존합니다.')
    by_id = {s['id']: s for s in market['sources']}
    by_id.update({s['id']: s for s in sources})
    market['sources'] = list(by_id.values())
    market['limitations'] = [
        '공개 공급사 및 공식 거래소 관측 자료로 지연·정정·조회 제한이 있을 수 있습니다. 각 항목의 실제 기준일과 관측시각을 확인하세요.',
        '주·월간과 일간 거래대금은 NAVER 직접 집계, 11/6 일간 종목 순매수·테마는 KRX 공식 직접조회입니다. 서로 다른 출처·집계시각 값을 혼합해 합산하지 않습니다.',
        SCOPE_NOTE,
        *[s for s in retained['originalLimitations'] if s.startswith(('기간 합계는', '과거 4거래일', '과거 일별 종목', '테마는', '테마 구성종목', '테마 표시 시총', '예탁금·신용융자'))],
        '주·월간 테마의 NAVER 순매수·순매도 상위100 범위 밖 금액은 미확인입니다. 공개 일간 스냅샷의 차이는 별도 원표와 관측시각으로 보존합니다.'
    ]
    market['updatedAt'] = dt.datetime.now(dt.timezone.utc).isoformat()
    market['refresh'] = {'attemptedAt': max(times), 'status': 'complete' if theme['status'] == 'verified' else 'partial',
                         'refreshedSections': ['rankings.foreign', 'rankings.institution', 'themes.daily.2026-11-06'],
                         'failures': [] if theme['status'] == 'verified' else [{'section': 'themes', 'message': 'KRX 개별종목 미확인 금액은 null을 유지합니다.'}],
                         'note': '11/8 실제 관측 KRX 원표로 11/6 일간만 보완했습니다. 16개 이전 일간·주월간·거래대금·가격·ETF 등은 보존했습니다.'}
    evidence = {'asOf': DAY, 'start': DAY, 'end': DAY, 'unit': 'KRW', 'assembledAt': market['updatedAt'],
                'sourceStatus': theme['sourceStatus'], 'sourceScreens': ['12010', '12009'],
                'source': manifest['sourceUrl'], 'finalDataNote': FINAL_NOTE, 'collectionWindowUTC': window,
                'individualSource': {'url': INDIVIDUAL_URL, 'activeMDIUrl': manifest['sourceUrl'],
                                     'sourceScreen': '12009', 'formId': 'MDCSTAT023_FORM',
                                     'navigationEvidence': {'text': '투자자별 거래실적(개별종목)',
                                                            'data-menu-id': 'MDC0201020302', 'class': 'CI-MDI-MENU',
                                                            'href': 'javascript:void(0)'}},
                'individualObservationSHA256': digest(individual),
                'basketDefinitionVersion': market['themes']['basketDefinitionVersion'], 'stats': stats,
                'individualObservedCount': len(individual), 'crossCheckDiscrepancies': discrepancies,
                'mappingEvidence': {'source': universe['url'], 'observedAt': universe['observedAt'],
                                    'rawEvidence': '../korea-money-evidence-20261106.json',
                                    'rawResponseSelector': {'array': 'turnoverRawResponses', 'file': 'universe.json'},
                                    'rawResponseSHA256': digest(universe), 'sourceRowCount': len(mapping),
                                    'eligibleStockCount': len(eligible), 'marketMapping': list(mapping.values())},
                'rankingsAudit': rank_audit,
                'flows': {who: {code: flows[who][code] for code in sorted(members & flows[who].keys())} for who in WHO}}
    if completion:
        evidence['completionManifestSHA256'] = hashlib.sha256(completion_path.read_bytes()).hexdigest()
    assert_preserved(before, market)
    return market, evidence, individual, manifest


def assert_preserved(before, after):
    """Bound the importer to its daily supplement, even when called again later."""
    mutable = {'sources', 'updatedAt', 'refresh', 'limitations', 'rankings', 'themes'}
    assert {k: v for k, v in before.items() if k not in mutable} == {k: v for k, v in after.items() if k not in mutable}
    for family in ('rankings', 'themes'):
        assert set(before[family]) == set(after[family])
        for key in before[family]:
            if key not in ('daily', 'note'):
                assert before[family][key] == after[family][key], (family, key)
        assert set(before[family]['daily']) == set(after[family]['daily'])
        for day, value in before[family]['daily'].items():
            if day != DAY:
                assert value == after[family]['daily'][day], (family, day)
    assert before['rankings']['daily'][DAY]['tradedValue'] == after['rankings']['daily'][DAY]['tradedValue']
    original = {s['id']: s for s in before['sources'] if not s['id'].startswith(('krx-foreign-csv-20261106', 'krx-foreign-individual-20261106', 'krx-institution-csv-20261106', 'krx-institution-individual-20261106'))}
    assert all(s in after['sources'] for s in original.values())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input-dir', type=Path, default=EVIDENCE)
    parser.add_argument('--universe', type=Path)
    parser.add_argument('--require-complete', action='store_true')
    args = parser.parse_args()
    market = json.loads((ROOT / 'data/korea-market.json').read_text())
    if args.universe:
        universe = json.loads(args.universe.read_text())
    else:
        raw = json.loads((ROOT / 'data/korea-money-evidence-20261106.json').read_text())
        universe = {k: v for k, v in next(r for r in raw['turnoverRawResponses'] if r['file'] == 'universe.json').items() if k != 'file'}
    market, evidence, individual, manifest = build(market, args.input_dir, universe, args.require_complete)
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    for inv in manifest['investors'].values():
        (EVIDENCE / inv['file']).write_bytes((args.input_dir / inv['file']).read_bytes())
    (EVIDENCE / 'source-manifest.json').write_bytes((args.input_dir / 'source-manifest.json').read_bytes())
    completion_path = args.input_dir / 'completion-manifest.json'
    if completion_path.exists():
        completion = json.loads(completion_path.read_text())
        (EVIDENCE / completion_path.name).write_bytes(completion_path.read_bytes())
        for item in completion['files']:
            (EVIDENCE / item['file']).write_bytes((args.input_dir / item['file']).read_bytes())
    write(EVIDENCE / 'individual-flow-checks.json', individual)
    write(EVIDENCE / 'verified-daily-theme-flows.json', evidence)
    write(ROOT / 'data/korea-market.json', market, compact=True)
    print(json.dumps({'stats': evidence['stats'], 'discrepancies': len(evidence['crossCheckDiscrepancies']),
                      'completeThemes': {who: sum(r['coverage'][who]['status'] == 'complete' for r in market['themes']['daily'][DAY]['rows']) for who in WHO}}, ensure_ascii=False))


if __name__ == '__main__':
    main()
