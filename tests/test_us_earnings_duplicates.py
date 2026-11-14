"""Synthetic duplicate candidates never alter the published archive."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('validate_us', ROOT / 'scripts/validate_us_analysis.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class EarningsDuplicatesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.archive = json.loads((ROOT / 'data/us_analysis.json').read_text())

    def setUp(self):
        self.data = copy.deepcopy(self.archive)
        # The newest completed session can legitimately contain no confirmed releases.
        self.entry = next(e for e in self.data['entries'] if e['date'] == '2026-11-12')
        self.row = self.entry['earnings']['rows'][0]

    def add_copy(self, **changes):
        row = copy.deepcopy(self.row)
        row.update(changes)
        self.entry['earnings']['rows'].append(row)
        return row

    def test_real_archive_and_repeated_validation_are_unchanged(self):
        before = copy.deepcopy(self.data)
        for _ in range(2):
            self.assertEqual(mod.validate(self.data), len(self.data['entries']))
        self.assertEqual(self.data, before)

    def test_nov13_unverified_releases_do_not_inherit_nov12(self):
        next_session = next((e for e in self.data['entries'] if e['date'] == '2026-11-13'), None)
        if next_session is None:
            self.skipTest('November 13 close is not in this snapshot')
        self.assertEqual(next_session['earnings']['status'], 'no_verified_releases')
        self.assertEqual(next_session['earnings']['rows'], [])
        self.assertTrue(self.entry['earnings']['rows'])

    def test_identical_and_conflicting_announcements_rejected(self):
        self.add_copy()
        with self.assertRaisesRegex(AssertionError, 'Duplicate earnings announcement'):
            mod.validate(self.data)
        self.entry['earnings']['rows'][-1]['summary'] = 'Conflicting synthetic summary'
        with self.assertRaisesRegex(AssertionError, 'Duplicate earnings announcement'):
            mod.validate(self.data)

    def test_missing_release_type_is_results(self):
        self.row.pop('releaseType', None)
        self.add_copy(releaseType='results')
        with self.assertRaisesRegex(AssertionError, 'Duplicate earnings announcement'):
            mod.validate(self.data)

    def test_other_period_and_preliminary_release_are_distinct(self):
        self.row.pop('releaseType', None)
        self.add_copy(period='Synthetic other period')
        self.add_copy(releaseType='preliminary')
        mod.validate(self.data)

    def test_different_announcement_dates_and_companies_are_preserved(self):
        earlier = next(e for e in self.data['entries'] if e['date'] == '2026-11-11')
        # Use an existing valid historical announcement fixture, changing only
        # the company to another verified member shared by both sessions.
        prior = copy.deepcopy(earlier['earnings']['rows'][0])
        prior['ticker'] = self.row['ticker']
        earlier['earnings']['rows'] = [prior]
        mod.validate(self.data)

    def test_call_supplement_is_not_a_new_announcement(self):
        self.add_copy(callSupplement={'observedAt': '2026-11-08T01:00:00Z', 'note': 'Synthetic later call'})
        with self.assertRaisesRegex(AssertionError, 'Duplicate earnings announcement'):
            mod.validate(self.data)
        self.entry['earnings']['rows'].pop()
        self.row['callSupplement'] = {'observedAt': '2026-11-08T01:00:00Z', 'note': 'Synthetic later call'}
        mod.validate(self.data)
        self.assertEqual(self.row['releaseDate'], self.entry['date'])

    def test_actual_et_timestamp_not_kst_or_collection_date(self):
        copy_row = self.add_copy()
        # Same instant represented by a different timezone is the same release.
        if copy_row.get('releaseTiming', {}).get('publishedAt'):
            published = mod.market_time(copy_row['releaseTiming']['publishedAt'])
            copy_row['releaseTiming']['publishedAt'] = published.astimezone(mod.dt.timezone.utc).isoformat()
        with self.assertRaisesRegex(AssertionError, 'Duplicate earnings announcement'):
            mod.validate(self.data)


if __name__ == '__main__':
    unittest.main()
