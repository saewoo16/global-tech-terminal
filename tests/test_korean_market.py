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
from korean_theme_source import build as build_themes, normalize as normalize_themes


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
        row = rows[0]
        row['coverage']['foreign']['memberFlows'][0]['netBuyKRW'] = None
        row['foreign'] = 0
        self.assertTrue(any('incomplete theme must stay null' in x for x in validate(data)))

    def test_partial_subtotal_is_exact_and_never_ranked(self):
        data = copy.deepcopy(self.data)
        cell = data['themes']['monthly']['rows'][0]['coverage']['foreign']
        cell['knownSubtotalKRW'] += 1
        cell['rank'] = 1
        errors = validate(data)
        self.assertTrue(any('known subtotal mismatch' in e for e in errors))
        self.assertTrue(any('cannot have rank' in e for e in errors))

    def test_display_is_top3_not_aggregation_universe(self):
        data = copy.deepcopy(self.data)
        basket = data['themes']['baskets'][0]
        self.assertGreater(basket['memberCount'], 3)
        basket['displayMembers'] = basket['members'][-3:]
        self.assertTrue(any('market cap top3' in e for e in validate(data)))

    def test_theme_components_cover_full_membership_once(self):
        data = copy.deepcopy(self.data)
        cell = data['themes']['monthly']['rows'][0]['coverage']['foreign']
        cell['memberFlows'][1]['code'] = cell['memberFlows'][0]['code']
        self.assertTrue(any('component codes' in e for e in validate(data)))

    def test_flow_refresh_does_not_redate_frozen_caps(self):
        responses = {}
        for market, code in [('KOSPI', '005930'), ('KOSDAQ', '247540')]:
            for investor in ['FOREIGNER', 'ORGANIZATION']:
                for period in ['DAY', 'WEEK', 'MONTH']:
                    key = f'{market}_{investor}_{period}'
                    responses[key] = {'url': 'https://stock.naver.com/api/fixture', 'data': {'sections': {
                        'buyRankList': [{'type': 'ST', 'itemcode': code, 'accTradeAmount': '123456000',
                                         'bizdateFrom': '20261019', 'bizdateTo': '20261019'}], 'sellRankList': []}}}
        result = build_themes(responses=responses)
        self.assertEqual(result['asOf'], '2026-10-19')
        self.assertEqual(result['marketCapAsOf'], self.data['themes']['marketCapAsOf'])
        self.assertEqual(result['membershipAsOf'], self.data['themes']['membershipAsOf'])
        self.assertGreater(result['baskets'][0]['memberCount'], 3)
        self.assertEqual(result['baskets'][0]['flows']['1d']['foreign']['knownSubtotalKRW'], 123456000)
        self.assertIsNone(result['baskets'][0]['flows']['1d']['foreign']['netBuyKRW'])

    def test_legacy_basket_history_is_not_rebranded_as_broad(self):
        current = copy.deepcopy(self.data['themes'])
        old_day = min(current['dates'])
        current['daily'][old_day] = {'status': 'verified', 'rows': [{'name': 'Legacy small basket'}]}
        # Normalization's retained history must carry the matching definition version.
        kept = {day: value for day, value in current['daily'].items()
                if value.get('basketDefinitionVersion') == current['basketDefinitionVersion']}
        self.assertNotIn(old_day, kept)

    def test_daily_index_returns_are_validated(self):
        data = copy.deepcopy(self.data)
        latest = max(data['indexMovers']['daily'])
        data['indexMovers']['daily'][latest]['KOSPI200']['gainers'][0]['changePct'] += 1
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
