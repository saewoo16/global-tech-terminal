import json
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]


class November5CompanyRefresh(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.evidence = json.loads((ROOT / 'data/price-refresh-evidence-20261105-asia.json').read_text())
        cls.market = json.loads((ROOT / 'data/market.json').read_text())

    def test_completed_sessions_and_history(self):
        evidence = self.evidence
        self.assertEqual(evidence['targetDate'], '2026-11-05')
        self.assertEqual(evidence['count'], 113)
        self.assertEqual(len({r['symbol'] for r in evidence['records']}), 113)
        self.assertEqual(evidence['reusedKoreanSources'], 27)
        for row in evidence['records']:
            with self.subTest(symbol=row['symbol']):
                self.assertTrue(row['validation']['identity'])
                self.assertTrue(row['validation']['sessionCompleted'])
                self.assertGreaterEqual(datetime.fromisoformat(row['observedAt']), datetime.fromisoformat(row['exchangeCloseCutoff']))
                self.assertEqual(row['sourceSessionDate'], '2026-11-05')
                self.assertEqual(row['overlapRevisions'], {})
                self.assertEqual(row['point'][1], round(row['rawTarget']['adjustedClose'], 5))
                stock = self.market['stocks'][row['symbol']]
                self.assertGreaterEqual(stock['lastPriceDate'], '2026-11-05')
                self.assertIn('2026-11-05', dict(stock['prices']))

    def test_contradictory_source_opens_reconciled(self):
        reconciled = [r for r in self.evidence['records'] if r['status'] == 'verified_independent_reconciliation']
        self.assertEqual(len(reconciled), 6)
        for row in reconciled:
            with self.subTest(symbol=row['symbol']):
                self.assertFalse(row['validation']['targetOHLC'])
                values = row['independentConfirmation']['values']
                self.assertEqual(datetime.fromtimestamp(values['time'], ZoneInfo(row['timezone'])).date().isoformat(), '2026-11-05')
                self.assertLessEqual(values['low'], min(values['open'], values['close']))
                self.assertGreaterEqual(values['high'], max(values['open'], values['close']))
                self.assertAlmostEqual(values['close'], row['rawTarget']['close'], places=3)
                self.assertAlmostEqual(values['close[1]'], row['rawPrevious']['close'], places=3)

    def test_completed_fx_and_cap_limitations(self):
        evidence = self.evidence
        self.assertEqual(evidence['publishedFX']['date'], '2026-11-04')
        self.assertEqual(evidence['publishedFX']['value'], 1342.9)
        bars = evidence['marketCapAndFXAssessment']['FX']['daily']
        self.assertTrue(next(x for x in bars if x['date'] == '2026-11-04')['completedBeforeObservation'])
        self.assertFalse(next(x for x in bars if x['date'] == '2026-11-05')['completedBeforeObservation'])
        self.assertTrue(evidence['preservation']['marketCapValuesAndObservationDatesPreserved'])
        self.assertEqual(len(evidence['preservation']['untouchedStocks']), 134)
        self.assertEqual(len(evidence['independentKoreanCloseComparisons']), 16)

class November5OfficialFilings(unittest.TestCase):
    def test_new_standalone_quarters_and_original_comparatives(self):
        snapshot = json.loads((ROOT / 'data/financial_backfill_zlatest_20261105_asia_official.json').read_text())
        expected = {'TSE:3433': (17928, 4391), 'TSE:5384': (21082, 4809), 'TSE:4203': (96830, 11767), 'TSE:7729': (55683, 14421), 'TSE:6963': (143744, 7852), 'TSE:6976': (112136, 13378)}
        self.assertEqual(set(snapshot['companies']), set(expected))
        for symbol, values in expected.items():
            quarter = snapshot['companies'][symbol]['quarters'][0]
            self.assertEqual((quarter['revenue'], quarter['operatingIncome']), values)
            self.assertEqual((quarter['periodStart'], quarter['date']), ('2026-07-01', '2026-09-30'))
            self.assertEqual(quarter['reportedCurrency'], 'JPY')
            self.assertTrue(quarter['sourceUrl'].startswith('https://'))
            self.assertEqual(len(quarter['sourceSha256']), 64)
            if symbol != 'TSE:6976':
                self.assertIn('firstQuarterSource', quarter['calculation'])


if __name__ == '__main__':
    unittest.main()
