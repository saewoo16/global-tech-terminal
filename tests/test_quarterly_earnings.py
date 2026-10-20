"""Regression checks for source-backed four-quarter earnings presentation."""
import json
import math
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


class QuarterlyEarningsTests(unittest.TestCase):
    def test_latest_reports_have_source_backed_four_quarter_history(self):
        for filename, market in [('briefings.json', 'KR'), ('us_analysis.json', None)]:
            data = json.loads((ROOT / 'data' / filename).read_text())
            entries = [e for e in data['entries'] if not market or e.get('market') == market]
            entry = max(entries, key=lambda e: e['date'])
            sources = {s['id'] for s in entry['sources']}
            for company in entry['earnings']['rows']:
                with self.subTest(company=company['ticker']):
                    history = company['quarterlyHistory']
                    self.assertTrue(history['unit'])
                    self.assertTrue(history['basis'])
                    rows = history['rows']
                    self.assertEqual(len(rows), 4)
                    self.assertEqual(len({r['period'] for r in rows}), 4)
                    self.assertEqual([r['period'] for r in rows], sorted(r['period'] for r in rows))
                    for row in rows:
                        self.assertTrue(row['sourceIds'])
                        self.assertLessEqual(set(row['sourceIds']), sources)
                        for key in ['revenue', 'operatingIncome', 'operatingMargin', 'netIncome']:
                            self.assertTrue(row[key] is None or isinstance(row[key], (int, float)))
                            if row[key] is not None:
                                self.assertTrue(math.isfinite(row[key]))
                        if row['operatingIncome'] is None:
                            self.assertIsNone(row['operatingMargin'])
                        elif row['revenue']:
                            self.assertAlmostEqual(row['operatingMargin'], 100 * row['operatingIncome'] / row['revenue'], delta=0.01)
