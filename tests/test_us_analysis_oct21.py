import datetime as dt,json,math,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class October21Verification(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.e=next(e for e in json.loads((ROOT/'data/us_analysis.json').read_text())['entries'] if e['date']=='2026-10-21')
  cls.proof=json.loads((ROOT/'data/us-close-evidence-20261021.json').read_text())
 def test_completed_session_and_indices(self):
  e=self.e;self.assertEqual(e['sessionVerification']['previousSession'],'2026-10-20');self.assertEqual(e['sessionVerification']['closedAt'],'2026-10-21T16:00:00-04:00')
  self.assertEqual(len(e['indices']),4)
  for r in e['indices']:
   self.assertEqual(r['previousDate'],'2026-10-20');self.assertAlmostEqual(r['changePct'],100*(r['close']/r['previousClose']-1))
 def test_no_cap500_panel_or_prior_earnings(self):
  self.assertNotIn('marketCapUnusualMovers',self.e)
  rows=self.e['earnings']['rows'];self.assertNotIn('SPCX',{r['ticker'] for r in rows})
  for r in rows:
   self.assertEqual(r['releaseDate'],'2026-10-21');self.assertEqual(r['presentationVersion'],3)
   self.assertEqual([m['label'] for m in r['metrics']],['매출','매출총이익','매출총이익률','영업이익','EPS'])
   self.assertEqual(len(r['quarterlyHistory']['rows']),4)
 def test_cutoff_and_price_reaction(self):
  cutoff=dt.datetime.fromisoformat(self.e['earnings']['reportCutoffAt'].replace('Z','+00:00'))
  self.assertEqual(cutoff,dt.datetime(2026,10,21,22,tzinfo=dt.timezone.utc))
  for r in self.e['earnings']['rows']:
   stamp=r.get('releaseTiming',{}).get('publishedAt')
   if stamp:self.assertLessEqual(dt.datetime.fromisoformat(stamp.replace('Z','+00:00')),cutoff)
   after=r.get('priceReaction',{}).get('afterHours',{})
   if after.get('status')=='verified':self.assertLessEqual(dt.datetime.fromisoformat(after['observedAt'].replace('Z','+00:00')),cutoff)
 def test_heatmap_reproduces_raw_regular_closes(self):
  h=next(e for e in json.loads((ROOT/'data/us_heatmaps.json').read_text())['entries'] if e['date']=='2026-10-21')
  self.assertEqual(h['status'],'verified');self.assertEqual(h['previousSession'],'2026-10-20');self.assertEqual(h['weighting']['basis'],'equal-security')
  self.assertEqual(len(h['rows']),self.e['coverage']['dailyValid'])
  for r in h['rows']:
   self.assertAlmostEqual(r['changePct'],100*(r['close']/r['previousClose']-1));self.assertEqual(r['asOf'],'2026-10-21')
 def test_unusual_filter_reproducible(self):
  daily=self.proof['screens']['dailyRows'];eligible={r['ticker'] for r in daily if abs(r['changePct'])>=5 and r['volumeCurrent']/r['volumePrevious']>=2}
  self.assertEqual(eligible,{r['ticker'] for r in self.e['unusualMovers']['rows']})
 def test_sector_dates(self):
  for r in self.e['sectors']['rows']:
   self.assertEqual(r['calculation']['asOf'],'2026-10-21');self.assertEqual(r['calculation']['anchors']['day'],'2026-10-20')
if __name__=='__main__':unittest.main()
