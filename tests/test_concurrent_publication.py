"""Offline bare-remote regressions: no network or live publication."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

class ConcurrentPublicationTests(unittest.TestCase):
    def git(self, path, *args):
        return subprocess.check_output(['git', '-C', str(path), *args], stderr=subprocess.DEVNULL, text=True).strip()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.remote = self.root/'remote.git'
        subprocess.run(['git','init','--bare',str(self.remote)],check=True,capture_output=True)
        self.a = self.root/'a'; self.b = self.root/'b'
        subprocess.run(['git','clone',str(self.remote),str(self.a)],check=True,capture_output=True)
        self.config(self.a)
        self.git(self.a,'checkout','-b','main')
        (self.a/'data').mkdir(); (self.a/'scripts').mkdir()
        (self.a/'data/value.json').write_text('old\n')
        (self.a/'README.md').write_text('baseline\n')
        (self.a/'scripts/validate_publication.sh').write_text('#!/bin/bash\necho checked > .git/validated\nexit "${FAIL_VALIDATION:-0}"\n')
        shutil.copy(ROOT/'scripts/publish_collected_data.sh',self.a/'scripts/publish_collected_data.sh')
        self.commit(self.a,'baseline'); self.git(self.a,'push','origin','main')
        subprocess.run(['git','clone','-b','main',str(self.remote),str(self.b)],check=True,capture_output=True); self.config(self.b)
        self.base=self.git(self.a,'rev-parse','HEAD')
        (self.a/'data/value.json').write_text('candidate\n'); self.commit(self.a,'candidate')
        self.candidate=self.git(self.a,'rev-parse','HEAD')

    def config(self,p):
        self.git(p,'config','user.email','test@example.invalid'); self.git(p,'config','user.name','Test')
    def commit(self,p,msg):
        self.git(p,'add','.'); self.git(p,'commit','-m',msg)
    def advance(self,path='README.md'):
        (self.b/path).write_text('remote advance\n'); self.commit(self.b,'advance'); self.git(self.b,'push','origin','main')
        return self.git(self.b,'rev-parse','HEAD')
    def run_guard(self,fail=0):
        return subprocess.run(['bash','scripts/publish_collected_data.sh'],cwd=self.a,env=dict(os.environ,FAIL_VALIDATION=str(fail)),capture_output=True,text=True)
    def remote_head(self):
        return self.git(self.remote,'rev-parse','main')
    def test_no_advance_normal_push(self):
        self.assertEqual(self.run_guard().returncode,0); self.assertEqual(self.remote_head(),self.candidate)
    def test_disjoint_rebased_and_revalidated(self):
        other=self.advance(); r=self.run_guard(); self.assertEqual(r.returncode,0,r.stderr)
        self.assertEqual(self.git(self.a,'rev-parse','HEAD^'),other)
        self.assertTrue((self.a/'.git/validated').exists())
        self.assertEqual((self.a/'README.md').read_text(),'remote advance\n')
        self.assertEqual((self.a/'data/value.json').read_text(),'candidate\n')
    def test_overlap_stops_even_textually_mergeable(self):
        other=self.advance('data/value.json'); r=self.run_guard()
        self.assertNotEqual(r.returncode,0); self.assertIn('overlap',r.stderr)
        self.assertEqual(self.remote_head(),other); self.assertEqual(self.git(self.a,'rev-parse','HEAD'),self.candidate)
    def test_validator_failure_never_pushes(self):
        other=self.advance(); self.assertNotEqual(self.run_guard(37).returncode,0)
        self.assertEqual(self.remote_head(),other)
    def test_validator_mutation_never_pushes(self):
        # A new remote validator unexpectedly modifies a tracked file.
        (self.b/'scripts/validate_publication.sh').write_text('#!/bin/bash\necho mutated > data/value.json\n')
        self.commit(self.b,'changed validator'); self.git(self.b,'push','origin','main')
        other=self.remote_head(); r=self.run_guard()
        self.assertNotEqual(r.returncode,0); self.assertIn('validation modified',r.stderr)
        self.assertEqual(self.remote_head(),other)

    def test_later_remote_race_rejected_without_force(self):
        hook=self.a/'.git/hooks/pre-push'
        hook.write_text('#!/bin/bash\ncd "'+str(self.b)+'"\nprintf race > README.md\ngit add README.md\ngit commit -m race >/dev/null\ngit push origin main >/dev/null\n')
        hook.chmod(0o755); r=self.run_guard(); self.assertNotEqual(r.returncode,0)
        self.assertNotEqual(self.remote_head(),self.candidate)
        self.assertEqual(self.git(self.remote,'show','main:data/value.json'),'old')
    def test_workflow_fetches_full_ancestry(self):
        text=(ROOT/'.github/workflows/update.yml').read_text()
        self.assertIn('fetch-depth: 0',text)
        self.assertIn('bash scripts/publish_collected_data.sh',text)
        self.assertNotIn('git push --force',text)
    def test_unexpected_shallow_history_fails_closed(self):
        shallow=self.root/'shallow'
        subprocess.run(['git','clone','--depth','1','-b','main',self.a.as_uri(),str(shallow)],check=True,capture_output=True)
        self.config(shallow); self.git(shallow,'remote','set-url','origin',str(self.remote))
        self.a=shallow
        self.assertNotEqual(self.run_guard().returncode,0)
        self.assertEqual(self.remote_head(),self.base)

    def test_dirty_tree_rejected(self):
        (self.a/'README.md').write_text('uncommitted')
        self.assertNotEqual(self.run_guard().returncode,0); self.assertEqual(self.remote_head(),self.base)

if __name__=='__main__': unittest.main()
