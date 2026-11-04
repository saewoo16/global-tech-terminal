import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class November4AsiaCompanies(unittest.TestCase):
    def test_completed_sessions_and_rejected_candles(self):
        evidence = json.loads((ROOT/'data/price-refresh-evidence-20261104-asia.json').read_text())
        records = evidence['records']
        self.assertEqual(len(records), 113)
        self.assertEqual(len({r['symbol'] for r in records}), 113)
        replacements = 0
        for row in records:
            self.assertEqual(row['status'], 'verified', row['symbol'])
            self.assertEqual(row['point'][0], '2026-11-04')
            self.assertGreater(row['point'][1], 0)
            bar = row.get('completeIndependentTarget', row['rawTarget'])
            self.assertLessEqual(bar['low'], min(bar['open'],bar['close']))
            self.assertLessEqual(max(bar['open'],bar['close']), bar['high'])
            if row.get('completeIndependentTarget'):
                replacements += 1
                self.assertIn('rejectedYahooCandleReason', row)
                self.assertTrue(row['independentSourceUrl'].startswith('https://web.ifzq.gtimg.cn/'))
            if row['symbol'].startswith('TSE:'):
                self.assertEqual(row['previousPoint'][0], '2026-11-02')
            else:
                self.assertEqual(row['previousPoint'][0], '2026-11-03')
        self.assertEqual(replacements, 5)

    def test_preservation_audit(self):
        evidence = json.loads((ROOT/'data/company-preservation-evidence-20261104.json').read_text())
        self.assertEqual(evidence['preservedNonAsianListings'], 134)
        self.assertEqual(evidence['preservedCapitalizationRecords'], 247)
        self.assertEqual(evidence['lostHistoricalDates'], [])
        self.assertEqual(evidence['verifiedAsiaListings'], 113)
        self.assertEqual(evidence['fullHistoryReconciliations'], ['KRX:005930','KRX:000660','KRX:000150'])

    def test_targeted_official_additions(self):
        snapshot = json.loads((ROOT/'data/financial_backfill_zlatest_20261104_asia_official.json').read_text())
        expected = {'KRX:036930': (78076,17667,'KRW'), 'TSE:5802': (1434321,122508,'JPY'), 'TWSE:2344': (82331,43784,'TWD')}
        self.assertEqual(set(snapshot['companies']), set(expected))
        for symbol, values in expected.items():
            quarter = snapshot['companies'][symbol]['quarters'][0]
            self.assertEqual((quarter['revenue'],quarter['operatingIncome'],quarter['reportedCurrency']),values)
            self.assertEqual(quarter['date'],'2026-09-30')
            self.assertEqual(quarter['verifiedAt'],'2026-11-04')
            self.assertTrue(quarter['sourceUrl'].startswith('https://'))
        self.assertEqual(2764912-1330591, expected['TSE:5802'][0])
        self.assertEqual(219567-97059, expected['TSE:5802'][1])
