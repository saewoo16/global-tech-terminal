import copy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('short_balance', ROOT / 'scripts/manage_korean_short_balance.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def fixture():
    source = {'id': 'synthetic-test-only', 'title': 'Unit test only', 'url': 'https://data.krx.co.kr/contents/MDC/MDI/mdiLoader/index.cmd?menuId=MDC0203', 'observedAt': '2026-11-01T07:36:00Z'}
    rows = [{'code': f'{i:06}', 'name': 'Synthetic test issuer', 'market': 'KOSPI' if i < 15 else 'KOSDAQ', 'balanceKRW': '90071992547409930', 'marketCapKRW': '900719925474099300', 'ratioPct': '10.00', 'observedAt': source['observedAt'], 'sourceIds': [source['id']], 'history': []} for i in range(30)]
    return {'schemaVersion': 1, 'metric': m.METRIC, 'unit': 'KRW', 'investorSplit': 'unavailable', 'status': 'verified', 'asOf': '2026-10-28', 'observedAt': source['observedAt'], 'coverage': {'markets': m.MARKETS, 'complete': True, 'scope': 'whole-market', 'evidenceNote': 'Synthetic test fixture only', 'count': 30, 'countByMarket': {'KOSPI': 15, 'KOSDAQ': 15}}, 'rows': rows, 'sources': [source]}


class ShortBalanceTests(unittest.TestCase):
    def test_published_payload(self):
        m.validate(json.loads((ROOT / 'data/korean_short_balance.json').read_text()))

    def test_alphanumeric_security_code(self):
        p = fixture()
        p['rows'][0]['code'] = '0009K0'
        self.assertEqual(m.validate(p)['rows'][0]['code'], '0009K0')
        p['rows'][0]['code'] = '0009k0'
        with self.assertRaises(ValueError): m.validate(p)

    def test_exact_amount(self):
        p = fixture()
        self.assertEqual(m.validate(p)['rows'][0]['balanceKRW'], '90071992547409930')
        p['rows'][0]['balanceKRW'] = 90071992547409930
        with self.assertRaises(ValueError): m.validate(p)

    def test_reject_bad_semantics_coverage(self):
        for key, value in [('metric', 'short-sale-trading'), ('investorSplit', 'foreign'), ('unit', '억원')]:
            p = fixture(); p[key] = value
            with self.assertRaises(ValueError): m.validate(p)
        p = fixture(); p['coverage']['complete'] = False
        with self.assertRaises(ValueError): m.validate(p)
        p = fixture(); p['rows'][0]['ratioPct'] = '11.00'
        with self.assertRaises(ValueError): m.validate(p)
        p = fixture(); p['rows'][0]['sourceIds'] = ['missing']
        with self.assertRaises(ValueError): m.validate(p)

    def test_real_reference_dates_missing_and_zero(self):
        p = fixture(); row = p['rows'][0]
        self.assertIsNone(m.change(row, p['asOf'], 7))
        def point(d, balance):
            return {**{k: row[k] for k in ('marketCapKRW', 'observedAt', 'sourceIds')}, 'balanceKRW': balance, 'ratioPct': '5.00', 'date': d}
        row['history'] = [point('2026-09-28', '45035996273704965'), point('2026-10-20', '45035996273704965')]
        m.validate(p)
        self.assertEqual(m.change(row, p['asOf'], 7), {'date': '2026-10-20', 'pct': '100'})
        self.assertEqual(m.change(row, p['asOf'], 30)['date'], '2026-09-28')
        row['history'][-1]['balanceKRW'] = '0'
        self.assertIsNone(m.change(row, p['asOf'], 7))

    def test_union_merge_prunes_only_unselected_history(self):
        old = fixture(); new = fixture(); new['asOf'] = '2026-10-29'
        selected = m.ranking_codes(new['rows'])
        new['coverage'].update(historyScope='current-ranking-union', historySecurityCount=len(selected))
        result = m.merge(old, new)
        self.assertEqual({r['code'] for r in result['rows'] if r['history']}, selected)
        self.assertEqual(len(result['rows']), 30)
        self.assertEqual({r['history'][0]['date'] for r in result['rows'] if r['history']}, {'2026-10-28'})

    def test_source_ratio_precision_boundary(self):
        p = fixture()
        row = p['rows'][0]
        row.update(balanceKRW='1005', marketCapKRW='100000', ratioPct='1.00')
        m.validate(p)  # exact half-unit boundary is accepted, not rounded away
        row['balanceKRW'] = '1006'
        with self.assertRaises(ValueError): m.validate(p)
        row['ratioPct'] = '1.01'
        m.validate(p)

    def test_history_integrity(self):
        p = fixture(); row = p['rows'][0]
        point = {k: row[k] for k in ('balanceKRW', 'marketCapKRW', 'ratioPct', 'observedAt', 'sourceIds')}
        point['date'] = '2026-10-29'; row['history'] = [point]
        with self.assertRaises(ValueError): m.validate(p)
        point['date'] = p['asOf']; row['history'] = [point, copy.deepcopy(point)]
        with self.assertRaises(ValueError): m.validate(p)

    def test_preserve_history_and_reject_regression(self):
        old = fixture(); new = fixture(); new['asOf'] = '2026-10-29'
        result = m.merge(old, new)
        self.assertEqual(result['rows'][0]['history'][0]['date'], '2026-10-28')
        new['asOf'] = '2026-10-27'
        with self.assertRaises(ValueError): m.merge(old, new)
        unavailable = fixture()
        unavailable.update(status='unavailable', asOf=None, rows=[], note='Synthetic test collection failure')
        unavailable['coverage'].update(complete=False, count=0)
        with self.assertRaises(ValueError): m.merge(old, unavailable)


if __name__ == '__main__': unittest.main()
