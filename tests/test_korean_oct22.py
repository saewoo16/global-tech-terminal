import json,unittest
from pathlib import Path
R=Path(__file__).resolve().parents[1]
class KoreanOctober22(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.p=json.loads((R/'data/korea-market.json').read_text());cls.b=json.loads((R/'data/briefings.json').read_text())
 def test_latest_complete_session(self):
  self.assertEqual(self.p['asOf'],'2026-10-22')
  e=max((e for e in self.b['entries']if e['market']=='KR'),key=lambda e:e['date'])
  self.assertEqual(e['date'],'2026-10-22');self.assertEqual(e['reportCutoffAt'],'2026-10-22T18:00:00+09:00')
  self.assertEqual(e['earnings']['rows'],[])
  self.assertEqual({x['name']:x['close']for x in e['indices']},{'KOSPI':5533.77,'KOSDAQ':764.1})
 def test_cash_flow_snapshot_matches_brief(self):
  e=next(e for e in self.b['entries']if e['market']=='KR' and e['date']=='2026-10-22')
  for b in e['flows']['rows']:
   r=self.p['flows']['markets'][b['market']]['rows'][-1]
   self.assertEqual(r['date'],'2026-10-22');self.assertTrue(r['snapshotPolicy'])
   for k in ('foreign','institution','individual','otherForeign','otherCorporation'):self.assertEqual(r[k],b[k])
 def test_period_money_is_not_relabelled_today(self):
  for period in ['aggregate5d','monthly']:
   for inv in ['foreign','institution']:self.assertEqual(self.p['rankings'][period][inv]['coverage']['end'],'2026-10-21')
   self.assertEqual(self.p['themes'][period]['coverage']['end'],'2026-10-21')
 def test_heatmap_session(self):
  h=self.p['heatmaps'];self.assertEqual(h['asOf'],'2026-10-22');self.assertEqual(h['previousSession'],'2026-10-21');self.assertTrue(h['regularSessionOnly'])
 def test_futures_date(self):
  for k in ['foreignFlows','openInterest']:self.assertEqual(self.p['futures'][k]['asOf'],'2026-10-22')
if __name__=='__main__':unittest.main()
