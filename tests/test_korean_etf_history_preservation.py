import copy,json,pathlib,sys,tempfile,unittest
from unittest.mock import patch
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import update_korean_etf_charts as collector

def bar(day,close=100,volume=10):
 return {'date':day,'open':100,'high':110,'low':90,'close':close,'volume':volume}
def fund(rows):
 return {'code':'091160','daily':rows,'dailyCoverage':{},'intraday':{'date':rows[-1]['date'],'points':[{'price':100},{'price':101}]},'sourceUrls':['https://example.com'],'metadataAsOf':rows[-1]['date']}

class HistoricalDailyPreservation(unittest.TestCase):
 def test_rolling_window_and_volume_revisions_preserve_all_original_bars(self):
  old=fund([bar('2025-11-10'),bar('2026-11-11')]);before=copy.deepcopy(old)
  new=fund([bar('2026-11-11',volume=99),bar('2026-11-12',101)])
  result=collector.preserve_daily_history(new,old)
  self.assertEqual(result['daily'][:-1],old['daily']);self.assertEqual(old,before)
  self.assertEqual(result['dailyCoverage']['count'],3)
  self.assertEqual(result['historyPreservation']['pendingRevisionDates'],['2026-11-11'])
  self.assertEqual(result['metadataAsOf'],'2026-11-12')
 def test_same_day_refresh_idempotent_and_does_not_clear_pending_review(self):
  old=collector.preserve_daily_history(fund([bar('2026-11-11',volume=99)]),fund([bar('2026-11-11')]))
  result=collector.preserve_daily_history(fund([bar('2026-11-11')]),old)
  self.assertEqual(result['daily'],old['daily']);self.assertEqual(result['historyPreservation'],old['historyPreservation'])
 def test_every_historical_ohlc_conflict_blocks_new_date(self):
  for key in ('open','high','low','close'):
   with self.subTest(key=key):
    old=fund([bar('2026-11-11')]);new=fund([bar('2026-11-11'),bar('2026-11-12')]);new['daily'][0][key]+=1
    with self.assertRaisesRegex(ValueError,'Historical daily OHLC revision'):collector.preserve_daily_history(new,old)
 def test_no_latest_boundary_overlap_blocks_append(self):
  with self.assertRaisesRegex(ValueError,'boundary overlap'):collector.preserve_daily_history(fund([bar('2026-11-12')]),fund([bar('2026-11-11')]))
 def test_old_gap_is_not_filled_and_new_ipo_not_extended_backward(self):
  old=fund([bar('2026-10-13'),bar('2026-10-15')]);new=fund([bar('2026-10-12'),bar('2026-10-13'),bar('2026-10-14'),bar('2026-10-15'),bar('2026-10-16')])
  self.assertEqual([x['date'] for x in collector.preserve_daily_history(new,old)['daily']],['2026-10-13','2026-10-15','2026-10-16'])
 def test_duplicate_unsorted_wrong_identity_and_invalid_bars_fail_closed(self):
  cases=[fund([bar('2026-11-11'),bar('2026-11-11')]),fund([bar('2026-11-12'),bar('2026-11-11')]),dict(fund([bar('2026-11-11')]),code='wrong'),fund([bar('2026-11-11',120)])]
  for new in cases:
   with self.assertRaises(ValueError):collector.preserve_daily_history(new,fund([bar('2026-11-11')]))
 def test_first_collection_is_unchanged(self):
  new=fund([bar('2026-11-11')]);self.assertIs(collector.preserve_daily_history(new,None),new)
 def test_real_all_39_funds_keep_entire_prefix_and_append_synthetic_session(self):
  snapshot=json.loads((ROOT/'data/korean_etf_charts.json').read_text())
  for old in snapshot['funds']:
   new=copy.deepcopy(old);new['daily']=new['daily'][1:]+[dict(new['daily'][-1],date='2026-11-13')]
   result=collector.preserve_daily_history(new,old)
   self.assertEqual(result['daily'][:-1],old['daily'])
 def test_main_applies_preservation_and_keeps_old_fund_on_price_conflict(self):
  for conflict in (False,True):
   with self.subTest(conflict=conflict),tempfile.TemporaryDirectory() as folder:
    path=pathlib.Path(folder)/'snapshot.json';old=fund([bar('2026-11-10'),bar('2026-11-11')]);path.write_text(json.dumps({'funds':[old]}))
    new=fund([bar('2026-11-11',101 if conflict else 100,99),bar('2026-11-12')])
    with patch.object(sys,'argv',['collector','--output',str(path)]),patch.object(collector,'UNIVERSE',[('091160','test','industry')]),patch.object(collector,'fetch',return_value=json.dumps({'result':{'etfItemList':[{'itemcode':'091160'}]}}).encode()),patch.object(collector,'build_fund',return_value=new),patch.object(collector,'refresh_representatives'):
     collector.main()
    result=json.loads(path.read_text());actual=result['funds'][0]
    self.assertEqual(actual['daily'][:2],old['daily'])
    self.assertEqual(len(actual['daily']),2 if conflict else 3)
    self.assertEqual(bool(result['errors']),conflict)
