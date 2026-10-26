"""October 26 completed session, actual provenance and no old-release leakage."""
import datetime as dt
import json
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

class October26AnalysisTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.data=json.loads((ROOT/'data/us_analysis.json').read_text())
  cls.entry=next(e for e in cls.data['entries'] if e['date']=='2026-10-26')
  cls.evidence=json.loads((ROOT/'data/us-close-evidence-20261026.json').read_text())
 def test_session_dates(self):
  e=self.entry
  self.assertEqual(e['sessionVerification']['previousSession'],'2026-10-23')
  self.assertEqual(e['sessionVerification']['closedAt'],'2026-10-26T16:00:00-04:00')
  self.assertEqual(e['reportCutoffAt'],'2026-10-27T07:00:00+09:00')
  self.assertEqual(len(e['indices']),4)
  self.assertEqual(len(e['sectors']['rows']),40)
  for row in e['sectors']['rows']:
   self.assertEqual(row['calculation']['asOf'],'2026-10-26')
 def test_breadth_actual_previous_closes(self):
  counts=dict.fromkeys(('advancing','declining','unchanged'),0)
  for row in self.evidence['screens']['dailyRows']:
   self.assertEqual(row['asOf'],'2026-10-26')
   self.assertEqual(row['previousSession'],'2026-10-23')
   a,b=row.get('close'),row.get('previousClose')
   if a is None or b is None:continue
   counts['advancing' if a>b else 'declining' if a<b else 'unchanged']+=1
  self.assertEqual(self.entry['breadth']['counts'],counts)
  self.assertEqual(sum(counts.values()),self.entry['breadth']['validCount'])
 def test_actual_et_earnings_and_no_prior_release_cloning(self):
  rows=self.entry['earnings']['rows']
  self.assertEqual(len({r['ticker'] for r in rows}),len(rows))
  for row in rows:
   self.assertEqual(row['releaseDate'],'2026-10-26')
   self.assertEqual(row['presentationVersion'],3)
   self.assertEqual(len(row['quarterlyHistory']['rows']),4)
   self.assertEqual(len({q['period'] for q in row['quarterlyHistory']['rows']}),4)
   self.assertNotIn(row['ticker'],['AXP','SLB'])
   self.assertEqual([m['label'] for m in row['metrics']],['매출','매출총이익','매출총이익률','영업이익','EPS'])
 def test_cutoff_excludes_later_quotes(self):
  cutoff=dt.datetime.fromisoformat(self.entry['reportCutoffAt'])
  for row in self.entry['earnings']['rows']:
   published=row['releaseTiming'].get('publishedAt')
   known=row['releaseTiming'].get('knownPublicBy')
   if published:self.assertLessEqual(dt.datetime.fromisoformat(published.replace('Z','+00:00')),cutoff)
   if known:self.assertLessEqual(dt.datetime.fromisoformat(known.replace('Z','+00:00')),cutoff)
   quote=row.get('priceReaction',{}).get('afterHours',{})
   if quote.get('status')=='verified':
    self.assertLessEqual(dt.datetime.fromisoformat(quote['collectedAt'].replace('Z','+00:00')),cutoff)
    self.assertAlmostEqual(quote['changePct'],(quote['price']/row['priceReaction']['regular']['close']-1)*100)
 def test_previous_session_retained(self):
  prior=next(e for e in self.data['entries'] if e['date']=='2026-10-23')
  self.assertEqual({r['ticker'] for r in prior['earnings']['rows']},{'AXP','SLB'})
  self.assertEqual(prior['breadth']['counts'],{'advancing':135,'declining':367,'unchanged':1})
