import unittest,json,datetime as dt
from pathlib import Path
R=Path(__file__).resolve().parents[1]
class CompanyNov13Morning(unittest.TestCase):
 def test_latest_completed_western_quotes(self):
  e=json.loads((R/'data/company-refresh-evidence-20261113-am.json').read_text());m=json.loads((R/'data/market.json').read_text())['stocks'];self.assertEqual(len(e['ready']),134);self.assertEqual(len({r['symbol']for r in e['ready']}),134);self.assertFalse(e['issues'])
  for r in e['ready']:
   self.assertEqual(r['point'][0],'2026-11-12');self.assertEqual(dict(m[r['symbol']]['prices'])['2026-11-12'],r['point'][1]);self.assertLess(r['regularSession']['end'],dt.datetime.fromisoformat(e['assembledAt']).timestamp());t=r['independent'];self.assertAlmostEqual(t[4],r['rawTarget']['close'],delta=max(.0001,abs(t[4])*1e-5))
 def test_prior_discrepancy_reconciled_without_rewriting(self):
  e=json.loads((R/'data/company-refresh-evidence-20261113-am.json').read_text());m=json.loads((R/'data/market.json').read_text())['stocks']
  rows={r['symbol']:r for r in e['ready']}
  for s,value in [('NASDAQ:COHU',45.975),('NASDAQ:MSFT',521.125)]:
   r=rows[s];self.assertEqual(dict(m[s]['prices'])['2026-11-11'],value);self.assertAlmostEqual(r['independent'][4]-r['independent'][6],value);self.assertEqual(r['reconciliation']['storedPriorClose'],value)
