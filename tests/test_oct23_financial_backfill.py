import copy
import json
import sys
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from apply_financial_backfills import apply

class October23FinancialBackfillTests(unittest.TestCase):
    def snapshots(self):
        return [json.loads(p.read_text()) for p in sorted((ROOT / 'data').glob('financial_backfill_zlatest_20261023_*.json'))]

    def test_verified_actual_quarters_and_gaap_operating_income(self):
        records = {k: v for s in self.snapshots() for k, v in s['companies'].items()}
        wdc = records['NASDAQ:WDC']['quarters']
        self.assertEqual([(q['date'], q['revenue'], q['operatingIncome']) for q in wdc], [
            ('2026-10-02', 4381, 2046), ('2026-07-03', 3747, 1563),
            ('2026-04-03', 3337, 1190), ('2026-01-02', 3017, 908)])
        disco = records['TSE:6146']['quarters'][0]
        self.assertEqual((disco['date'], disco['revenue'], disco['operatingIncome']), ('2026-09-30', 142750, 67606))
        self.assertEqual(disco['sourceFacts']['operatingIncome']['worksheet'], 'Quarterly')
        besi = records['EURONEXT:BESI']['quarters'][0]
        self.assertEqual((besi['date'], besi['revenue'], besi['operatingIncome']), ('2026-09-30', 283.4, 129.679))
        for record in records.values():
            for q in record['quarters']:
                self.assertTrue(q['sourceUrl'].startswith('https://'))
                self.assertEqual(q['verifiedAt'], '2026-10-23')
                for field in ('revenue', 'operatingIncome'):
                    fact = q['sourceFacts'][field]
                    divisor = 1000 if fact['rawUnit'].startswith('thousands') else 1
                    self.assertEqual(q[field], fact['rawValue'] / divisor)

    def test_no_price_cap_or_market_dates_changed_and_idempotent(self):
        market = json.loads((ROOT / 'data/market.json').read_text())
        result = apply(copy.deepcopy(market), self.snapshots())
        for key in market:
            if key != 'stocks':
                self.assertEqual(market[key], result[key])
        for symbol, before in market['stocks'].items():
            after = result['stocks'][symbol]
            for key in ('prices', 'close', 'updated', 'lastPriceDate', 'marketCapUSD', 'marketCapUpdated', 'priceCurrency', 'latestCompletedSession'):
                self.assertEqual(before.get(key), after.get(key), (symbol, key))
        self.assertEqual(result, apply(copy.deepcopy(result), self.snapshots()))
