"""October 23 actual ET session, cut-off and price provenance regressions."""
import copy
import datetime as dt
import json
import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from validate_us_analysis import validate, validate_earnings_prices

class October23AnalysisTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.data=json.loads((ROOT/'data/us_analysis.json').read_text())
  cls.entry=next(e for e in cls.data['entries'] if e['date']=='2026-10-23')
  cls.evidence=json.loads((ROOT/'data/us-close-evidence-20261023.json').read_text())
 def test_dates_scope_and_panel_sources(self):
  validate(self.data)
  e=self.entry
  self.assertEqual(e['sessionVerification']['previousSession'],'2026-10-22')
  self.assertEqual(e['sessionVerification']['closedAt'],'2026-10-23T16:00:00-04:00')
  self.assertEqual(e['reportCutoffAt'],'2026-10-23T22:00:00Z')
  self.assertEqual(len(e['sectors']['rows']),40)
  self.assertEqual(len(e['constituents']),503)
  for r in self.evidence['screens']['dailyRows']:
   self.assertEqual(r['asOf'],'2026-10-23')
   self.assertEqual(r['previousSession'],'2026-10-22')
  for r in e['sectors']['rows']:
   self.assertEqual(r['calculation']['asOf'],'2026-10-23')
 def test_no_previous_day_announcements_and_exact_four_quarters(self):
  rows=self.entry['earnings']['rows']
  self.assertEqual({r['ticker'] for r in rows},{'AXP','SLB'})
  for r in rows:
   self.assertEqual(r['releaseDate'],'2026-10-23')
   self.assertEqual(r['presentationVersion'],3)
   self.assertEqual(len(r['quarterlyHistory']['rows']),4)
   self.assertEqual(len({q['period'] for q in r['quarterlyHistory']['rows']}),4)
 def test_neutral_quotes_and_actual_collection_cutoff(self):
  bars={r['ticker']:r for r in self.evidence['screens']['dailyRows']}
  cutoff=dt.datetime.fromisoformat(self.entry['reportCutoffAt'].replace('Z','+00:00'))
  for r in self.entry['earnings']['rows']:
   p=r['priceReaction']; b=bars[r['ticker']]
   self.assertEqual(p['regular']['close'],b['close'])
   self.assertEqual(p['regular']['previousClose'],b['previousClose'])
   for field in ['afterHours','subsequentAfterHours']:
    a=p.get(field,{})
    if a.get('status')!='verified':continue
    self.assertAlmostEqual(a['changePct'],(a['price']/b['close']-1)*100)
    observed=dt.datetime.fromisoformat(a['observedAt']);collected=dt.datetime.fromisoformat(a['collectedAt'])
    self.assertEqual(observed.date().isoformat(),'2026-10-23')
    self.assertLessEqual(observed,collected)
    if field=='afterHours':self.assertLessEqual(collected,cutoff)
   z=copy.deepcopy(r)
   if z['priceReaction']['afterHours']['status']=='verified':
    z['priceReaction']['afterHours']['collectedAt']='2026-10-23T22:01:00Z'
    with self.assertRaises(AssertionError):validate_earnings_prices(z)
 def test_breadth_uses_two_regular_closes_not_rounded_returns(self):
  counts=dict.fromkeys(('advancing','declining','unchanged'),0)
  for r in self.evidence['screens']['dailyRows']:
   k='advancing' if r['close']>r['previousClose'] else 'declining' if r['close']<r['previousClose'] else 'unchanged'
   counts[k]+=1
  self.assertEqual(self.entry['breadth']['counts'],counts)
  self.assertEqual(sum(counts.values()),self.entry['breadth']['validCount'])
 def test_previous_session_history_preserved(self):
  prior=next(e for e in self.data['entries'] if e['date']=='2026-10-22')
  self.assertEqual(len(prior['earnings']['rows']),28)
  self.assertEqual(prior['breadth']['counts'],{'advancing':336,'declining':166,'unchanged':1})

 def test_repair_publication_time_and_call_sessions(self):
  self.assertGreater(self.data['updatedAt'],'2026-10-25T00:00:00')
  self.assertEqual(self.entry['publication']['status'],'delayed_publication')
  self.assertLess(self.entry['publication']['preparedAt'],self.data['updatedAt'])
  slb=next(r for r in self.entry['earnings']['rows'] if r['ticker']=='SLB')
  self.assertTrue(slb['callEvidence']['qaVerified'])
  prior=next(e for e in self.data['entries'] if e['date']=='2026-10-22')
  fix=next(r for r in prior['earnings']['rows'] if r['ticker']=='FIX')
  self.assertEqual(fix['releaseDate'],'2026-10-22')
  self.assertTrue(fix['callEvidence']['qaVerified'])
