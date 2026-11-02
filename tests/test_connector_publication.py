import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('prepare_connector_publication', Path(__file__).parents[1] / 'scripts/prepare_connector_publication.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class ConnectorPlanTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / 'a.json').write_text('{"검증": true}', encoding='utf-8')
        (self.root / 'b.txt').write_text('b', encoding='utf-8')

    def plan(self, paths, **kw):
        return m.prepare(self.root, paths, 'a' * 40, 'b' * 40, **kw)

    def test_batches_text_without_mutation(self):
        plan = self.plan(['a.json', 'b.txt'])
        self.assertEqual(len(plan['inlineEntries']), 2)
        self.assertEqual(plan['separateBlobFiles'], [])
        self.assertEqual(plan['inlineEntries'][0]['content'], '{"검증": true}')
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), ['a.json', 'b.txt'])

    def test_large_file_retains_explicit_blob_plan(self):
        (self.root / 'large.json').write_text('x' * 5000)
        plan = self.plan(['large.json', 'a.json'], inline_budget=1024)
        self.assertEqual([e['path'] for e in plan['inlineEntries']], ['a.json'])
        self.assertEqual(plan['separateBlobFiles'][0]['path'], 'large.json')
        self.assertNotIn('content', plan['separateBlobFiles'][0])

    def test_rejects_unsafe_duplicate_missing_and_binary(self):
        (self.root / 'binary').write_bytes(b'\0')
        for paths in [['../outside'], ['/etc/passwd'], ['a.json', 'a.json'], ['missing'], []]:
            with self.assertRaises(ValueError):
                self.plan(paths)

    def test_preserves_non_utf8_as_separate_blob(self):
        (self.root / 'source.csv').write_bytes('검증'.encode('cp949'))
        plan = self.plan(['source.csv'])
        self.assertEqual(plan['inlineEntries'], [])
        self.assertEqual(len(plan['separateBlobFiles']), 1)
        self.assertNotIn('content', plan['separateBlobFiles'][0])

    def test_rejects_symlink_and_invalid_sha(self):
        (self.root / 'link').symlink_to(self.root / 'a.json')
        with self.assertRaises(ValueError):
            self.plan(['link'])
        with self.assertRaises(ValueError):
            m.prepare(self.root, ['a.json'], 'main', 'b' * 40)

    def test_escaped_json_bytes_budget(self):
        (self.root / 'escaped').write_text('"' * 700)
        plan = self.plan(['escaped'], inline_budget=1024)
        self.assertEqual(len(plan['separateBlobFiles']), 1)


if __name__ == '__main__':
    unittest.main()
