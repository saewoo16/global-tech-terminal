"""Derive the latest session's compact S&P 500 breadth from preserved close evidence.

Run before publication: python scripts/build_us_breadth.py
Read-only verification: python scripts/build_us_breadth.py --check
No network requests, new market observations, or prior-session fallbacks.
"""
import argparse
import copy
import json
from pathlib import Path

from validate_us_analysis import ROOT, finite_number, validate, validate_breadth


def derive_breadth(entry, evidence):
    counts = dict.fromkeys(('advancing', 'declining', 'unchanged'), 0)
    valid = set()
    for row in evidence['screens']['dailyRows']:
        close, previous = row.get('close'), row.get('previousClose')
        if not all(finite_number(value) and value > 0 for value in (close, previous)):
            continue
        valid.add(row['ticker'])
        counts['advancing' if close > previous else 'declining' if close < previous else 'unchanged'] += 1
    roster = entry['constituents']
    members = {row['ticker'] for row in roster}
    missing = sorted(members - valid)
    breadth = {
        'status': 'unavailable' if not valid else 'partial' if missing else 'verified',
        'universe': 'S&P 500',
        'asOf': entry['date'],
        'previousSession': entry['sessionVerification']['previousSession'],
        'universeAsOf': entry['coverage']['universeAsOf'],
        'companies': len({str(row['cik']).lstrip('0') for row in roster}),
        'securities': len(members),
        'validCount': len(valid),
        'missingCount': len(missing),
        'missingTickers': missing,
        'counts': counts,
        'percentages': {key: value / len(valid) * 100 if valid else None for key, value in counts.items()},
        'denominator': 'valid_securities',
        'priceBasis': 'regular_close_vs_previous_regular_close',
        'evidencePath': f"data/us-close-evidence-{entry['date'].replace('-', '')}.json",
        'evidenceRows': 'screens.dailyRows',
        'sourceIds': ['sp500_membership', 'us_sp500_price_method'],
        'note': 'S&P 500 구성 증권만 집계하며 미국 시장 전체가 아닙니다. 복수 주식종류는 각각 1개 증권으로 유지합니다. 정규장 종가와 직전 거래일 정규장 종가를 반올림 전에 비교하고, 비율의 분모는 양일 종가가 확인된 증권 수입니다. 미확인 종목은 보합이나 0%로 간주하지 않습니다.',
    }
    validate_breadth(breadth, entry, evidence)
    return breadth


def build(payload, date=None):
    """Return a validated candidate, changing only the selected/latest breadth."""
    candidate = copy.deepcopy(payload)
    entry = (next(e for e in candidate['entries'] if e['date'] == date) if date
             else max(candidate['entries'], key=lambda e: e['date']))
    path = ROOT / f"data/us-close-evidence-{entry['date'].replace('-', '')}.json"
    evidence = json.loads(path.read_text())  # Missing session evidence is an error, not a fallback.
    entry['breadth'] = derive_breadth(entry, evidence)
    validate(candidate)
    return candidate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=ROOT / 'data/us_analysis.json')
    parser.add_argument('--date', help='Explicit report session; default is latest completed entry')
    parser.add_argument('--check', action='store_true', help='Verify derivation without writing')
    args = parser.parse_args()
    original = json.loads(args.input.read_text())
    candidate = build(original, args.date)
    if args.check:
        if candidate != original:
            raise SystemExit('Breadth is missing or differs from the preserved close evidence.')
        print('Verified latest/selected S&P 500 breadth against preserved close evidence.')
    elif candidate != original:
        args.input.write_text(json.dumps(candidate, ensure_ascii=False, indent=2) + '\n')
        print('Updated only the latest/selected entry breadth; all other panels preserved.')
    else:
        print('Breadth already matches preserved close evidence; no files changed.')


if __name__ == '__main__':
    main()
