"""Regression: October 27 close preserves real session and statistical dates."""
import json,pathlib,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
class October27Close(unittest.TestCase):
 def test_dated_evidence_and_latest_entry(self):
  d=json.loads((ROOT/'data/korea-close-evidence-20261027.json').read_text())
  self.assertEqual(d['sessionDate'],'2026-10-27')
  self.assertEqual(d['previousSession'],'2026-10-26')
  entries=json.loads((ROOT/'data/briefings.json').read_text())['entries']
  e=next(e for e in entries if e.get('market')=='KR' and e['date']=='2026-10-27')
  self.assertEqual(e['earnings'],{'rows':[]})
  self.assertEqual([(i['name'],i['close']) for i in e['indices']],[('KOSPI',5638.34),('KOSDAQ',743.83)])
  for r in e['movers']['rows']:
   self.assertGreaterEqual(abs(r['changePct']),5)
   self.assertGreaterEqual(r['volumeRatio'],2)
   self.assertEqual(r['asOf'],'2026-10-27')
 def test_liquidity_is_prior_statistical_date_not_close_date(self):
  e=json.loads((ROOT/'data/korea-close-evidence-20261027.json').read_text())['liquidity']
  self.assertEqual(e['officialReleaseReused']['date'],'2026-10-26')
  self.assertEqual(e['officialReleaseReused']['officialMarginLoans'],30067740)
