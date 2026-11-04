import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class November3CompanyRefresh(unittest.TestCase):
    def test_verified_completed_price_evidence(self):
        records = []
        for suffix in ('us-europe', 'asia'):
            data = json.loads((ROOT / f'data/price-refresh-evidence-20261103-{suffix}.json').read_text())
            self.assertEqual(data['targetDate'], '2026-11-03')
            records.extend(data['records'])
        self.assertEqual(len(records), 210)
        self.assertEqual(len({r['symbol'] for r in records}), 210)
        for record in records:
            self.assertEqual(record['status'], 'verified', record['symbol'])
            self.assertEqual(record['point'][0], '2026-11-03')
            bar = record['rawTarget']
            self.assertLessEqual(bar['low'], min(bar['open'], bar['close']))
            self.assertLessEqual(max(bar['open'], bar['close']), bar['high'])
            self.assertGreater(record['point'][1], 0)

    def test_official_quarter_values_and_actual_periods(self):
        audit = json.loads((ROOT / 'data/company-refresh-evidence-20261103.json').read_text())
        updates = {r['symbol']: r['quarter'] for r in audit['financialUpdates']}
        expected = {'NASDAQ:FISV': (5196, -5494), 'NYSE:DD': (1868, None),
                    'NYSE:ETN': (8947, None), 'NASDAQ:AMD': (13377, 2832),
                    'NASDAQ:SMCI': (19945.832, 2064.493),
                    'NYSE:ANET': (3657.6, 1642.4), 'NASDAQ:BKNG': (8893, 3418)}
        self.assertEqual(set(updates), set(expected))
        for symbol, values in expected.items():
            self.assertEqual((updates[symbol]['revenue'], updates[symbol]['operatingIncome']), values)
            self.assertEqual(updates[symbol]['reportedCurrency'], 'USD')
        self.assertEqual(updates['NASDAQ:AMD']['date'], '2026-09-26')
