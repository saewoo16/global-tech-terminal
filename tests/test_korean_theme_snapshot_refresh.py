"""Generic refreshes must preserve dated official and closing observations."""
import copy
from datetime import date, timedelta
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from korean_theme_source import build, normalize

INVESTORS = ('foreign', 'institution')


def partial_provider_result(day):
    """Synthetic top-100 response with only two observed constituent amounts."""
    target = date.fromisoformat(day)
    responses = {}
    for market, code in [('KOSPI', '005930'), ('KOSDAQ', '247540')]:
        for investor in ('FOREIGNER', 'ORGANIZATION'):
            for period, offset in [('DAY', 0), ('WEEK', 6), ('MONTH', 30)]:
                responses[f'{market}_{investor}_{period}'] = {
                    'url': 'https://stock.naver.com/api/test?periodType=' + period,
                    'data': {'sections': {'buyRankList': [{
                        'type': 'ST', 'itemcode': code, 'accTradeAmount': '123',
                        'bizdateFrom': (target - timedelta(days=offset)).strftime('%Y%m%d'),
                        'bizdateTo': target.strftime('%Y%m%d'), 'estimated': False,
                    }], 'sellRankList': []}},
                }
    return build(responses=responses)


class KoreanThemeSnapshotRefreshTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload = json.loads((ROOT / 'data/korea-market.json').read_text())

    def test_both_official_policies_survive_same_day_partial_refresh_unchanged(self):
        for day, policy in [
            ('2026-11-04', 'verified_official_krx_daily'),
            ('2026-11-05', 'verified_official_krx_observed_provisional'),
        ]:
            with self.subTest(day=day, policy=policy):
                previous = copy.deepcopy(self.payload['themes'])
                original = copy.deepcopy(previous)
                self.assertEqual(previous['daily'][day]['snapshotPolicy'], policy)
                incoming = partial_provider_result(day)
                original_incoming = copy.deepcopy(incoming)
                actual = normalize(incoming, previous['dates'], previous)
                self.assertEqual(actual['daily'][day], original['daily'][day])
                self.assertEqual(previous, original)
                self.assertEqual(incoming, original_incoming)
                for period, section in [('1w', 'aggregate5d'), ('1m', 'monthly')]:
                    self.assertEqual(actual[section]['status'], 'partial')
                    self.assertEqual(actual[section]['coverage']['start'], incoming['periods'][period]['from'])
                    self.assertEqual(actual[section]['coverage']['end'], day)
                    self.assertTrue(actual[section]['sourceIds'])
                    self.assertTrue(all(sid.endswith(day.replace('-', ''))
                                        for sid in actual[section]['sourceIds']))

    def test_provisional_partial_status_nulls_and_exact_coverage_are_preserved(self):
        previous = copy.deepcopy(self.payload['themes'])
        actual = normalize(partial_provider_result('2026-11-05'), previous['dates'], previous)
        section = actual['daily']['2026-11-05']
        self.assertEqual(section['status'], 'partial')
        self.assertEqual(len(section['rows']), 13)
        self.assertEqual(sum(row['coverage']['foreign']['status'] == 'complete'
                             for row in section['rows']), 13)
        self.assertEqual(sum(row['coverage']['institution']['status'] == 'complete'
                             for row in section['rows']), 3)
        self.assertEqual(section['sourceIds'], previous['daily']['2026-11-05']['sourceIds'])
        missing_count = 0
        for row in section['rows']:
            cell = row['coverage']['institution']
            if cell['status'] != 'complete':
                missing_count += 1
                for value in (row['institution'], cell['netBuyKRW'], cell['netBuyEok'], cell['rank']):
                    self.assertIsNone(value)
                self.assertEqual(cell['knownSubtotalKRW'], sum(
                    item['netBuyKRW'] for item in cell['memberFlows'] if item['netBuyKRW'] is not None))
                self.assertEqual([item['code'] for item in cell['missingMembers']], [
                    item['code'] for item in cell['memberFlows'] if item['netBuyKRW'] is None])
        self.assertEqual(missing_count, 10)

    def test_protected_same_day_keeps_prior_catalog_when_catalog_changes(self):
        previous = copy.deepcopy(self.payload['themes'])
        original = copy.deepcopy(previous)
        incoming = partial_provider_result('2026-11-05')
        incoming.update(basketDefinitionVersion='synthetic-new-catalog',
                        membershipAsOf='2026-11-05', marketCapAsOf='2026-11-05')
        actual = normalize(incoming, previous['dates'], previous)
        saved = actual['daily']['2026-11-05']
        expected = copy.deepcopy(previous['daily']['2026-11-05'])
        catalog = {basket['id']: basket for basket in previous['baskets']}
        for row in expected['rows']:
            for field in ('members', 'displayMembers', 'displayMembersByMarket',
                          'marketCapAsOf', 'sourceCategories', 'scopeNote',
                          'excludedMembers', 'providerUnionCount'):
                row.setdefault(field, copy.deepcopy(catalog[row['id']][field]))
            row.setdefault('membershipAsOf', expected['membershipAsOf'])
            row.setdefault('marketCapAsOf', expected['marketCapAsOf'])
        self.assertEqual(saved, expected)
        self.assertEqual(actual['basketDefinitionVersion'], 'synthetic-new-catalog')
        self.assertEqual(actual['aggregate5d']['membershipAsOf'], '2026-11-05')
        self.assertEqual(previous, original)

    def test_unprotected_theme_day_still_refreshes(self):
        for policy in (None, 'unrecognized-policy'):
            with self.subTest(policy=policy):
                previous = copy.deepcopy(self.payload['themes'])
                previous['daily']['2026-11-05']['snapshotPolicy'] = policy
                incoming = partial_provider_result('2026-11-05')
                actual = normalize(incoming, previous['dates'], previous)
                expected = normalize(incoming, ['2026-11-05'])['daily']['2026-11-05']
                self.assertEqual(actual['daily']['2026-11-05'], expected)
                self.assertNotIn('snapshotPolicy', actual['daily']['2026-11-05'])

    def test_new_theme_day_advances_without_revising_official_history(self):
        previous = copy.deepcopy(self.payload['themes'])
        day = (date.fromisoformat(max(previous['dates'])) + timedelta(days=1)).isoformat()
        incoming = partial_provider_result(day)
        actual = normalize(incoming, [*previous['dates'], day], previous)
        self.assertEqual(actual['daily']['2026-11-05'], previous['daily']['2026-11-05'])
        self.assertEqual(actual['daily'][day], normalize(incoming, [day])['daily'][day])
        self.assertEqual(actual['aggregate5d']['coverage']['end'], day)
        self.assertEqual(actual['monthly']['coverage']['end'], day)


if __name__ == '__main__':
    unittest.main()
