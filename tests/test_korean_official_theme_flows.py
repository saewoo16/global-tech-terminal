"""Official daily constituent amounts must stay complete and source-dated."""
import copy
import csv
import hashlib
import io
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from korean_theme_source import build, normalize
from test_korean_oct22 import assert_period_provenance

class OfficialThemeFlowsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload = json.loads((ROOT / 'data/korea-market.json').read_text())
        cls.evidence = json.loads((ROOT / 'data/korea-theme-official-evidence-20261104.json').read_text())

    def test_all_amounts_reconcile_with_original_sources(self):
        verified = self.evidence['verified']
        self.assertEqual((verified['asOf'], verified['start'], verified['end']), ('2026-11-04',) * 3)
        checks = self.evidence['individualChecks']
        self.assertEqual(checks['date'], '2026-11-04')
        individual = {r['stock'][:6]: r for r in checks['records']}
        for investor, label in [('foreign', '외국인'), ('institution', '기관합계')]:
            source = next(f for f in self.evidence['sourceFiles'] if f['name'].startswith(investor + '-'))
            raw = source['content'].encode(source['encoding'])
            self.assertEqual(len(raw), source['bytes'])
            self.assertEqual(hashlib.sha256(raw).hexdigest(), source['sha256'])
            records = list(csv.reader(io.StringIO(source['content'])))
            self.assertEqual(records[0][-1], '거래대금_순매수')
            amounts = {r[0]: int(r[-1].replace(',', '')) for r in records[1:]}
            self.assertEqual(len(amounts), len(records) - 1)
            self.assertEqual(len(verified['flows'][investor]), 1065)
            for code, flow in verified['flows'][investor].items():
                if flow['source'] == 'KRX 12010 CSV':
                    self.assertEqual(flow['netBuyKRW'], amounts[code])
                else:
                    self.assertNotIn(code, amounts)
                    check = individual[code]
                    self.assertEqual((check['start'], check['end']), ('20261104', '20261104'))
                    row = next(r.split('\t') for r in check['rows'] if r.split('\t')[0] == label)
                    self.assertEqual(flow['netBuyKRW'], int(row[-1].replace(',', '')))

    def test_all_thirteen_themes_are_complete_without_redating_other_windows(self):
        themes = self.payload['themes']
        section = themes['daily']['2026-11-04']
        self.assertEqual(section['status'], 'verified')
        self.assertEqual(len(section['rows']), 13)
        self.assertEqual(section['coverage']['start'], section['coverage']['end'])
        catalog = {b['id']: b for b in themes['baskets']}
        for row in section['rows']:
            codes = {m['code'] for m in catalog[row['id']]['members']}
            for investor in ['foreign', 'institution']:
                cell = row['coverage'][investor]
                self.assertEqual({c['code'] for c in cell['memberFlows']}, codes)
                self.assertEqual(cell['availableCount'], len(codes))
                self.assertEqual(cell['missingMembers'], [])
                self.assertEqual(cell['status'], 'complete')
                expected = sum(self.evidence['verified']['flows'][investor][c]['netBuyKRW'] for c in codes)
                self.assertEqual(cell['netBuyKRW'], expected)
                self.assertEqual(row[investor], expected / 1e8)
        # Live period amounts may advance with their actual dated sources;
        # preserving the official daily snapshot must not freeze other windows.
        assert_period_provenance(self, self.payload)
        self.assertEqual(section['membershipAsOf'], '2026-10-19')
        self.assertEqual(section['marketCapAsOf'], '2026-10-19')

    def test_generic_partial_refresh_cannot_replace_frozen_official_day(self):
        responses = {}
        for market, code in [('KOSPI', '005930'), ('KOSDAQ', '247540')]:
            for investor in ['FOREIGNER', 'ORGANIZATION']:
                for period in ['DAY', 'WEEK', 'MONTH']:
                    responses[f'{market}_{investor}_{period}'] = {'url': 'https://stock.naver.com/api/test?periodType=' + period, 'data': {'sections': {
                        'buyRankList': [{'type': 'ST', 'itemcode': code, 'accTradeAmount': '123', 'bizdateFrom': '20261104', 'bizdateTo': '20261104', 'estimated': False}], 'sellRankList': []}}}
        prior = copy.deepcopy(self.payload['themes'])
        incoming = build(responses=responses)
        actual = normalize(incoming, prior['dates'], prior)
        self.assertEqual(actual['daily']['2026-11-04'], prior['daily']['2026-11-04'])
        self.assertEqual(actual['aggregate5d']['coverage']['end'], '2026-11-04')
        self.assertEqual(actual['aggregate5d']['status'], 'partial')
        sources = {source['id']: source for source in self.payload['sources']}
        sources.update({source['id']: source for source in incoming['sources']})
        refreshed = {**self.payload, 'themes': actual, 'sources': list(sources.values())}
        assert_period_provenance(self, refreshed)
        self.assertEqual(self.payload['themes'], prior)

if __name__ == '__main__':
    unittest.main()
