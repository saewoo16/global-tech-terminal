"""Import complete KRX CP949 balance exports without network or authentication.

Manifest: {"snapshots":[{"market":"KOSPI", "date":"YYYY-MM-DD",
"observedAt":"...Z", "path":"export.csv", "sourceUrl":"https://data.krx.co.kr/..."}]}.
Each date must have BOTH markets. Export all rows in shares / KRW units. Paths are
resolved relative to manifest. --check validates/builds without changing files.
"""
import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
from manage_korean_short_balance import MARKETS, METRIC, ROOT, amount, day, merge, require, timestamp, validate, ranking_codes

HEADERS = ['종목코드', '종목명', '수량_공매도순보유잔고수량', '수량_상장주식수', '금액_공매도순보유잔고금액', '금액_시가총액', '비중']


def load_snapshot(item, base):
    require(item.get('market') in MARKETS, 'Unknown market')
    day(item.get('date'))
    require(timestamp(item.get('observedAt')).date() >= day(item['date']), 'Observation predates export date')
    path = Path(item['path'])
    if not path.is_absolute():
        path = base / path
    raw = path.read_bytes()
    if 'sha256' in item:
        require(item['sha256'] == hashlib.sha256(raw).hexdigest(), 'Export bytes differ from manifest SHA256')
    text = raw.decode('cp949')
    reader = csv.DictReader(io.StringIO(text, newline=''))
    require(reader.fieldnames == HEADERS, 'Unexpected KRX balance CSV headers or wrong units/export')
    source_id = 'krx-short-' + item['market'].lower() + '-' + item['date'] + '-' + hashlib.sha256(raw).hexdigest()[:12]
    rows = []
    for raw_row in reader:
        require(set(raw_row) == set(HEADERS) and all(v is not None for v in raw_row.values()), 'Malformed CSV row')
        row = {'code': raw_row['종목코드'], 'name': raw_row['종목명'], 'market': item['market'],
               'balanceKRW': raw_row['금액_공매도순보유잔고금액'], 'marketCapKRW': raw_row['금액_시가총액'],
               'ratioPct': raw_row['비중'], 'balanceShares': raw_row['수량_공매도순보유잔고수량'],
               'listedShares': raw_row['수량_상장주식수'], 'observedAt': item['observedAt'], 'sourceIds': [source_id], 'history': []}
        for key in ('balanceKRW', 'marketCapKRW', 'balanceShares', 'listedShares'):
            amount(row[key], key in ('marketCapKRW', 'listedShares'))
        require(int(row['balanceKRW']) * int(row['listedShares']) == int(row['balanceShares']) * int(row['marketCapKRW']), 'KRX amount and quantity ratios disagree; check units')
        rows.append(row)
    require(rows, 'Empty export is not a verified market snapshot')
    require(len({r['code'] for r in rows}) == len(rows), 'Duplicate security in export')
    if 'expectedRows' in item:
        require(item['expectedRows'] == len(rows), 'Export count differs from independently checked source row count')
    source = {'id': source_id, 'title': f"KRX {item['market']} 개별종목 공매도 순보유잔고 {item['date']}",
              'url': item['sourceUrl'], 'observedAt': item['observedAt'], 'date': item['date'],
              'rawFile': path.name, 'sha256': hashlib.sha256(raw).hexdigest(), 'rowCount': len(rows),
              'sourceUnits': {'quantity': 'shares', 'amount': 'KRW', 'ratio': 'percent'},
              'note': 'KRX 공식 CSV 전체 행 · 우선주·리츠·스팩 등 원표 종목 포함 · 종목 단위, 발행사 합산 아님'}
    return rows, source


def build(manifest, base=Path('.')):
    require(isinstance(manifest.get('snapshots'), list) and manifest['snapshots'], 'snapshots manifest required')
    snapshots, sources = {}, []
    for item in manifest['snapshots']:
        key = (item.get('date'), item.get('market'))
        require(key not in snapshots, 'Duplicate date/market export')
        rows, source = load_snapshot(item, base)
        snapshots[key] = rows
        sources.append(source)
    dates = sorted({key[0] for key in snapshots})
    require(all((d, m) in snapshots for d in dates for m in MARKETS), 'Every date must include both complete market exports')
    latest = dates[-1]
    rows = [r for market in MARKETS for r in snapshots[(latest, market)]]
    histories = {}
    for d in dates:
        if d == latest:
            continue
        for market in MARKETS:
            for row in snapshots[(d, market)]:
                histories.setdefault(row['code'], []).append({'date': d, **{k: row[k] for k in ('balanceKRW', 'marketCapKRW', 'ratioPct', 'balanceShares', 'listedShares', 'observedAt', 'sourceIds')}})
    selected = ranking_codes(rows)
    for row in rows:
        row['history'] = histories.get(row['code'], []) if row['code'] in selected else []
    observed = max((s['observedAt'] for s in sources), key=timestamp)
    payload = {'schemaVersion': 1, 'metric': METRIC, 'unit': 'KRW', 'investorSplit': 'unavailable',
               'status': 'verified', 'asOf': latest, 'observedAt': observed,
               'coverage': {'markets': MARKETS, 'complete': True, 'scope': 'whole-market', 'count': len(rows),
                            'countByMarket': {m: len(snapshots[(latest, m)]) for m in MARKETS},
                            'historyDates': dates[:-1], 'snapshotDates': dates,
                            'historyScope': 'current-ranking-union', 'historySecurityCount': len(selected),
                            'evidenceNote': 'KRX 공식 CSV 양 시장 전체 행. 우선주·리츠·스팩 등 원표 종목 포함, 종목 단위이며 발행사별 합산 아님. 과거에만 존재한 종목은 현재 순위에서 제외하며 신규 종목의 과거 값을 채우지 않음.'},
               'sources': sources, 'rows': rows,
               'limitations': ['종목별 투자자 유형별 잔고는 이 원표에 없으므로 외국인·국내 기관으로 추정 분리하지 않습니다.', '보고된 순보유잔고이며 모든 경제적 숏 익스포저를 포괄하지 않습니다.']}
    # Validate each historical export as well, including securities no longer
    # present in the current universe. They remain auditable in source files.
    for d in dates:
        historical = {**payload, 'asOf': d, 'rows': [r for m in MARKETS for r in snapshots[(d, m)]]}
        historical['coverage'] = {**payload['coverage'], 'count': len(historical['rows']), 'countByMarket': {m: len(snapshots[(d, m)]) for m in MARKETS}}
        historical['coverage'].pop('historyScope', None)
        historical['coverage'].pop('historySecurityCount', None)
        validate(historical)
    return validate(payload)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--path', default=str(ROOT / 'data/korean_short_balance.json'))
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    manifest_path = Path(args.manifest)
    payload = build(json.loads(manifest_path.read_text()), manifest_path.parent)
    path = Path(args.path)
    old = json.loads(path.read_text()) if path.exists() else None
    result = merge(old, payload)
    if args.check:
        print(f"Validated {len(result['rows'])} current securities as of {result['asOf']}; {len(payload['sources'])} official exports. No files changed.")
    elif result == old:
        print('No changed verified balance data.')
    else:
        temp = path.with_suffix('.tmp')
        temp.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
        temp.replace(path)
        print(f"Imported {len(result['rows'])} current securities as of {result['asOf']}.")


if __name__ == '__main__':
    main()
