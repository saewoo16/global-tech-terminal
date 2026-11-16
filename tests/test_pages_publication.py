import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('build_pages', ROOT / 'scripts/build_pages_artifact.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class PagesPublicationTests(unittest.TestCase):
    def test_preserves_bytes_and_excludes_nonpublic_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / 'repo'
            repo.mkdir()
            excluded = {
                'assets/short-balance.js': b'// archived script',
                'data/korean_short_balance.json': b'{}',
                'data/short-balance-evidence/original.csv': b'restricted CSV',
                'data/short-balance-evidence/subdir/extract.json': b'{}',
            }
            fixture = {
                'index.html': b'<html>original</html>',
                'data/example.json': b'{"price": 1.23456789}',
                'assets/app.js': b'// unchanged',
                'assets/short-balance.css': b'.short-links {}',
                'scripts/private.py': b'# not public',
                **excluded,
            }
            for name, content in fixture.items():
                path = repo / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)
            subprocess.run(['git', 'init', '-q', str(repo)], check=True)
            subprocess.run(['git', '-C', str(repo), 'add', '.'], check=True)
            subprocess.run(['git', '-C', str(repo), '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'fixture'], check=True)
            out = Path(tmp) / 'out'
            with patch.object(builder, 'ROOT', repo):
                builder.build(out)
                with self.assertRaises(ValueError):
                    builder.build(out)
                (repo / 'data/example.json').write_text('{}')
                with self.assertRaises(ValueError):
                    builder.build(Path(tmp) / 'dirty')
            self.assertEqual((out / 'data/example.json').read_bytes(), b'{"price": 1.23456789}')
            self.assertFalse((out / 'scripts').exists())
            manifest = json.loads((out / 'deployment-version.json').read_text())
            self.assertEqual(set(manifest['files']), {'index.html', 'data/example.json', 'assets/app.js', 'assets/short-balance.css'})
            self.assertEqual(len(manifest['commit']), 40)
            for name, content in excluded.items():
                self.assertEqual((repo / name).read_bytes(), content)
                self.assertFalse((out / name).exists())
                self.assertNotIn(name, manifest['files'])

    def test_workflow_preserves_collection_and_minimal_permissions(self):
        text = (ROOT / '.github/workflows/pages.yml').read_text()
        self.assertIn('cancel-in-progress: false', text)
        self.assertIn('workflow_run:', text)
        self.assertIn('github.event.workflow_run.conclusion == \'success\'', text)
        self.assertIn('bash scripts/validate_publication.sh', text)
        self.assertNotIn('contents: write', text)
        self.assertNotIn('actions: write', text)
        self.assertNotIn('schedule:', text)
        self.assertNotIn('update_data.py', text)


if __name__ == '__main__':
    unittest.main()
