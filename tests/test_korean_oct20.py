"""Verified October20 refresh invariants; no stale observations relabelled."""
import json
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class October20Tests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.d=json.loads((ROOT/'data/korea-market.json').read_text())
  cls.b=next(x for x in json.loads((ROOT/'data/briefings.json').read_text())['entries'] if x['market']=='KR' and x['date']=='2026-10-20')
 def test_snapshot_balances_and_archive_matches(self):
  for market in ['KOSPI','KOSDAQ']:
   r=next(x for x in self.d['flows']['markets'][market]['rows'] if x['date']=='2026-10-20')
   b=next(x for x in self.b['flows']['rows'] if x['market']==market)
   for k in ['foreign','institution','individual']: self.assertEqual(r[k],b[k])
 def test_actual_price_dates(self):
  for k in ['sectorReturns','highsScreen']:self.assertGreaterEqual(self.d[k]['asOf'],'2026-10-20')
  self.assertGreaterEqual(max(self.d['indexMovers']['dates']),'2026-10-20')
 def test_abnormal_volume_uses_previous_not_average(self):
  self.assertEqual(len(self.b['movers']['rows']),5)
  for r in self.b['movers']['rows']:
   self.assertGreaterEqual(abs(r['changePct']),5)
   self.assertGreaterEqual(r['volumeCurrent']/r['volumePrevious'],2)
   self.assertEqual(r['previousSession'],'2026-10-19')
   self.assertFalse(r['regularSessionVolumeCertified'])
 def test_highs_are_disjoint_and_all_visible(self):
  rows=self.d['highsScreen']['rows']
  self.assertTrue({r['classification'] for r in rows} <= {'new_high','near_high'})
  if self.d['highsScreen']['asOf'] == self.b['date']:
   self.assertEqual({r['ticker'] for r in rows},{r['ticker'] for r in self.b['highs']['rows']})
  self.assertEqual({r['classification'] for r in self.b['highs']['rows']}, {'new_high', 'near_high'})
 def test_earnings_not_monthly_sales_republication(self):
  names=[r['name'] for r in self.b['earnings']['rows']]
  self.assertIn('LS에코에너지',names)
  self.assertNotIn('이마트',names)
if __name__=='__main__': unittest.main()
