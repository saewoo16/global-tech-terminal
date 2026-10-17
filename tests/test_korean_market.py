import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from validate_korean_market import validate
from update_korean_market import merge_series, as_number, collect_flows
from unittest.mock import patch


class KoreanMarketTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads((ROOT / 'data/korea-market.json').read_text())

    def test_snapshot_is_valid(self):
        self.assertEqual(validate(self.data), [])

    def test_deposits_are_never_split(self):
        data = copy.deepcopy(self.data)
        data['liquidity']['depositScope'] = 'KOSPI'
        self.assertTrue(any('market-wide' in x for x in validate(data)))

    def test_nan_and_numeric_strings_rejected(self):
        for value in (float('nan'), float('inf'), '100', True):
            data = copy.deepcopy(self.data)
            section = data['flows']['markets']['KOSPI']
            section['rows'] = [{'date': data['asOf'], 'foreign': value, 'institution': None, 'individual': None}]
            self.assertTrue(any('finite number' in x for x in validate(data)))

    def test_invalid_url_and_orphan_source_rejected(self):
        data = copy.deepcopy(self.data)
        data['sources'][0]['url'] = 'javascript:alert(1)'
        self.assertTrue(any('unsafe source' in x for x in validate(data)))
        data = copy.deepcopy(self.data)
        data['flows']['markets']['KOSPI']['sourceIds'] = ['does-not-exist']
        self.assertTrue(any('unknown source' in x for x in validate(data)))

    def test_coverage_must_match_observations(self):
        data = copy.deepcopy(self.data)
        section = data['flows']['markets']['KOSPI']
        section['rows'] = [{'date': data['asOf'], 'foreign': 0, 'institution': None, 'individual': None}]
        section['coverage'] = {'start': '1900-01-01', 'end': data['asOf'], 'count': 2}
        errors = validate(data)
        self.assertTrue(any('start mismatch' in x for x in errors))
        self.assertTrue(any('count mismatch' in x for x in errors))

    def test_unknown_is_not_zero(self):
        for series in self.data['liquidity']['series'].values():
            if series['status'] == 'unavailable':
                self.assertEqual(series['rows'], [])
                self.assertTrue(series['note'])

    def test_incremental_merge_preserves_good_history(self):
        section = {'rows': [{'date': '2026-10-12', 'value': 1}, {'date': '2026-10-13', 'value': 2}], 'coverage': {}}
        merge_series(section, [{'date': '2026-10-13', 'value': 3}, {'date': '2026-10-14', 'value': 4}], '2023-10-17')
        self.assertEqual([row['value'] for row in section['rows']], [1, 3, 4])
        before = copy.deepcopy(section)
        with self.assertRaises(ValueError):
            merge_series(section, [], '2023-10-17')
        self.assertEqual(section, before)

    def test_collector_refuses_missing_categories(self):
        raw = json.dumps({'content': [{'bizdate': '20261016', 'netAmounts': [{'investorGubun': '9000', 'diffValue': 1}]}]})
        with patch('update_korean_market.fetch', return_value=raw):
            with self.assertRaisesRegex(ValueError, 'missing investor'):
                collect_flows('KOSPI', '2026-10-17')

    def test_collector_rejects_boolean_and_nonfinite(self):
        for value in [True, float('nan'), float('inf')]:
            with self.assertRaises(ValueError):
                as_number(value)

    def test_incomplete_theme_cannot_be_partial_sum(self):
        data = copy.deepcopy(self.data)
        rows = data['themes']['monthly']['rows']
        row = next(r for r in rows if r['foreign'] is None)
        row['foreign'] = 0
        self.assertTrue(any('incomplete theme must stay null' in x for x in validate(data)))

    def test_daily_index_returns_are_validated(self):
        data = copy.deepcopy(self.data)
        data['indexMovers']['daily']['2026-10-16']['KOSPI200']['gainers'][0]['changePct'] += 1
        self.assertTrue(any('return arithmetic mismatch' in x for x in validate(data)))

    def test_alphanumeric_index_codes_preserved(self):
        all_rows = [row for index in self.data['indexMovers']['monthly'].values() for key in ['gainers', 'losers'] for row in index[key]]
        self.assertTrue(all(isinstance(row['code'], str) for row in all_rows))

    def test_existing_tabs_and_fifth_tab_present(self):
        html = (ROOT / 'index.html').read_text()
        for view in ['explorer', 'briefing', 'heatmap', 'rates', 'korea']:
            self.assertIn(f'id="{view}-panel"', html)
            self.assertIn(f'id="{view}-tab"', html)
        self.assertLess(html.index('data-tradingview-widget="BAMLH0A0HYM2EY"'), html.index('data-tradingview-widget="BAMLH0A0HYM2"'))


if __name__ == '__main__':
    unittest.main()
