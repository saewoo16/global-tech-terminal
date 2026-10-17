import copy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('manage_briefings', ROOT/'scripts/manage_briefings.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class BriefingDataTests(unittest.TestCase):
    def setUp(self):
        self.payload = json.loads((ROOT/'data/briefings.json').read_text())

    def test_published_archive_valid(self):
        module.validate_document(self.payload)
        self.assertEqual({item['market'] for item in self.payload['entries']}, {'US', 'KR'})

    def test_all_published_sector_etfs_have_explicit_holdings_status(self):
        for entry in self.payload['entries']:
            for row in entry.get('sectors', {}).get('rows', []):
                if ',' in row['ticker']:
                    self.assertEqual(row.get('instrumentType'), 'basket')
                    self.assertNotIn('holdings', row)
                else:
                    self.assertEqual(row.get('instrumentType'), 'etf')
                    self.assertIn(row.get('holdings', {}).get('status'), ('verified', 'unverified'))

    def test_kodex_machinery_is_not_mislabeled_shipbuilding(self):
        entry = next(e for e in self.payload['entries'] if e['market'] == 'KR')
        row = next(r for r in entry['sectors']['rows'] if r['ticker'] == '102960.KS')
        self.assertEqual(row['benchmark'], 'KODEX 기계장비')
        self.assertEqual(row['name'], '기계장비(조선 포함)')

    def test_expanded_screens_keep_coverage_limits_and_etfs_separate(self):
        us = next(e for e in self.payload['entries'] if e['market'] == 'US' and e['date'] == '2026-10-16')
        kr = next(e for e in self.payload['entries'] if e['market'] == 'KR' and e['date'] == '2026-10-16')
        self.assertEqual(us['screeningCoverage']['requested'], 500)
        self.assertEqual(kr['screeningCoverage']['requested'], 300)
        self.assertEqual(us['screeningCoverage']['dailyValid'], 500)
        self.assertEqual(kr['screeningCoverage']['dailyValid'], 299)
        self.assertEqual(us['screeningCoverage']['full52WeekHistory'], 490)
        self.assertEqual(kr['screeningCoverage']['full52WeekHistory'], 294)
        etfs = [r for r in us['highs']['rows'] if r['ticker'] in ('XLE', 'IHF')]
        self.assertEqual(len(etfs), 2)
        self.assertTrue(all('ETF' in r['kind'] for r in etfs))
        self.assertEqual(len(us['highs']['rows']) - len(etfs), 22)
        self.assertEqual(len(kr['highs']['rows']), 2)
        self.assertEqual([us['screeningCoverage']['turnoverCoverage'], kr['screeningCoverage']['turnoverCoverage']], [0, 0])

    def test_invalid_source_is_rejected(self):
        for url in ('javascript:alert(1)', 'file:///etc/passwd', 'https://secret:token@example.com', '//example.com'):
            payload = copy.deepcopy(self.payload)
            payload['entries'][0]['sources'][0]['url'] = url
            with self.assertRaises(ValueError): module.validate_document(payload)

    def test_duplicate_dates_invalid_dates_unknown_sources(self):
        payload = copy.deepcopy(self.payload)
        payload['entries'].append(payload['entries'][0])
        with self.assertRaises(ValueError): module.validate_document(payload)
        entry = copy.deepcopy(self.payload['entries'][0])
        entry['date'] = '2026-02-30'
        with self.assertRaises(ValueError): module.validate_entry(entry)
        entry = copy.deepcopy(self.payload['entries'][0])
        entry['summary'][0]['sourceIds'] = ['nonexistent']
        with self.assertRaises(ValueError): module.validate_entry(entry)

    def test_missing_is_allowed_but_fake_numbers_not(self):
        for value in (float('nan'), float('inf'), '1.2', True, -101):
            payload = copy.deepcopy(self.payload)
            payload['entries'][0]['sectors']['rows'][0]['day'] = value
            with self.assertRaises(ValueError): module.validate_document(payload)
        payload = copy.deepcopy(self.payload)
        payload['entries'][0]['sectors']['rows'][0]['day'] = None
        module.validate_document(payload)

    def test_call_highlights_must_be_an_array_of_strings(self):
        for value in ('not a list', None, [123]):
            payload = copy.deepcopy(self.payload)
            payload['entries'][0]['earnings']['rows'][0]['callHighlights'] = value
            with self.assertRaises(ValueError): module.validate_document(payload)

    def holdings_entry(self):
        entry = copy.deepcopy(self.payload['entries'][0])
        row = entry['sectors']['rows'][0]
        row['instrumentType'] = 'etf'
        row['holdings'] = {'status': 'verified', 'asOf': '2026-10-15',
            'sourceIds': [entry['sources'][0]['id']],
            'top5': [{'name': 'Company '+str(i), 'ticker': str(i), 'weightPct': 10-i} for i in range(5)]}
        return entry

    def test_verified_holdings_validate_date_sources_count_order_and_weights(self):
        module.validate_entry(self.holdings_entry())
        mutations = [
            lambda h: h.update(asOf='2026-02-30'),
            lambda h: h.update(sourceIds=[]),
            lambda h: h.update(sourceIds=['unknown']),
            lambda h: h['top5'].pop(),
            lambda h: h['top5'].reverse(),
            lambda h: h['top5'][0].update(weightPct='10'),
            lambda h: h['top5'][0].update(weightPct=True),
            lambda h: h['top5'][0].update(weightPct=101),
            lambda h: h['top5'][0].update(ticker='1'),
            lambda h: h['top5'][0].update(name=''),
        ]
        for mutate in mutations:
            entry = self.holdings_entry()
            mutate(entry['sectors']['rows'][0]['holdings'])
            with self.assertRaises(ValueError): module.validate_entry(entry)

    def test_unverified_holdings_and_baskets_are_explicit(self):
        entry = self.holdings_entry()
        row = entry['sectors']['rows'][0]
        row['holdings'] = {'status': 'unverified', 'note': 'Official dated holdings not verified'}
        module.validate_entry(entry)
        row['holdings']['top5'] = [{'name': 'Guess'}]
        with self.assertRaises(ValueError): module.validate_entry(entry)
        row['holdings'] = {'status': 'unverified', 'note': 'Missing'}
        row['instrumentType'] = 'basket'
        with self.assertRaises(ValueError): module.validate_entry(entry)

    def test_upsert_preserves_history_and_other_market(self):
        original = copy.deepcopy(self.payload)
        replacement = copy.deepcopy(self.payload['entries'][0])
        replacement['title'] = 'Updated verified brief'
        result = module.upsert(self.payload, replacement)
        self.assertEqual(len(result['entries']), len(self.payload['entries']))
        replacement['date'] = '2026-10-19'
        result = module.upsert(result, replacement)
        self.assertEqual(len(result['entries']), len(self.payload['entries'])+1)
        self.assertEqual(result['entries'][0]['date'], '2026-10-19')
        self.assertEqual(self.payload, original)

if __name__ == '__main__': unittest.main()
