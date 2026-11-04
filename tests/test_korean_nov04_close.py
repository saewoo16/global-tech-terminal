"""November 4 completed-session evidence and immutable archived entry checks."""
import json,math,pathlib,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
class November04Close(unittest.TestCase):
 def test_official_completed_session(self):
  e=json.loads((ROOT/'data/korea-session-evidence-20261104.json').read_text())
  self.assertEqual(e['date'],'2026-11-04')
  self.assertNotIn(e['date'],e['calendar']['holidays'])
  self.assertEqual(e['latestObservedMarketDates'],{'KOSPI':e['date'],'KOSDAQ':e['date']})
 def test_dated_earnings_and_index_closes(self):
  entries=json.loads((ROOT/'data/briefings.json').read_text())['entries']
  e=next(x for x in entries if x['market']=='KR' and x['date']=='2026-11-04')
  self.assertEqual([(x['name'],x['close']) for x in e['indices']],[('KOSPI',5683.8),('KOSDAQ',714.95)])
  ids={x['id'] for x in e['sources']}
  for row in e['earnings']['rows']:
   self.assertEqual(row['releaseDate'],e['date'])
   self.assertEqual(len(row['quarterlyHistory']['rows']),4)
   for q in row['quarterlyHistory']['rows']:
    self.assertTrue(set(q['sourceIds']) <= ids)
    if q.get('revenue') not in (0,None) and q.get('operatingIncome') is not None:
     self.assertTrue(math.isclose(q['operatingMargin'],q['operatingIncome']/q['revenue']*100,abs_tol=1e-9))
