"""Offline guards for fail-closed validation of refreshed publication files."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class PublicationPipelineTests(unittest.TestCase):
    def test_validation_brackets_all_updates_before_save(self):
        workflow = (ROOT / '.github/workflows/update.yml').read_text()
        command = 'run: bash scripts/validate_publication.sh'
        self.assertEqual(workflow.count(command), 2)
        before, after = [m for m in range(len(workflow)) if workflow.startswith(command, m)]
        for updater in ('update_data.py', 'update_korean_market.py',
                        'patch_japan_financials.py', 'patch_regional_earnings.py',
                        'apply_financial_backfills.py', 'audit_coverage.py'):
            self.assertLess(before, workflow.index(updater))
            self.assertLess(workflow.index(updater), after)
        self.assertLess(after, workflow.index('git add data/'))
        self.assertNotIn('continue-on-error', workflow)
        self.assertNotIn('always()', workflow)

    def run_guard_with_stub_commands(self, fail_on=''):
        # Exercise real shell control flow without running recursively or fetching data.
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            log = folder / 'calls'
            for name in ('python', 'node'):
                executable = folder / name
                executable.write_text('#!/bin/bash\n'
                                      'echo "$(basename "$0") $*" >> "$CALL_LOG"\n'
                                      'if [[ -n "$FAIL_ON" && "$*" == *"$FAIL_ON"* ]]; then exit 37; fi\n')
                executable.chmod(0o755)
            env = dict(os.environ, PATH=tmp+os.pathsep+os.environ['PATH'],
                       CALL_LOG=str(log), FAIL_ON=fail_on)
            result = subprocess.run(['bash', str(ROOT / 'scripts/validate_publication.sh')],
                                    cwd=tmp, env=env, capture_output=True, text=True)
            return result.returncode, log.read_text().splitlines()

    def test_guard_runs_entire_suite_and_all_validators(self):
        status, calls = self.run_guard_with_stub_commands()
        self.assertEqual(status, 0)
        self.assertEqual(calls[0], 'python -m unittest discover -s tests -v')
        for path in (ROOT / 'tests').glob('test_*.cjs'):
            self.assertIn('node tests/'+path.name, calls)
        self.assertEqual(calls[-3:], ['python scripts/validate_us_analysis.py',
                                     'python scripts/validate_korean_market.py',
                                     'python scripts/manage_briefings.py'])

    def test_each_validation_failure_stops_publication_guard(self):
        for failed in ('unittest', 'test_korea_ui.cjs', 'validate_us_analysis.py',
                       'validate_korean_market.py', 'manage_briefings.py'):
            with self.subTest(failed=failed):
                status, calls = self.run_guard_with_stub_commands(failed)
                self.assertEqual(status, 37)
                self.assertIn(failed, calls[-1])


if __name__ == '__main__':
    unittest.main()
