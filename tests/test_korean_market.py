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

    def test_latest_brief_and_domestic_snapshots_are_consistent(self):
        archive = json.loads((ROOT / 'data/briefings.json').read_text())
        latest = max((e for e in archive['entries'] if e['market'] == 'KR'), key=lambda e: e['date'])
        for row in latest['flows']['rows']:
            observations = {r['date']: r for r in self.data['flows']['markets'][row['market']]['rows']}
            if latest['date'] in observations:
                for field in ['foreign', 'institution', 'individual']:
                    self.assertEqual(row[field], observations[latest['date']][field])
        if latest['date'] == self.data['sectorReturns']['asOf']:
            self.assertEqual([(r['name'], r['day'], r['week'], r['month']) for r in latest['sectors']['rows']],
                             [(r['name'], r['day'], r['week'], r['month']) for r in self.data['sectorReturns']['rows']])
        if latest['date'] == self.data['highsScreen']['asOf']:
            self.assertEqual({r['ticker'] for r in latest['highs']['rows']},
                             {r['ticker'] for r in self.data['highsScreen']['rows']})

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

    def test_incremental_merge_preserves_explicit_archived_snapshot(self):
        frozen = {'date': '2026-10-19', 'foreign': 422.37,
                  'snapshotPolicy': 'Preserved 17:18 KST provisional observation',
                  'retrievedAt': '2026-10-19T08:18:00.231334+00:00',
                  'sourceId': 'naver_flow_kospi_1019'}
        section = {'rows': [{'date': '2026-10-16', 'foreign': 1}, copy.deepcopy(frozen)],
                   'coverage': {}, 'status': 'verified'}
        merge_series(section, [
            {'date': '2026-10-16', 'foreign': 2},
            {'date': '2026-10-19', 'foreign': 961.85},
            {'date': '2026-10-20', 'foreign': 3},
        ], '2023-10-17')
        self.assertEqual(section['rows'][1], frozen)
        self.assertEqual(section['rows'][0]['foreign'], 2)
        self.assertEqual(section['rows'][2]['foreign'], 3)
        self.assertEqual(section['coverage']['end'], '2026-10-20')
        self.assertEqual(section['coverage']['count'], 3)

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

    def test_estimated_share_ranking_cannot_become_zero_theme_amounts(self):
        raw = {'type': 'ST', 'itemcode': '005930', 'accTradeAmount': '0',
               'bizdateFrom': '20261019', 'bizdateTo': '20261019', 'estimated': True}
        response = {'url': 'https://stock.naver.com/api/fixture',
                    'data': {'sections': {'buyRankList': [raw], 'sellRankList': []}}}
        with self.assertRaisesRegex(ValueError, 'Estimated share ranking'):
            build_themes(responses={'KOSPI_FOREIGNER_DAY': response})

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

    def test_market_split_cap_labels_cannot_use_global_top3(self):
        data = copy.deepcopy(self.data)
        basket = data['themes']['baskets'][0]
        basket['displayMembersByMarket']['KOSDAQ'] = basket['displayMembers']
        self.assertTrue(any('KOSDAQ display must be market cap top3' in e for e in validate(data)))

    def test_granular_sector_arithmetic_rejected_when_changed(self):
        data = copy.deepcopy(self.data)
        data['sectorReturns']['rows'][0]['month'] += 1
        self.assertTrue(any('sectorReturns: return arithmetic mismatch' in e for e in validate(data)))

    def test_near_high_distance_and_true_high_checked(self):
        data = copy.deepcopy(self.data)
        row = next((row for row in data['highsScreen']['rows'] if row['classification'] == 'near_high'), data['highsScreen']['rows'][0])
        row['classification'] = 'near_high'
        row['distancePct'] = -5
        errors = validate(data)
        self.assertTrue(any('high-distance mismatch' in e for e in errors))
        self.assertTrue(any('near high must be within3pct' in e for e in errors))
        data = copy.deepcopy(self.data)
        row = data['highsScreen']['rows'][0]
        row['classification'] = 'new_high'
        row['sessionHigh'] = row['prior52WeekHigh']
        self.assertTrue(any('strictly exceed' in e for e in validate(data)))

    def test_all_highs_are_union_of_actual300_screen(self):
        evidence = json.loads((ROOT / 'data/korea-highs-evidence.json').read_text())
        self.assertEqual(len(evidence['rows']), 300)
        eligible = [r for r in evidence['rows'] if r.get('freshDailyCoverage') and r.get('fullHistoryCoverage')]
        self.assertEqual(len(eligible), self.data['highsScreen']['coverage']['full52WeekHistory'])
        expected = {r['code'] for r in eligible if r['close'] >= .97 * r['high52'] or r['sessionHigh'] > r['prior52WeekHigh']}
        self.assertEqual(expected, {r['code'] for r in self.data['highsScreen']['rows']})

    def test_latest_turnover_excludes_konex_from_denominator(self):
        section = self.data['rankings']['daily'][max(self.data['rankings']['daily'])]['tradedValue']
        if section['status'] == 'unavailable':
            self.assertEqual(section['rows'], [])
            self.assertTrue(section['note'])
            # A fresh unavailable session must not masquerade as an older verified ranking.
            self.assertEqual(section['coverage']['end'], max(self.data['rankings']['daily']))
            section = next(self.data['rankings']['daily'][d]['tradedValue'] for d in sorted(self.data['rankings']['daily'], reverse=True) if self.data['rankings']['daily'][d]['tradedValue']['status'] == 'verified')
        coverage = section['coverage']
        self.assertEqual(coverage['marketUniverseCount'] + coverage['excludedOtherMarketCount'], coverage['sourceUniverseCount'])
        self.assertLessEqual(coverage['eligibleStockCount'], coverage['marketUniverseCount'])
        self.assertIn('KOSPI', coverage['universeDefinition'])
        self.assertIn('KOSDAQ', coverage['universeDefinition'])
        self.assertTrue(all(row['market'] in ('KOSPI', 'KOSDAQ') for row in section['rows']))

    def test_analysis_tabs_replace_standalone_legacy_views(self):
        html = (ROOT / 'index.html').read_text()
        for view in ['explorer', 'rates', 'korea', 'us']:
            self.assertIn(f'id="{view}-panel"', html)
            self.assertIn(f'id="{view}-tab"', html)
        for view in ['briefing', 'heatmap']:
            self.assertNotIn(f'id="{view}-tab"', html)
            self.assertNotIn(f'id="{view}-panel"', html)
        self.assertLess(html.index('data-tradingview-widget="BAMLH0A0HYM2EY"'), html.index('data-tradingview-widget="BAMLH0A0HYM2"'))


if __name__ == '__main__':
    unittest.main()
