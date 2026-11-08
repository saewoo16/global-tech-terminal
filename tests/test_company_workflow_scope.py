"""Offline write-boundary regressions; no live collectors or publication."""
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('publication_scope', ROOT/'scripts/check_publication_scope.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class CompanyScopeTests(unittest.TestCase):
    def test_only_company_outputs_are_allowed(self):
        self.assertEqual(len(m.validate_paths(m.SCOPES['company'], 'company')), 4)
        for path in ('data/korea-market.json', 'data/korean_etf_charts.json',
                     'data/us_analysis.json', 'data/us_heatmaps.json',
                     'data/overseas_etf_charts.json', 'data/macro_quotes.json',
                     'data/fedwatch.json', 'README.md', 'assets/app.js'):
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, 'outside company'):
                m.validate_paths(['data/market.json', path], 'company')

    def test_unknown_scope_rejected(self):
        with self.assertRaises(ValueError):
            m.validate_paths([], 'all')

    def test_workflow_preserves_company_fallback_but_not_other_collectors(self):
        workflow = (ROOT/'.github/workflows/update.yml').read_text()
        for required in ("cron: '0 22 * * 1-5'", 'workflow_dispatch:',
                         'python scripts/update_data.py', 'python scripts/patch_japan_financials.py',
                         'python scripts/patch_regional_earnings.py', 'python scripts/apply_financial_backfills.py',
                         'python scripts/audit_coverage.py --baseline /tmp/market-baseline.json',
                         'bash scripts/publish_collected_data.sh', 'fetch-depth: 0'):
            self.assertIn(required, workflow)
        for forbidden in ('python scripts/update_korean_market.py',
                          'python scripts/update_overseas_etf_charts.py',
                          'python scripts/update_macro_quotes.py', 'git add data/\n',
                          'pages: write', 'id-token:', 'secrets.', '--force'):
            self.assertNotIn(forbidden, workflow)
        self.assertEqual(workflow.count('python scripts/check_publication_scope.py --scope company --base HEAD'), 2)
        self.assertIn('git add data/market.json data/coverage.json data/coverage.csv data/regional_earnings_coverage.csv', workflow)
        # Their existing tools and the separate Korean official-source job remain.
        for script in ('update_korean_market.py', 'update_overseas_etf_charts.py', 'update_macro_quotes.py'):
            self.assertTrue((ROOT/'scripts'/script).is_file())
        korean = (ROOT/'.github/workflows/korean-close-data.yml').read_text()
        self.assertIn("cron: '30 8 * * 1-5'", korean)
        self.assertIn("cron: '0 9,10 * * 1-5'", korean)

    def test_tracked_untracked_staged_and_renamed_files_are_checked(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            def git(*args):
                return subprocess.check_output(['git', '-C', folder, *args], stderr=subprocess.DEVNULL)
            git('init'); git('config', 'user.email', 'test@example.invalid'); git('config', 'user.name', 'Test')
            (root/'data').mkdir(); (root/'data/market.json').write_text('{}')
            (root/'data/us_analysis.json').write_text('{}')
            git('add', '.'); git('commit', '-m', 'baseline')
            self.assertEqual(m.changed_paths(root, 'HEAD'), set())
            (root/'data/market.json').write_text('{"new":1}')
            self.assertEqual(m.validate_paths(m.changed_paths(root, 'HEAD'), 'company'), ['data/market.json'])
            git('add', 'data/market.json')
            (root/'data/unknown.json').write_text('{}')
            self.assertIn('data/unknown.json', m.changed_paths(root, 'HEAD'))
            with self.assertRaises(ValueError):
                m.validate_paths(m.changed_paths(root, 'HEAD'), 'company')
            (root/'data/unknown.json').unlink()
            git('mv', 'data/us_analysis.json', 'data/coverage.json')
            self.assertIn('data/us_analysis.json', m.changed_paths(root, 'HEAD'))
            with self.assertRaises(ValueError):
                m.validate_paths(m.changed_paths(root, 'HEAD'), 'company')


if __name__ == '__main__':
    unittest.main()
