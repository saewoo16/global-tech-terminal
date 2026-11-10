import json, unittest
from datetime import datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class NovemberTenReleaseTests(unittest.TestCase):
 def setUp(self):
  self.p=json.loads((ROOT/'data/us_analysis.json').read_text());self.e=next(e for e in self.p['entries'] if e['date']=='2026-11-10')
 def test_completed_session_and_cutoff(self):
  e=self.e
  self.assertEqual(e['sessionVerification']['closedAt'],'2026-11-10T16:00:00-05:00')
  self.assertEqual(e['sessionVerification']['previousSession'],'2026-11-09')
  self.assertEqual(e['reportCutoffAt'],'2026-11-11T07:00:00+09:00')
  self.assertGreaterEqual(datetime.fromisoformat(self.p['updatedAt']),datetime.fromisoformat(e['collectedAt']))
  self.assertEqual(len(self.p['entries']),len({x['date'] for x in self.p['entries']}))
 def test_new_earnings_actual_release_date(self):
  for r in self.e['earnings']['rows']:
   self.assertEqual(r['releaseDate'],self.e['date'])
   self.assertEqual(r.get('presentationVersion'),3)
 def test_comparable_consensus_surprises(self):
  r=self.e['earnings']['rows'][0]
  for m in r['metrics']:
   raw=m['raw']
   if raw.get('consensusComparable') and raw.get('consensusValue',0)>0:
    self.assertAlmostEqual(raw['surprisePct'],(raw['value']/raw['consensusValue']-1)*100)
 def test_sector_anchors(self):
  self.assertEqual(len(self.e['sectors']['rows']),40)
  for r in self.e['sectors']['rows']:
   c=r['calculation'];self.assertEqual(c['asOf'],self.e['date'])
   self.assertEqual(c['anchors'],{'day':'2026-11-09','week':'2026-11-03','month':'2026-10-09'})
   for field,anchor in c['anchors'].items():
    values=[(a['bars'][self.e['date']]['adjustedClose']/a['bars'][anchor]['adjustedClose']-1)*100 for a in c['components']]
    self.assertAlmostEqual(r[field],sum(values)/len(values),delta=0.0051)
 def test_index_crosscheck(self):
  x=json.loads((ROOT/'data/us-indices-evidence-20261110.json').read_text())
  for r in self.e['indices']:self.assertEqual(r['close'],x['crosscheck']['closes'][r['ticker']])
if __name__=='__main__':unittest.main()
