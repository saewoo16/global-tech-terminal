import json, unittest, math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class NovemberNineReleaseTests(unittest.TestCase):
 def test_session_and_no_earnings_date_relabel(self):
  p=json.loads((ROOT/'data/us_analysis.json').read_text());e=next(x for x in p['entries'] if x['date']=='2026-11-09')
  self.assertEqual(e['sessionVerification']['closedAt'],'2026-11-09T16:00:00-05:00')
  self.assertEqual(e['reportCutoffAt'],'2026-11-10T07:00:00+09:00')
  self.assertEqual(len(p['entries']),len({x['date'] for x in p['entries']}))
  for r in e['earnings']['rows']: self.assertEqual(r['releaseDate'],e['date'])
 def test_sector_periods_and_precise_returns(self):
  p=json.loads((ROOT/'data/us_analysis.json').read_text());e=next(x for x in p['entries'] if x['date']=='2026-11-09')
  self.assertEqual(len(e['sectors']['rows']),40)
  for r in e['sectors']['rows']:
   c=r['calculation'];self.assertEqual(c['asOf'],e['date']);self.assertEqual(c['anchors'],{'day':'2026-11-06','week':'2026-11-02','month':'2026-10-09'})
   for field,anchor in c['anchors'].items():
    vals=[]
    for component in c['components']:
     bars=component['bars'];vals.append((bars[e['date']]['adjustedClose']/bars[anchor]['adjustedClose']-1)*100)
    self.assertAlmostEqual(r[field],sum(vals)/len(vals),delta=0.0051)
 def test_indices_have_independent_close_evidence(self):
  e=json.loads((ROOT/'data/us-indices-evidence-20261109.json').read_text())
  self.assertEqual(set(e['crosscheck']['closes']),{'^DJI','^GSPC','^IXIC','^RUT'})
  self.assertTrue(e['crosscheck']['rawSha256'])
if __name__=='__main__':unittest.main()
