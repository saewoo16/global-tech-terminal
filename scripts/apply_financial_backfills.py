"""Apply auditable source snapshots after the live feed, preserving newer periods.

Every snapshot includes its real verification date. Re-running this script does
not make old filings fresh. Values are millions of the stated reporting currency.
"""
import json
import datetime as dt
from pathlib import Path
from data_quality import annotate, merge_quarters, migrate_symbols, write_json

ROOT = Path(__file__).resolve().parents[1]


def apply(market, snapshots):
    stocks = migrate_symbols(market.setdefault('stocks', {}))
    for snapshot in snapshots:
        for symbol, record in snapshot.get('companies', {}).items():
            item = stocks.setdefault(symbol, {})
            quarters = []
            for raw in record.get('quarters', []):
                q = dict(raw)
                q.setdefault('sourceType', 'filing')
                q.setdefault('source', 'Official issuer filing')
                q.setdefault('verifiedAt', snapshot.get('asOf'))
                q.setdefault('reportedCurrency', record.get('reportingCurrency'))
                if not q.get('sourceUrl'):
                    raise ValueError(f'Missing source URL: {symbol} {q.get("date")}')
                quarters.append(q)
            prior = item.get('quarters', [])
            if record.get('replaceQuarters') and quarters:
                # Replace the audited historical window, not future live quarters.
                newest = max(q['date'] for q in quarters)
                # Providers may normalize a fiscal June 26 close to June 30.
                # Only genuinely later quarters may survive a verified replacement.
                cutoff=(dt.date.fromisoformat(newest)+dt.timedelta(days=45)).isoformat()
                prior = [q for q in prior if q.get('date', '') > cutoff]
            item['quarters'] = merge_quarters(prior, quarters)
            for field in ('reportingCurrency','financialNote','reportedPeriods'):
                if field in record:
                    item[field] = record[field]
            if quarters:
                item['financialVerifiedAt'] = snapshot.get('asOf')
                item['finSource'] = 'Official issuer filings (per-quarter sources)'
                item.pop('financialUpdated', None)
            annotate(symbol, item)
            if record.get('financialStatus') == 'not_disclosed':
                item['financialStatus'] = 'not_disclosed'
                item['quarterlyReporting'] = 'not_disclosed'
                item['financialNote'] = record['financialNote']
    for symbol, item in stocks.items():
        annotate(symbol, item)
    return market


def main():
    path = ROOT/'data/market.json'
    market = json.loads(path.read_text())
    snapshots = [json.loads(p.read_text()) for p in sorted((ROOT/'data').glob('financial_backfill_*.json'))]
    write_json(path, apply(market, snapshots))
    print('SOURCE_BACKFILLS', len(snapshots), 'snapshots applied')


if __name__ == '__main__':
    main()
