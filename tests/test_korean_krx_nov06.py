"""Exact official Nov6 money; keep the separate public snapshot and old sessions."""
import copy
import csv
import hashlib
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from decimal import Decimal

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from import_krx_nov06_flows import build, digest, parse_individual, assert_preserved, DAY
from korean_rankings_source import preferred
from korean_theme_source import OFFICIAL_DAILY_SNAPSHOT_POLICIES, normalize
from test_korean_theme_snapshot_refresh import partial_provider_result
from update_korean_market import merge_daily_rankings


class November6OfficialTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder = ROOT / 'data/korea-krx-evidence-20261106'
        cls.market = json.loads((ROOT / 'data/korea-market.json').read_text())
        cls.manifest = json.loads((cls.folder / 'source-manifest.json').read_text())
        cls.evidence = json.loads((cls.folder / 'verified-daily-theme-flows.json').read_text())
        cls.public = json.loads((cls.folder / 'previous-public-daily-snapshot.json').read_text())
        cls.individual = json.loads((cls.folder / 'individual-flow-checks.json').read_text())
        cls.raw = {who: list(csv.DictReader(io.StringIO((cls.folder / f'{who}-20261106.csv').read_text(encoding='cp949'))))
                   for who in ('foreign', 'institution')}
        cls.bulk = {who: {r['종목코드']: r for r in rows} for who, rows in cls.raw.items()}
        public_raw = json.loads((ROOT / 'data/korea-money-evidence-20261106.json').read_text())
        cls.universe = {k: v for k, v in next(r for r in public_raw['turnoverRawResponses'] if r['file'] == 'universe.json').items() if k != 'file'}

    def test_exact_csv_bytes_and_buy_minus_sell(self):
        for who, rows in self.raw.items():
            info = self.manifest['investors'][who]
            self.assertEqual(hashlib.sha256((self.folder / info['file']).read_bytes()).hexdigest(), info['sha256'])
            self.assertEqual(len(rows), {'foreign': 2620, 'institution': 2479}[who])
            self.assertEqual(len(rows), len(self.bulk[who]))
            for r in rows:
                for unit in ('거래량_', '거래대금_'):
                    self.assertEqual(int(r[unit + '매수']) - int(r[unit + '매도']), int(r[unit + '순매수']))

    def test_frozen_capture_hashes_and_independent_theme_totals(self):
        path = self.folder / 'completion-manifest.json'
        completion = json.loads(path.read_text())
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), self.evidence['completionManifestSHA256'])
        self.assertEqual(completion['individualRecordCount'], 65)
        self.assertEqual(completion['bulkIndividualCrosschecks'], 47)
        self.assertEqual(completion['crossSourceDiscrepancies'], [])
        captures = []
        for info in completion['files']:
            data = (self.folder / info['file']).read_bytes()
            self.assertEqual(hashlib.sha256(data).hexdigest(), info['sha256'])
            rows = json.loads(data)
            self.assertEqual(len(rows), info['count'])
            captures.extend(rows)
        self.assertEqual(sorted(captures, key=lambda r: r['code']), self.individual)
        self.assertEqual(completion['sourceUrl'], self.evidence['individualSource']['url'])
        self.assertEqual(completion['actualBrowserUrl'], self.evidence['individualSource']['activeMDIUrl'])
        actual = {r['id']: r for r in self.market['themes']['daily'][DAY]['rows']}
        for expected in completion['themes']:
            self.assertEqual(actual[expected['id']]['memberCount'], expected['expectedCount'])
            for who in ('foreign', 'institution'):
                self.assertEqual(actual[expected['id']]['coverage'][who]['netBuyKRW'], expected[who + 'NetBuyKRW'])

    def test_explicit_individual_rows_and_zeros(self):
        by_code = {r['code']: r for r in self.individual}
        self.assertEqual(len(by_code), len(self.individual))
        self.assertEqual(digest(self.individual), self.evidence['individualObservationSHA256'])
        self.assertEqual(len(by_code), 65)
        for who, label in [('foreign', '외국인'), ('institution', '기관합계')]:
            info = self.evidence['stats'][who]
            self.assertEqual(info['rawCovered'], {'foreign': 1047, 'institution': 1000}[who])
            self.assertEqual(info['individuallyVerified'], {'foreign': 18, 'institution': 65}[who])
            self.assertEqual((info['covered'], info['expected'], info['missingCodes']), (1065, 1065, []))
            self.assertEqual(set(info['originalCSVAbsentCodes']), set(by_code) - set(self.bulk[who]) if who == 'foreign' else set(by_code))
            for code in info['originalCSVAbsentCodes']:
                record = by_code[code]
                self.assertEqual((record['start'], record['end'], record['money'], record['queryType']), ('20261106', '20261106', '원', '1'))
                self.assertTrue(record['stock'].startswith(code + '/'))
                rows = {v[0]: v[1:] for line in record['tables'][0].splitlines()[1:] if (v := line.split('\t'))}
                self.assertEqual(len(rows), 13)
                values = [int(n.replace(',', '')) for n in rows[label]]
                self.assertEqual(values[4] - values[3], values[5])
                exact = self.evidence['flows'][who][code]
                self.assertEqual(exact['netBuyKRW'], values[5])
                self.assertEqual(exact['sourceScreen'], '12009')
                self.assertEqual(exact['observedAt'], record['observedAt'])
                if exact['netBuyKRW'] == 0:
                    self.assertEqual(rows[label][5], '0')
        # Every overlapping individual observation must reconcile or retain an explicit discrepancy.
        discrepancies = {(d['investor'], d['code']): d for d in self.evidence['crossCheckDiscrepancies']}
        for record in self.individual:
            parsed = parse_individual(record)
            for who, value in parsed.items():
                raw = self.bulk[who].get(record['code'])
                if raw:
                    pairs = [('netBuyKRW', '거래대금_순매수'), ('buyKRW', '거래대금_매수'), ('sellKRW', '거래대금_매도'), ('netBuyVolume', '거래량_순매수')]
                    mismatch = any(value[a] != int(raw[b]) for a, b in pairs)
                    self.assertEqual((who, record['code']) in discrepancies, mismatch)
                    self.assertEqual(self.evidence['flows'][who][record['code']]['netBuyKRW'], int(raw['거래대금_순매수']))

    def test_full_theme_sums_and_same_membership(self):
        section = self.market['themes']['daily'][DAY]
        self.assertEqual(section['status'], 'verified')
        self.assertIn(section['snapshotPolicy'], OFFICIAL_DAILY_SNAPSHOT_POLICIES)
        self.assertEqual(len(section['rows']), 13)
        original = {r['id']: r for r in self.public['daily']['themes']['rows']}
        members = {m['code'] for b in self.market['themes']['baskets'] for m in b['members']}
        self.assertEqual(len(members), 1065)
        for who in ('foreign', 'institution'):
            self.assertEqual(set(self.evidence['flows'][who]), members)
            for code, exact in self.evidence['flows'][who].items():
                if code in self.bulk[who]:
                    self.assertEqual(exact['netBuyKRW'], int(self.bulk[who][code]['거래대금_순매수']))
                    self.assertEqual(exact['netBuyVolume'], int(self.bulk[who][code]['거래량_순매수']))
                    self.assertEqual(exact['buyKRW'], int(self.bulk[who][code]['거래대금_매수']))
                    self.assertEqual(exact['sellKRW'], int(self.bulk[who][code]['거래대금_매도']))
                    self.assertEqual(exact['sourceScreen'], '12010')
                    self.assertEqual(exact['observedAt'], self.manifest['investors'][who]['observedAt'])
        for row in section['rows']:
            for who in ('foreign', 'institution'):
                cell = row['coverage'][who]
                self.assertEqual(cell['status'], 'complete')
                self.assertEqual(cell['availableCount'], cell['expectedCount'])
                self.assertEqual(cell['expectedCount'], row['memberCount'])
                self.assertEqual(cell['missingMembers'], [])
                self.assertEqual([r['code'] for r in cell['memberFlows']], [r['code'] for r in original[row['id']]['coverage'][who]['memberFlows']])
                for member in cell['memberFlows']:
                    self.assertEqual(member['netBuyKRW'], self.evidence['flows'][who][member['code']]['netBuyKRW'])
                total = sum(m['netBuyKRW'] for m in cell['memberFlows'])
                self.assertEqual(cell['netBuyKRW'], total)
                self.assertEqual(cell['knownSubtotalKRW'], total)
                self.assertEqual(Decimal(str(row[who])) * 100000000, total)
        self.assertEqual(section['membershipAsOf'], '2026-10-19')
        self.assertEqual(section['marketCapAsOf'], '2026-10-19')

    def test_market_rankings_use_full_source_with_exact_eligible_filter(self):
        mapping = {r['itemcode']: r for r in self.universe['payload']}
        self.assertEqual(len(mapping), 2878)
        eligible = {c: r for c, r in mapping.items() if r['type'] == 'ST' and r['sosok'] in ('0', '1') and not preferred(r)}
        self.assertEqual(len(eligible), 2610)
        self.assertEqual(self.evidence['mappingEvidence']['rawResponseSHA256'], digest(self.universe))
        for who in ('foreign', 'institution'):
            section = self.market['rankings']['daily'][DAY][who]
            candidates = sorted([r for r in self.raw[who] if r['종목코드'] in eligible], key=lambda r: (-int(r['거래대금_순매수']), r['종목코드']))
            for market, sosok in [('KOSPI', '0'), ('KOSDAQ', '1'), ('ALL', None)]:
                wanted = [r for r in candidates if sosok is None or eligible[r['종목코드']]['sosok'] == sosok][:15]
                actual = section['rows'] if market == 'ALL' else section['byMarket'][market]
                self.assertEqual([r['code'] for r in actual], [r['종목코드'] for r in wanted])
                for a, b in zip(actual, wanted):
                    self.assertEqual(a['valueKRW'], int(b['거래대금_순매수']))
                    self.assertEqual(Decimal(str(a['value'])) * 100000000, a['valueKRW'])
            refreshed = merge_daily_rankings(self.market['rankings']['daily'][DAY], {who: {'rows': [], 'status': 'unavailable'}}, DAY)
            self.assertEqual(refreshed[who], section)

    def test_dates_scope_and_source_observation_times(self):
        e = self.evidence
        self.assertEqual((e['asOf'], e['start'], e['end']), (DAY, DAY, DAY))
        self.assertIn('not a provider final-status flag', e['finalDataNote'])
        self.assertEqual(e['sourceStatus'], 'official_krx_observed_after_scheduled_final_time')
        self.assertEqual(set(e['sourceScreens']), {'12010', '12009'})
        times = [r['observedAt'] for r in self.individual] + [r['observedAt'] for r in self.manifest['investors'].values()]
        self.assertTrue(all(t.startswith('2026-11-08T') for t in times))
        self.assertEqual(e['collectionWindowUTC'], {'observedAtStart': min(times), 'observedAtEnd': max(times)})
        for who in ('foreign', 'institution'):
            self.assertEqual(self.market['rankings']['daily'][DAY][who]['coverage']['observedAt'], self.manifest['investors'][who]['observedAt'])

    def test_retained_public_snapshot_and_sixteen_prior_days(self):
        self.assertEqual(self.public['snapshotSHA256'], {
            'rankings': 'e5ace883af2645f6a57a158d51bac85b2cdf69484c08aadfea16932d6dd38ad9',
            'themes': '51fb54704ba624b3ad84d2e1b0634f05dc0e375b0494ec5df5430c7d3686e8e8'})
        for family in ('rankings', 'themes'):
            self.assertEqual(digest(self.public['daily'][family]), self.public['snapshotSHA256'][family])
            prior = self.public['preservedDailySnapshots'][family]
            self.assertEqual(len(prior), 16)
            for day, want in prior.items():
                self.assertEqual(digest(self.market[family]['daily'][day]), want, (family, day))
            for key, want in self.public['preservedPeriods'][family].items():
                self.assertEqual(digest(self.market[family][key]), want, (family, key))
        self.assertEqual(self.market['rankings']['daily'][DAY]['tradedValue'], self.public['daily']['rankings']['tradedValue'])
        self.assertEqual(self.public['daily']['themes']['status'], 'partial')
        self.assertEqual(self.public['daily']['themes']['snapshotPolicy'], 'verified_public_naver_partial_amounts')

    def test_later_partial_provider_refresh_preserves_official_daily(self):
        previous = copy.deepcopy(self.market['themes'])
        refreshed = normalize(partial_provider_result(DAY), previous['dates'], previous)
        self.assertEqual(refreshed['daily'][DAY], previous['daily'][DAY])
        self.assertEqual(refreshed['aggregate5d']['status'], 'partial')
        self.assertEqual(refreshed['monthly']['status'], 'partial')

    def test_missing_capture_cannot_become_zero_or_complete(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            for name in ('source-manifest.json', 'foreign-20261106.csv', 'institution-20261106.csv'):
                shutil.copy2(self.folder / name, folder / name)
            removed = self.individual[0]['code']
            (folder / 'individual-flow-checks.json').write_text(json.dumps(self.individual[1:], ensure_ascii=False))
            with self.assertRaises(AssertionError):
                build(copy.deepcopy(self.market), folder, self.universe, require_complete=True)
            result, evidence, _, _ = build(copy.deepcopy(self.market), folder, self.universe)
            self.assertIn(removed, evidence['stats']['institution']['missingCodes'])
            self.assertEqual(result['themes']['daily'][DAY]['status'], 'partial')
            for row in result['themes']['daily'][DAY]['rows']:
                cell = row['coverage']['institution']
                if removed in cell['missingMembers']:
                    self.assertIsNone(row['institution'])
                    self.assertIsNone(cell['netBuyKRW'])
                    self.assertIsNone(next(r['netBuyKRW'] for r in cell['memberFlows'] if r['code'] == removed))
            assert_preserved(self.market, result)

    def test_corrupt_individual_query_is_rejected(self):
        for key, value in [('money', '백만원'), ('start', '20261105'), ('code', '999999'), ('queryType', '2')]:
            record = copy.deepcopy(self.individual[0])
            record[key] = value
            with self.assertRaises(AssertionError):
                parse_individual(record)
        record = copy.deepcopy(self.individual[0])
        record['tables'][0] = record['tables'][0].replace('외국인\t0\t0\t0\t0\t0\t0', '외국인\t0\t0\t0\t0\t0\t1')
        with self.assertRaises(AssertionError):
            parse_individual(record)


if __name__ == '__main__':
    unittest.main()
