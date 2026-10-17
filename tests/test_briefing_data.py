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
