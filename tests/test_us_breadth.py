"""S&P 500 breadth is derived from verified, unrounded two-session closes."""
import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from validate_us_analysis import validate, validate_breadth
from build_us_breadth import build, derive_breadth


class USBreadthTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads((ROOT / 'data/us_analysis.json').read_text())
        self.entry = next(e for e in self.data['entries'] if e['date'] == '2026-10-22')
        self.breadth = self.entry['breadth']
        self.evidence = json.loads((ROOT / self.breadth['evidencePath']).read_text())

    def check(self):
        validate_breadth(self.breadth, self.entry, self.evidence)

    def test_exact_latest_snapshot_and_optional_historical_schema(self):
        validate(self.data)
        self.assertEqual(self.breadth['counts'], {'advancing': 336, 'declining': 166, 'unchanged': 1})
        self.assertEqual(self.breadth['companies'], 500)
        self.assertEqual(self.breadth['securities'], 503)
        self.assertEqual(self.breadth['validCount'], 503)
        self.assertEqual(self.breadth['missingTickers'], [])
        self.assertEqual(self.breadth['missingCount'], 0)
        self.assertTrue(all('breadth' not in e for e in self.data['entries'] if e['date'] < self.entry['date']))

    def test_reusable_builder_is_idempotent_and_preserves_every_other_panel(self):
        self.assertEqual(derive_breadth(self.entry, self.evidence), self.breadth)
        self.assertEqual(build(self.data), self.data)
        original = copy.deepcopy(self.data)
        self.entry.pop('breadth')
        self.assertEqual(build(self.data, self.entry['date']), original)
        self.assertNotIn('breadth', self.entry, 'Builder returns a candidate without mutating its input')

    def test_missing_latest_evidence_never_reuses_previous_breadth(self):
        self.entry['date'] = '2099-10-22'
        with self.assertRaises(FileNotFoundError):
            build(self.data)

    def test_company_denominator_and_wrong_counts_rejected(self):
        for patch in [dict(securities=500), dict(companies=503), dict(denominator='companies'),
                      dict(counts={'advancing': 335, 'declining': 167, 'unchanged': 1}),
                      dict(percentages={k: v / 500 * 100 for k, v in self.breadth['counts'].items()}),
                      dict(counts={'advancing': True, 'declining': 501, 'unchanged': 1})]:
            with self.subTest(patch=patch), self.assertRaises(AssertionError):
                validate_breadth({**self.breadth, **patch}, self.entry, self.evidence)

    def test_matching_totals_cannot_disguise_wrong_direction(self):
        self.breadth['counts']['advancing'] -= 1
        self.breadth['counts']['declining'] += 1
        self.breadth['percentages'] = {k: v / 503 * 100 for k, v in self.breadth['counts'].items()}
        with self.assertRaises(AssertionError):
            self.check()

    def test_dates_scope_and_evidence_reference_are_exact(self):
        for patch in [dict(universe='US'), dict(asOf='2026-10-21'), dict(previousSession='2026-10-20'),
                      dict(universeAsOf='2026-10-21'), dict(priceBasis='after_hours'),
                      dict(evidencePath='../other.json'), dict(evidenceRows='other.rows')]:
            with self.subTest(patch=patch), self.assertRaises(AssertionError):
                validate_breadth({**self.breadth, **patch}, self.entry, self.evidence)

    def test_duplicate_foreign_and_stale_evidence_rows_rejected(self):
        for patch in [dict(ticker='NOT_A_MEMBER'), dict(asOf='2026-10-21'),
                      dict(previousSession='2026-10-20'), dict(sourceIds=['invented'])]:
            evidence = copy.deepcopy(self.evidence)
            evidence['screens']['dailyRows'][0].update(patch)
            with self.subTest(patch=patch), self.assertRaises(AssertionError):
                validate_breadth(self.breadth, self.entry, evidence)
        self.evidence['screens']['dailyRows'].append(self.evidence['screens']['dailyRows'][0])
        with self.assertRaises(AssertionError):
            self.check()

    def test_null_zero_and_invalid_prices_are_not_unchanged(self):
        for bad in (None, 0, -1, True, '100'):
            evidence = copy.deepcopy(self.evidence)
            evidence['screens']['dailyRows'][0]['close'] = bad
            with self.subTest(bad=bad), self.assertRaises(AssertionError):
                validate_breadth(self.breadth, self.entry, evidence)

    def test_missing_security_is_explicit_and_denominator_uses_valid_only(self):
        row = self.evidence['screens']['dailyRows'].pop(0)
        self.assertGreater(row['close'], row['previousClose'])
        self.breadth.update(status='partial', validCount=502, missingCount=1, missingTickers=[row['ticker']])
        self.breadth['counts']['advancing'] -= 1
        self.breadth['percentages'] = {k: v / 502 * 100 for k, v in self.breadth['counts'].items()}
        self.evidence['screens']['coverage'].update(dailyValid=502, missingCount=1)
        self.check()
        self.breadth['missingTickers'] = ['UNKNOWN']
        with self.assertRaises(AssertionError):
            self.check()

    def test_direction_uses_raw_closes_not_rounded_change_percent(self):
        # Reporting a return rounded to zero must not turn a rising security into unchanged.
        for row in self.evidence['screens']['dailyRows']:
            row['changePct'] = 0
        self.check()

    def test_unavailable_cannot_claim_zero_percent(self):
        self.evidence['screens']['dailyRows'] = []
        self.evidence['screens']['coverage'].update(dailyValid=0, missingCount=503)
        self.breadth.update(status='unavailable', validCount=0, missingCount=503,
                            missingTickers=[r['ticker'] for r in self.entry['constituents']])
        self.breadth['counts'] = dict.fromkeys(self.breadth['counts'], 0)
        self.breadth['percentages'] = dict.fromkeys(self.breadth['percentages'], None)
        self.check()
        self.breadth['percentages']['unchanged'] = 0
        with self.assertRaises(AssertionError):
            self.check()


if __name__ == '__main__':
    unittest.main()
