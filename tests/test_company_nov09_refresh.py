"""Persisted evidence for the November 9 Asian completed-session refresh."""
import datetime as dt
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class CompanyNovember9Refresh(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.market = json.loads((ROOT / 'data/market.json').read_text())
        cls.evidence = json.loads((ROOT / 'data/price-refresh-evidence-20261109-asia.json').read_text())
        cls.financials = json.loads((ROOT / 'data/financial_backfill_zlatest_20261109_asia_official.json').read_text())

    def test_source_identity_and_completed_session(self):
        records = self.evidence['records']
        self.assertEqual(len(records), 113)
        self.assertEqual(len({r['symbol'] for r in records}), 113)
        self.assertEqual(sum(r['reused'] for r in records), 27)
        for record in records:
            self.assertEqual(record['sourceSessionDate'], '2026-11-09')
            self.assertTrue(record['validation']['identity'])
            self.assertTrue(record['validation']['sessionCompleted'])
            cutoff = dt.datetime.fromisoformat(record['exchangeCloseCutoff'])
            observed = dt.datetime.fromisoformat(record['observedAt'])
            self.assertLess(cutoff, observed)
            self.assertTrue(record['validation']['independentCurrentAndPreviousClose'])

    def test_added_prices_and_unique_dates(self):
        for record in self.evidence['records']:
            stock = self.market['stocks'][record['symbol']]
            points = stock['prices']
            self.assertEqual(len(points), len(dict(points)))
            self.assertEqual(points, sorted(points))
            self.assertGreaterEqual(stock['lastPriceDate'], '2026-11-09')
            self.assertAlmostEqual(dict(points)['2026-11-09'], record['point'][1], places=4)
            self.assertEqual(record['previousPoint'][0], '2026-11-06')

    def test_independent_comparison_and_rejected_fields(self):
        self.assertEqual(self.evidence['independentVerification']['sameSessionCurrentAndPreviousCloseMatches'], 113)
        discrepancies = self.evidence['rejectedOHLCDiscrepancies']
        self.assertEqual(len(discrepancies), 9)
        by_symbol = {r['symbol']: r for r in self.evidence['records']}
        for item in discrepancies:
            record = by_symbol[item['symbol']]
            self.assertTrue(record['validation']['independentTargetOHLC'])
            self.assertTrue(record['independentConfirmation']['currentCloseMatches'])
            self.assertTrue(record['independentConfirmation']['previousCloseMatches'])
            self.assertTrue(record['rejectedYahooFields'])

    def test_preservation_and_honest_source_limits(self):
        preserved = self.evidence['preservation']
        self.assertEqual(preserved['unchangedUSAndEuropeanListings'], 134)
        self.assertEqual(preserved['removedHistoryDates'], 0)
        self.assertEqual(preserved['changedHistoryValues'], 0)
        self.assertEqual(preserved['marketCapFieldsChanged'], 0)
        self.assertFalse(preserved['fxChanged'])
        self.assertEqual(self.evidence['publishedFX'], {'value': 1356.34, 'asOf': '2026-11-06'})
        self.assertEqual(self.evidence['rawReceiptCoverage']['newYahooRawResponses'], 86)
        self.assertEqual(self.evidence['rawReceiptCoverage']['reusedKoreanParsedReceipts'], 27)

    def test_official_quarters_and_original_precision(self):
        expected = {'TSE:5801': (372470, 32161, 'JPY'),
                    'TSE:4901': (885021, 89984, 'JPY'),
                    'TSE:6525': (88629, 20888, 'JPY'),
                    'KRX:000150': (5426900, 459400, 'KRW')}
        self.assertEqual(set(self.financials['companies']), set(expected))
        for symbol, (revenue, operating, currency) in expected.items():
            quarter = self.financials['companies'][symbol]['quarters'][0]
            self.assertEqual(quarter['date'], '2026-09-30')
            self.assertEqual(quarter['periodStart'], '2026-07-01')
            self.assertEqual(quarter['publishedAt'][:10], '2026-11-09')
            self.assertEqual(quarter['verifiedAt'], '2026-11-09')
            self.assertEqual(quarter['sourceType'], 'filing')
            self.assertEqual((quarter['revenue'], quarter['operatingIncome'], quarter['reportedCurrency']),
                             (revenue, operating, currency))
            current = next(q for q in self.market['stocks'][symbol]['quarters'] if q['date'] == quarter['date'])
            self.assertEqual(current['revenue'], revenue)
            self.assertEqual(current['operatingIncome'], operating)
        self.assertTrue(self.financials['companies']['KRX:000150']['quarters'][0]['provisional'])
        kokusai = self.financials['companies']['TSE:6525']['quarters'][0]
        self.assertNotIn('sourceSha256', kokusai)
        self.assertEqual(len(kokusai['sourceTextSha256']), 64)


if __name__ == '__main__':
    unittest.main()
