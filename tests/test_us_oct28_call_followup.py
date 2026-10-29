"""Call supplements remain on their original ET release date and actual timestamps."""
import datetime as dt,json,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class October28CallFollowup(unittest.TestCase):
 @classmethod
 def setUpClass(cls): cls.p=json.loads((ROOT/'data/us_analysis.json').read_text())
 def test_actual_after_cutoff_call_sources_and_original_dates(self):
  for e in self.p['entries']:
   sources={s['id']:s for s in e['sources']}
   for r in e['earnings']['rows']:
    ids=[s for s in r.get('callSourceIds',[]) if s.startswith('oct28-followup-')]
    if not ids:continue
    self.assertEqual(r['releaseDate'],e['date'])
    self.assertEqual(r['callPresentationPhase'],'supplement')
    self.assertTrue(r['callEvidence']['qaVerified'])
    self.assertGreater(dt.datetime.fromisoformat(r['callVerifiedAt']),dt.datetime.fromisoformat(e['reportCutoffAt']))
    self.assertEqual(r['callHighlights'],r['displayCallHighlights'])
    self.assertTrue(r['callHighlights'])
    for sid in ids:
     self.assertEqual(sources[sid]['observedAt'],r['callVerifiedAt'])
     self.assertLessEqual(dt.datetime.fromisoformat(sources[sid]['retrievedAt']),dt.datetime.fromisoformat(r['callVerifiedAt']))
 def test_prior_release_calls_do_not_reappear_today(self):
  latest=next(e for e in self.p['entries'] if e['date']=='2026-10-28')
  prior=next(e for e in self.p['entries'] if e['date']=='2026-10-27')
  for ticker in ('TER','WM','BKR','EXE','ESS','UHS','BXP'):
   self.assertNotIn(ticker,[r['ticker'] for r in latest['earnings']['rows']])
   r=next(r for r in prior['earnings']['rows'] if r['ticker']==ticker)
   self.assertTrue(r['callHighlights'])
 def test_official_ir_guidance_does_not_assert_call_verified(self):
  e=next(e for e in self.p['entries'] if e['date']=='2026-10-28')
  r=next(r for r in e['earnings']['rows'] if r['ticker']=='MSFT')
  self.assertTrue(r['guidanceSourceIds'])
  self.assertIn('공식 FY2027 Q2',r['guidance'])
  if not r.get('callHighlights'):self.assertIn('대기',r['callStatus'])
