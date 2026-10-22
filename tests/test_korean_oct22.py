import copy,json,re,unittest
from datetime import date
from pathlib import Path
R=Path(__file__).resolve().parents[1]

def assert_period_provenance(test, payload):
 """Rolling panels may advance, but their actual dated sources must advance too."""
 sources={s['id']:s for s in payload['sources']}
 for period, source_period in [('aggregate5d','week'),('monthly','month')]:
  sections=[payload['rankings'][period][inv] for inv in ('foreign','institution')]
  sections.append(payload['themes'][period])
  for section in sections:
   window=section['coverage']
   start,end=window['start'],window['end']
   test.assertEqual(date.fromisoformat(start).isoformat(),start)
   test.assertEqual(date.fromisoformat(end).isoformat(),end)
   test.assertLessEqual(start,end)
   test.assertLessEqual(end,payload['asOf'])
   refs=section['sourceIds']
   test.assertTrue(refs)
   for sid in refs:
    test.assertIn(sid,sources)
    match=re.fullmatch(r'naver-(kospi|kosdaq)-(foreign|institution)-'+source_period+r'-(\d{8})',sid)
    test.assertIsNotNone(match, sid)
    test.assertEqual(match.group(3),end.replace('-',''))
    test.assertIn('periodType='+source_period.upper(),sources[sid]['url'])
   for row in section.get('rows',[]):
    if 'sourceId' in row:
     test.assertIn(row['sourceId'],refs)
    for inv in ('foreign','institution'):
     for component in row.get('coverage',{}).get(inv,{}).get('memberFlows',[]):
      if component.get('netBuyKRW') is not None:
       test.assertIn(component['sourceId'],refs)
   for rows in section.get('byMarket',{}).values():
    for row in rows:
     test.assertIn(row['sourceId'],refs)
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
  # The 18:00 report retained 10/21; a later real provider publication can
  # legitimately advance these independently refreshed rolling panels.
  assert_period_provenance(self,self.p)
 def test_period_relabel_without_new_sources_rejected(self):
  for kind in ('rankings','themes'):
   p=copy.deepcopy(self.p)
   section=p[kind]['aggregate5d']
   if kind=='rankings':section=section['foreign']
   section['coverage']['end']='2099-01-01'
   p['asOf']='2099-01-01'  # Must fail source date comparison, not future guard.
   with self.assertRaises(AssertionError):assert_period_provenance(self,p)
 def test_period_source_mismatch_rejected(self):
  p=copy.deepcopy(self.p)
  p['rankings']['monthly']['foreign']['sourceIds']=p['rankings']['aggregate5d']['foreign']['sourceIds']
  with self.assertRaises(AssertionError):assert_period_provenance(self,p)
 def test_heatmap_session(self):
  h=self.p['heatmaps'];self.assertEqual(h['asOf'],'2026-10-22');self.assertEqual(h['previousSession'],'2026-10-21');self.assertTrue(h['regularSessionOnly'])
 def test_futures_date(self):
  for k in ['foreignFlows','openInterest']:self.assertEqual(self.p['futures'][k]['asOf'],'2026-10-22')
if __name__=='__main__':unittest.main()
