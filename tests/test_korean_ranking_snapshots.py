"""A later provider aggregate must not replace a sourced close snapshot."""
import copy
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from update_korean_market import merge_daily_rankings, update_rankings


def rank(value, day='2026-10-21'):
    row = {'code': '005930', 'value': value}
    return {'status': 'verified', 'unit': 'KRW', 'sourceIds': ['naver-live'],
            'rows': [row], 'byMarket': {'KOSPI': [copy.deepcopy(row)]},
            'coverage': {'start': day, 'end': day}}


class DailyRankingSnapshotTests(unittest.TestCase):
    def frozen(self):
        old = rank(4721.6)
        old['unit'] = '억원'
        old['sourceIds'] = ['yonhap-close']
        old['coverage']['snapshotAt'] = '2026-10-21T15:30:00+09:00'
        return old

    def test_later_aggregate_does_not_replace_timestamped_snapshot(self):
        old = {'foreign': self.frozen()}
        original = copy.deepcopy(old)
        got = merge_daily_rankings(old, {'foreign': rank(460034084000)}, '2026-10-21')
        self.assertEqual(got, original)
        self.assertEqual(old, original)

    def test_explicit_snapshot_policy_is_preserved(self):
        old = self.frozen()
        del old['coverage']['snapshotAt']
        old['snapshotPolicy'] = 'Reviewed closing snapshot; coordinated revisions only'
        self.assertEqual(merge_daily_rankings({'foreign': old}, {'foreign': rank(1)}, '2026-10-21')['foreign'], old)

    def test_unfrozen_sections_and_new_sessions_still_update(self):
        old = {'foreign': self.frozen(), 'institution': rank(1)}
        got = merge_daily_rankings(old, {'foreign': rank(1), 'institution': rank(123456789)}, '2026-10-21')
        self.assertEqual(got['foreign'], old['foreign'])
        self.assertEqual(got['institution']['rows'][0]['value'], 1.234568)
        newer = merge_daily_rankings({}, {'foreign': rank(123456789, '2026-10-22')}, '2026-10-22')
        self.assertEqual(newer['foreign']['coverage']['end'], '2026-10-22')

    def test_integration_preserves_snapshot_and_refreshes_periods(self):
        frozen = self.frozen()
        payload = {'asOf': '2026-10-21', 'sources': [], 'rankings': {
            'daily': {'2026-10-21': {'foreign': frozen}}, 'dates': ['2026-10-21']}}
        incoming = {'asOf': '2026-10-21', 'sources': [], 'rankings': {
            'daily': {'2026-10-21': {'foreign': rank(460034084000)}},
            'periods': {'week': {'foreign': rank(100000000)}, 'month': {'foreign': rank(200000000)}}}}
        with patch('update_korean_market.collect_rankings', return_value=incoming):
            update_rankings(payload)
        self.assertEqual(payload['rankings']['daily']['2026-10-21']['foreign'], frozen)
        self.assertEqual(payload['rankings']['aggregate5d']['foreign']['rows'][0]['value'], 1)
        self.assertEqual(payload['rankings']['monthly']['foreign']['rows'][0]['value'], 2)

    def test_timestamp_without_verified_sources_is_not_frozen(self):
        for field, val in [('status', 'unavailable'), ('sourceIds', [])]:
            old = self.frozen(); old[field] = val
            got = merge_daily_rankings({'foreign': old}, {'foreign': rank(100000000)}, '2026-10-21')
            self.assertEqual(got['foreign']['rows'][0]['value'], 1)

if __name__ == '__main__':
    unittest.main()
