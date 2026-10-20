"""Published 2026-10-19 regression checks; future entries do not replace this fixture."""
import datetime as dt
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class October19AnalysisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        data = json.loads((ROOT / 'data/us_analysis.json').read_text())
        cls.entry = next(e for e in data['entries'] if e['date'] == '2026-10-19')
        cls.evidence = json.loads((ROOT / 'data/us-close-evidence-20261019.json').read_text())

    def test_indices_keep_actual_regular_close_and_previous_session(self):
        expected = {'^DJI': 51966.03, '^GSPC': 7690.73, '^IXIC': 26430.89, '^RUT': 2728.30}
        self.assertEqual({r['ticker'] for r in self.entry['indices']}, set(expected))
        for row in self.entry['indices']:
            self.assertAlmostEqual(row['close'], expected[row['ticker']], places=2)
            self.assertEqual(row['previousDate'], '2026-10-16')
            self.assertEqual(row['closedAt'], '2026-10-19T16:00:00-04:00')
            self.assertAlmostEqual(row['changePct'], 100 * (row['close'] / row['previousClose'] - 1))

    def test_fx_retains_provider_observations_separate_from_stock_close(self):
        expected = {'DX-Y.NYB', 'JPY=X', 'KRW=X', 'EURUSD=X'}
        self.assertEqual({r['ticker'] for r in self.entry['fx']}, expected)
        for row in self.entry['fx']:
            self.assertGreater(dt.datetime.fromisoformat(row['observedAt'].replace('Z', '+00:00')),
                               dt.datetime.fromisoformat('2026-10-19T20:00:00+00:00'))
            self.assertIn('공급사', row['basis'])
            self.assertIn('일간', row['basis'])
            self.assertTrue(row['sourceIds'])
            self.assertNotIn('closedAt', row)

    def test_all_503_daily_comparisons_support_rankings_and_verified_zero_screen(self):
        rows = self.evidence['screens']['dailyRows']
        members = {r['ticker'] for r in self.entry['constituents']}
        self.assertEqual(len(rows), 503)
        self.assertEqual({r['ticker'] for r in rows}, members)
        for row in rows:
            self.assertEqual(row['asOf'], '2026-10-19')
            self.assertEqual(row['previousSession'], '2026-10-16')
            self.assertGreater(row['close'], 0)
            self.assertGreater(row['previousClose'], 0)
            self.assertIsInstance(row['volumeCurrent'], int)
            self.assertGreater(row['volumePrevious'], 0)
            self.assertAlmostEqual(row['changePct'], 100 * (row['close'] / row['previousClose'] - 1))
            self.assertAlmostEqual(row['volumeRatio'], row['volumeCurrent'] / row['volumePrevious'])
        for side, descending in [('gainers', True), ('losers', False)]:
            ordered = sorted(rows, key=lambda r: (-r['changePct'] if descending else r['changePct'], r['ticker']))[:10]
            self.assertEqual([r['ticker'] for r in self.entry['movers'][side]], [r['ticker'] for r in ordered])
        candidates = [r for r in rows if abs(r['changePct']) >= 5]
        self.assertEqual({r['ticker'] for r in candidates}, {'DDOG', 'SNDK', 'TWLO', 'WDC'})
        self.assertTrue(all(r['volumeRatio'] < 1 for r in candidates))
        qualifying = [r for r in candidates if r['volumeRatio'] >= 2]
        self.assertEqual(qualifying, [])
        screen = self.entry['unusualMovers']
        self.assertEqual(screen['rows'], [])
        self.assertEqual(screen['coverage']['selected'], 503)
        self.assertEqual(screen['coverage']['volumeValid'], 503)
        self.assertEqual(screen['coverage']['missingCount'], 0)

    def test_short_history_exclusions_do_not_remove_daily_prices(self):
        rows = self.evidence['screens']['dailyRows']
        short = {r['ticker'] for r in rows if not r['fullWindow']}
        self.assertEqual(short, {'FDXF', 'HONA', 'Q', 'VYLR'})
        highs = self.entry['highs']['rows']
        self.assertEqual(len(highs), 34)
        self.assertFalse(short & {r['ticker'] for r in highs})
        self.assertEqual(sum(r['classification'] == 'new_high' for r in highs), 10)
        self.assertEqual(sum(r['classification'] == 'near_high' for r in highs), 24)
        selected = {r['ticker'] for r in rows if r['fullWindow'] and (r['dayHigh'] > r['priorHigh52'] or r['distancePct'] >= -3)}
        self.assertEqual(selected, {r['ticker'] for r in highs})
        for row in highs:
            self.assertAlmostEqual(row['distancePct'], 100 * (row['close'] / row['high52'] - 1))
            self.assertGreaterEqual(row['high52'], row['dayHigh'])
        self.assertEqual(self.entry['coverage']['historicalGapRepairs'][0]['ticker'], 'FISV')
        self.assertEqual(self.entry['coverage']['historicalGapRepairs'][0]['usedFields'], ['high'])

    def test_sector_returns_use_same_adjusted_basis_and_actual_anchors(self):
        rows = self.entry['sectors']['rows']
        self.assertGreaterEqual(len(rows), 40)
        for row in rows:
            calc = row['calculation']
            self.assertEqual(calc['asOf'], '2026-10-19')
            self.assertEqual(calc['anchors'], {'day': '2026-10-16', 'week': '2026-10-12', 'month': '2026-09-18'})
            for key, start in calc['anchors'].items():
                values = []
                for component in calc['components']:
                    bars = component['bars']
                    expected = 100 * (bars[calc['asOf']]['adjustedClose'] / bars[start]['adjustedClose'] - 1)
                    self.assertAlmostEqual(component['returnsUnrounded'][key], expected)
                    values.append(expected)
                self.assertAlmostEqual(row[key], sum(values) / len(values), delta=0.005)
            if row.get('holdings', {}).get('status') == 'verified':
                self.assertLessEqual(row['holdings']['asOf'], '2026-10-19')

    def test_later_call_supplement_preserves_release_search_cutoff(self):
        earnings = self.entry['earnings']
        self.assertEqual(earnings['coverage']['cutoffAt'], '2026-10-19T21:31:00Z')
        self.assertEqual(earnings['coverage']['transcriptReviewedTickers'], ['FITB', 'WRB'])
        self.assertEqual(earnings['coverage']['releaseOnlyTickers'], ['STLD'])
        rows = {r['ticker']: r for r in earnings['rows']}
        self.assertEqual(rows['WRB']['callDetails']['transcriptStatus'], 'public_third_party_verified')
        for ticker, time, price in [('STLD', '19:05', 232.75), ('WRB', '18:47', 72.60)]:
            ah = rows[ticker]['priceReaction']['afterHours']
            self.assertEqual(ah['observedAt'], f'2026-10-19T{time}:00-04:00')
            self.assertEqual(ah['price'], price)
            self.assertGreater(dt.datetime.fromisoformat(ah['retrievedAt'].replace('Z', '+00:00')), dt.datetime.fromisoformat(ah['observedAt']))

    def test_earnings_calculations_preserve_reporting_bases_and_nulls(self):
        issuers = {r['ticker']: r for r in self.entry['earnings']['rows']}
        self.assertTrue({'FITB', 'STLD', 'WRB'} <= issuers.keys())
        for row in issuers.values():
            for metric in row['metrics']:
                raw = metric.get('raw', {})
                for key, baseline in [('yoyPct', 'yearAgoQuarter'), ('qoqPct', 'previousQuarter'), ('surprisePct', 'consensusValue')]:
                    if raw.get(key) is not None:
                        self.assertAlmostEqual(raw[key], 100 * (raw['value'] / raw[baseline] - 1), delta=0.005)
                for key, baseline in [('yoyPp', 'yearAgoQuarter'), ('qoqPp', 'previousQuarter')]:
                    if raw.get(key) is not None:
                        self.assertAlmostEqual(raw[key], raw['value'] - raw[baseline], delta=0.0001)
                if raw.get('consensusComparable') is False:
                    self.assertIsNone(raw.get('surprisePct'))
                if raw.get('status') == 'not_applicable':
                    self.assertIsNone(raw['value'])
                    self.assertTrue(metric['value'].startswith('N/A'))
        stld = {m['label']: m for m in issuers['STLD']['metrics']}
        self.assertEqual(stld['희석 EPS']['basis'], 'US GAAP')
        self.assertEqual(stld['희석 EPS']['raw']['value'], 5.26)
        self.assertIsNone(stld['희석 EPS']['raw']['surprisePct'])
        self.assertIsNone(stld['조정 EPS']['raw']['value'])
        for issuer in ('FITB', 'WRB'):
            metrics = {m['label']: m for m in issuers[issuer]['metrics']}
            for label in ('매출총이익', '매출총이익률', '영업이익', '영업이익률'):
                self.assertEqual(metrics[label]['raw']['status'], 'not_applicable')


if __name__ == '__main__':
    unittest.main()
