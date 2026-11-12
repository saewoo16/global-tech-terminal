import json, unittest, datetime as dt
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class CompanyNovember12PM(unittest.TestCase):
 def test_completed_asian_sessions_and_independent_closes(self):
  e=json.loads((ROOT/'data/company-refresh-evidence-20261112-pm.json').read_text());m=json.loads((ROOT/'data/market.json').read_text())['stocks']
  rows=e['verified']['ready'];self.assertEqual(len(rows),113);self.assertEqual(len({r['symbol']for r in rows}),113)
  for r in rows:
   self.assertEqual(r['point'][0],'2026-11-12');self.assertEqual(dict(m[r['symbol']]['prices'])['2026-11-12'],r['point'][1])
   self.assertLess(r['regularSession']['end'],dt.datetime.fromisoformat(e['assembledAt']).timestamp())
   t=r['independent'];self.assertAlmostEqual(t[4],r['rawTarget']['close'],delta=max(.0001,abs(t[4])*1e-5));self.assertAlmostEqual(t[4]-t[6],r['rawPreviousClose'],delta=max(.01,abs(r['rawPreviousClose'])*1e-5))
   if r.get('completeIndependentBarUsed'):self.assertLessEqual(t[3],min(t[1],t[4]));self.assertGreaterEqual(t[2],max(t[1],t[4]))
 def test_new_quarters_preserve_accounting_basis(self):
  d=json.loads((ROOT/'data/financial_backfill_zlatest_20261112_asia_official.json').read_text())['companies']
  a=d['TSE:6383']['quarters'][0];b=d['NASDAQ:IMOS']['quarters'][0]
  self.assertEqual((a['revenue'],a['operatingIncome']),(553776-355513,83487-56680));self.assertIn('Japan GAAP',a['basis']);self.assertEqual((b['revenue'],b['operatingIncome']),(8400.763,1657.346));self.assertIn('Other operating income',b['calculation']['note'])
