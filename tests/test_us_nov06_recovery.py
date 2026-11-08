import datetime as dt
import json
import math
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class November6Recovery(unittest.TestCase):
    def setUp(self):
        self.payload = json.loads((ROOT / 'data/us_analysis.json').read_text())
        self.entry = next(e for e in self.payload['entries'] if e['date'] == '2026-11-06')
        self.evidence = json.loads((ROOT / 'data/us-close-evidence-20261106.json').read_text())

    def test_completed_session_and_actual_collection(self):
        e = self.entry
        self.assertEqual(e['sessionVerification']['closedAt'], '2026-11-06T16:00:00-05:00')
        self.assertEqual(e['reportCutoffAt'], '2026-11-07T07:00:00+09:00')
        self.assertGreater(dt.datetime.fromisoformat(e['collectedAt']), dt.datetime.fromisoformat(e['reportCutoffAt']))
        self.assertEqual(len(self.payload['entries']), len({e['date'] for e in self.payload['entries']}))

    def test_full_prices_breadth_and_high_scope(self):
        rows = self.evidence['screens']['dailyRows']
        self.assertEqual(len(rows), 503)
        self.assertEqual(len({r['cik'] for r in rows}), 500)
        self.assertEqual(self.entry['breadth']['counts'], {'advancing': 184, 'declining': 318, 'unchanged': 1})
        self.assertEqual(self.entry['coverage']['full52WeekHistory'], 500)
        self.assertEqual(set(self.entry['coverage']['shortHistoryTickers']), {'FDXF', 'HONA', 'VYLR'})
        for r in rows:
            self.assertAlmostEqual(r['changePct'], 100 * (r['close'] / r['previousClose'] - 1))
            self.assertEqual(r['asOf'], '2026-11-06')
            self.assertEqual(r['previousSession'], '2026-11-05')

    def test_all_sector_returns_and_split_basis(self):
        self.assertEqual(len(self.entry['sectors']['rows']), 40)
        for row in self.entry['sectors']['rows']:
            calc = row['calculation']
            self.assertEqual(calc['anchors'], {'day': '2026-11-05', 'week': '2026-10-30', 'month': '2026-10-06'})
            self.assertEqual(calc['asOf'], '2026-11-06')
            for period, anchor in calc['anchors'].items():
                returns = [100 * (c['bars']['2026-11-06']['adjustedClose'] / c['bars'][anchor]['adjustedClose'] - 1) for c in calc['components']]
                self.assertAlmostEqual(row[period], round(sum(returns) / len(returns), 2))
            if row['ticker'] in ('SOXX', 'ITA'):
                self.assertGreater(row['day'], 0)
                self.assertGreater(row['month'], -50)

    def test_current_session_earnings_and_cutoff(self):
        rows = self.entry['earnings']['rows']
        self.assertEqual({r['ticker'] for r in rows}, {'BEN', 'CHTR', 'HUM', 'MRNA', 'PPL', 'VST'})
        for row in rows:
            self.assertEqual(row['releaseDate'], '2026-11-06')
            self.assertEqual(len(row['quarterlyHistory']['rows']), 4)
            self.assertEqual(row['presentationVersion'], 3)
            self.assertIsInstance(row['displayCallHighlights'], list)
            self.assertEqual(len(row['displayCallHighlights']), 3)
        self.assertEqual(next(r for r in rows if r['ticker'] == 'BEN')['releaseType'], 'preliminary')


if __name__ == '__main__':
    unittest.main()
