import copy
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from korean_futures_source import parse_foreign_page, exact_integer, collect_foreign_flows, update_quality, parse_open_interest, OI_CONTRACT, OI_CONTRACT_NAME
from validate_korean_market import validate
from update_korean_market import merge_series


class KoreanFuturesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads((ROOT / 'data/korea-market.json').read_text())

    def source_page(self, day='20261016', buy=147478, sell=151678, net=-4200):
        return {'number': 0, 'content': [{'bizdate': day, 'netAmounts': [
            {'investorGubun': '9000', 'buyQuant': buy, 'sellQuant': sell, 'diffValue': net},
            {'investorGubun': '1000', 'diffValue': -net}]}]}

    def test_contract_parser_preserves_units_and_identity(self):
        page = self.source_page()
        page['number'] = '0'  # Public API serializes this index as a numeric string.
        row = parse_foreign_page(page, '2026-10-16', 0)[0]
        self.assertEqual(row['foreign'], -4200)
        self.assertEqual(row['buy'], 147478)
        self.assertEqual(row['sell'], 151678)
        self.assertNotIn('sourceBalanceWarning', row)
        for value in [1.1, True, None, '1.0', '1e3', float('nan'), '--1']:
            with self.assertRaises(ValueError):
                exact_integer(value)

    def test_bad_contract_arithmetic_and_wrong_page_fail(self):
        for page in [self.source_page(net=-4000), self.source_page(buy=-1), self.source_page(day='20261017')]:
            with self.assertRaises(ValueError):
                parse_foreign_page(page, '2026-10-16', 0)
        with self.assertRaises(ValueError):
            parse_foreign_page(self.source_page(), '2026-10-16', 1)
        with patch('korean_futures_source.fetch', side_effect=[self.source_page(), {**self.source_page(), 'number': 1}]):
            with self.assertRaisesRegex(ValueError, 'duplicate futures'):
                collect_foreign_flows('2026-10-16')

    def test_source_imbalance_is_flagged_without_changing_foreign(self):
        page = self.source_page()
        page['content'][0]['netAmounts'][1]['diffValue'] += 135
        row = parse_foreign_page(page, '2026-10-16', 0)[0]
        self.assertEqual(row['foreign'], -4200)
        self.assertTrue(row['sourceBalanceWarning'])
        self.assertEqual(row['sourceInvestorNetImbalance'], 135)
        section = {'rows': [row]}
        update_quality(section)
        self.assertEqual(section['status'], 'partial')
        self.assertEqual(section['qualityFlags']['affectedDates'], ['2026-10-16'])

    def test_snapshot_actual_foreign_sums_and_flags(self):
        # Fixed, independently audited October 16 checkpoint; live refreshes may append rows.
        section = {'rows': [r for r in self.data['futures']['foreignFlows']['rows'] if r['date'] <= '2026-10-16']}
        self.assertGreaterEqual(len(section['rows']), 252)
        self.assertEqual(section['rows'][-1]['foreign'], -4200)
        for count, expected in [(5, 9580), (21, 6800), (63, 18244), (126, 26101), (252, -34948)]:
            rows = section['rows'][-count:]
            self.assertEqual(sum(row['foreign'] for row in rows), expected)
            self.assertEqual(sum(bool(row.get('sourceBalanceWarning')) for row in rows), 6 if count == 252 else 0)
        observed = {row['date'] for row in section['rows']}
        expected_flags = set(self.data['futures']['foreignFlows']['qualityFlags']['affectedDates']) & observed
        self.assertEqual({row['date'] for row in section['rows'] if row.get('sourceBalanceWarning')}, expected_flags)
        for row in section['rows']:
            self.assertEqual(row['buy'] - row['sell'], row['foreign'])

    def test_rolling_history_cutoff_preserves_dynamic_coverage_and_checks(self):
        data = copy.deepcopy(self.data)
        section = data['futures']['foreignFlows']
        original_count = len(section['rows'])
        next_start = section['rows'][1]['date']
        merge_series(section, [copy.deepcopy(section['rows'][-1])], next_start)
        update_quality(section)
        self.assertEqual(len(section['rows']), original_count - 1)
        self.assertEqual(section['coverage']['start'], next_start)
        self.assertEqual(validate(data), [])

    def test_validator_rejects_wrong_units_positions_and_fractional_oi(self):
        cases = [('unit', '억원', 'explicit unit'), ('holderScope', 'foreign', 'market-wide')]
        for field, value, expected in cases:
            data = copy.deepcopy(self.data)
            data['futures']['openInterest'][field] = value
            self.assertTrue(any(expected in e for e in validate(data)))
        for value in [-1, .5]:
            data = copy.deepcopy(self.data)
            part = data['futures']['openInterest']
            part.update(status='verified', rows=[{'date': data['asOf'], 'openInterest': value}],
                        sourceIds=[data['sources'][0]['id']], coverage={'start': data['asOf'], 'end': data['asOf'], 'count': 1})
            self.assertTrue(any('open interest cannot' in e or 'whole numbers' in e for e in validate(data)))

    def test_quality_warnings_and_contract_units_cannot_be_dropped(self):
        mutations = [
            lambda part: part.update(unit='억원'),
            lambda part: next(row for row in part['rows'] if row.get('sourceBalanceWarning')).pop('sourceBalanceWarning'),
            lambda part: part['qualityFlags'].update(count=0),
            lambda part: part['windowChecks']['252'].update(flaggedDates=[]),
            lambda part: part['windowChecks']['252'].update(foreignTotal=0)]
        for mutate in mutations:
            data = copy.deepcopy(self.data)
            mutate(data['futures']['foreignFlows'])
            self.assertTrue(any('futures.foreignFlows:' in e for e in validate(data)))

    def test_fixed_oi_contract_validation_and_stale_failure(self):
        master = {'data': [{'symbolCode': OI_CONTRACT, 'name': OI_CONTRACT_NAME}]}
        history = {'data': [{'date': '2026-10-16T00:00:00', 'unsettledVolume': 148415}]}
        rows = parse_open_interest(master, history, '2026-10-16')
        self.assertEqual(rows[0]['openInterest'], 148415)
        self.assertEqual(rows[0]['contractCode'], OI_CONTRACT)
        for broken in [{'data': []}, {'data': [{'symbolCode': OI_CONTRACT, 'name': 'F 202703'}]}]:
            with self.assertRaisesRegex(ValueError, 'absent'):
                parse_open_interest(broken, history, '2026-10-16')
        with self.assertRaisesRegex(ValueError, 'no automatic roll'):
            parse_open_interest(master, history, '2026-10-16', 'other', 'F 202703')
        with self.assertRaisesRegex(ValueError, 'stale'):
            parse_open_interest(master, history, '2026-10-17')
        for value in [None, -1, 1.1, '10', True]:
            with self.assertRaisesRegex(ValueError, 'integral'):
                parse_open_interest(master, {'data': [{'date': '2026-10-16', 'unsettledVolume': value}]}, '2026-10-16')
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            parse_open_interest(master, {'data': history['data'] * 2}, '2026-10-16')

    def test_fixed_oi_snapshot_is_not_stitched_or_foreign_only(self):
        part = self.data['futures']['openInterest']
        self.assertEqual(part['holderScope'], 'market')
        self.assertEqual(part['contractCode'], OI_CONTRACT)
        snapshot = [r for r in part['rows'] if r['date'] <= '2026-10-16']
        self.assertGreaterEqual(len(snapshot), 2)
        self.assertEqual(snapshot[-1]['openInterest'], 148415)
        self.assertEqual(snapshot[-1]['openInterest'] - snapshot[-2]['openInterest'], -6004)
        self.assertEqual({r['contractCode'] for r in part['rows']}, {OI_CONTRACT})
        data = copy.deepcopy(self.data)
        data['futures']['openInterest']['rows'][0]['contractCode'] = 'different-contract'
        self.assertTrue(any('fixed contract mismatch' in e for e in validate(data)))

    def test_classification_is_exact_single_source_join_and_preserves_cap(self):
        mapping = json.loads((ROOT / 'data/korea-heatmap-industries.json').read_text())
        rows = [row for part in self.data['heatmaps']['markets'].values() for row in part['rows']]
        codes = {row['code'] for row in rows}
        self.assertEqual(len(codes), len(rows))
        self.assertEqual(set(mapping['byCode']), codes)
        self.assertEqual(mapping['coverage']['total'], len(rows))
        unknown = {r['code'] for r in rows if r['industry']['id'] == 'unclassified'}
        self.assertEqual(mapping['coverage']['classified'], len(rows) - len(unknown))
        self.assertEqual(mapping['coverage']['unclassified'], len(unknown))
        self.assertEqual(mapping['asOf'], self.data['heatmaps']['classification']['asOf'])
        self.assertLessEqual(mapping['asOf'], self.data['heatmaps']['asOf'])
        self.assertEqual(mapping['conflictsInUniverse'], [])
        self.assertEqual({r['code'] for r in mapping['unclassified']}, unknown)
        self.assertTrue(all(r.get('reason') for r in mapping['unclassified']))
        for part in self.data['heatmaps']['markets'].values():
            self.assertEqual(sum(row['marketCapKRW'] for row in part['rows']), part['totalDisplayedMarketCapKRW'])
            for row in part['rows']:
                self.assertEqual(row['industry'], mapping['byCode'][row['code']])
        data = copy.deepcopy(self.data)
        data['heatmaps']['markets']['KOSPI']['rows'][0]['industry'] = {'id': 'unclassified', 'name': 'guess'}
        self.assertTrue(any('unknown cannot be guessed' in e for e in validate(data)))


if __name__ == '__main__':
    unittest.main()
