import copy
import importlib.util
import json
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('validate_us',ROOT/'scripts/validate_us_analysis.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
class USAnalysisTests(unittest.TestCase):
 def setUp(self):self.data=json.loads((ROOT/'data/us_analysis.json').read_text())
 def test_real_snapshot(self):self.assertEqual(mod.validate(self.data),1)
 def test_weekend_rejected(self):
  self.data['entries'][0]['date']='2026-10-17'
  with self.assertRaises(AssertionError):mod.validate(self.data)
 def test_open_session_rejected(self):
  self.data['entries'][0]['sessionStatus']='open'
  with self.assertRaises(AssertionError):mod.validate(self.data)
 def test_false_new_high_rejected(self):
  row=next(r for r in self.data['entries'][0]['highs']['rows'] if r['classification']=='new_high');row['dayHigh']=row['priorHigh52']
  with self.assertRaises(AssertionError):mod.validate(self.data)
 def test_source_mismatch_rejected(self):
  self.data['entries'][0]['summary'][0]['sourceIds']=['invented']
  with self.assertRaises(AssertionError):mod.validate(self.data)
 def test_cap500_cannot_be_relabelled(self):
  self.data['entries'][0]['highs']['rows'][0]['ticker']='NOT_A_MEMBER'
  with self.assertRaises(AssertionError):mod.validate(self.data)
 def test_real_coverage_and_exact_top_tens(self):
  e=self.data['entries'][0];self.assertEqual(len(e['constituents']),503);self.assertEqual(e['coverage']['dailyValid'],503)
  self.assertEqual(len(e['highs']['rows']),45)
  for side in ['gainers','losers']:self.assertEqual(len(e['movers'][side]),10)
 def test_financial_reporting_bases(self):
  rows={r['ticker']:r for r in self.data['entries'][0]['earnings']['rows']};self.assertEqual(len(rows),5)
  tfc=rows['TFC']['metrics'];self.assertEqual(tfc[6]['value'],'$0.56');self.assertEqual(tfc[7]['value'],'$1.16');self.assertTrue(tfc[5]['value'].startswith('약 '));self.assertEqual(rows['RF']['metrics'][5]['value'],'631 백만 USD')

class EarningsSessionTests(unittest.TestCase):
 """All after-close values below are synthetic fixtures, never published stock quotes."""
 def setUp(self):
  self.row={'releaseDate':'2026-10-16',
   'releaseTiming':{'session':'after_close','publishedAt':'2026-10-16T16:05:00-04:00','sourceIds':['fixture_release']},
   'priceReaction':{'currency':'USD','regular':{'date':'2026-10-16','previousDate':'2026-10-15','closedAt':'2026-10-16T16:00:00-04:00','close':110,'previousClose':100,'changePct':10,'sourceIds':['fixture_close']},
    'afterHours':{'status':'verified','price':104.5,'changePct':-5,'observedAt':'2026-10-16T17:10:00-04:00','sourceIds':['fixture_quote']}}}
 def test_synthetic_after_close(self):mod.validate_earnings_prices(self.row)
 def test_current_snapshot_all_before_open(self):
  data=json.loads((ROOT/'data/us_analysis.json').read_text())
  for row in data['entries'][0]['earnings']['rows']:
   self.assertEqual(row['releaseTiming']['session'],'before_open');self.assertEqual(row['priceReaction']['afterHours']['status'],'not_applicable');mod.validate_earnings_prices(row)
 def test_pre_release_and_same_time_quotes_rejected(self):
  for t in ['16:04','16:05']:
   self.row['priceReaction']['afterHours']['observedAt']=f'2026-10-16T{t}:00-04:00'
   with self.assertRaises(AssertionError):mod.validate_earnings_prices(self.row)
 def test_next_day_premarket_and_previous_day_rejected(self):
  for t in ['2026-10-19T08:00:00-04:00','2026-10-15T17:30:00-04:00','2026-10-16T20:15:00-04:00']:
   self.row['priceReaction']['afterHours']['observedAt']=t
   with self.assertRaises(AssertionError):mod.validate_earnings_prices(self.row)
 def test_wrong_percentage_denominator_rejected(self):
  self.row['priceReaction']['afterHours']['changePct']=4.5
  with self.assertRaises(AssertionError):mod.validate_earnings_prices(self.row)
 def test_before_open_cannot_claim_after_close_reaction(self):
  self.row['releaseTiming'].update(session='before_open',publishedAt='2026-10-16T07:00:00-04:00')
  with self.assertRaises(AssertionError):mod.validate_earnings_prices(self.row)
 def test_unknown_is_null_not_zero(self):
  ah=self.row['priceReaction']['afterHours'];ah.update(status='unverified',price=None,changePct=None,observedAt=None,sourceIds=[]);mod.validate_earnings_prices(self.row)
  ah['changePct']=0
  with self.assertRaises(AssertionError):mod.validate_earnings_prices(self.row)
 def test_real_zero_move_allowed(self):
  self.row['priceReaction']['afterHours'].update(price=110,changePct=0);mod.validate_earnings_prices(self.row)
 def test_missing_timezone_and_sources_rejected(self):
  for obj,key,bad in [(self.row['releaseTiming'],'publishedAt','2026-10-16T16:05:00'),(self.row['releaseTiming'],'sourceIds',[]),(self.row['priceReaction']['afterHours'],'sourceIds',[])]:
   old=obj[key];obj[key]=bad
   with self.assertRaises(AssertionError):mod.validate_earnings_prices(self.row)
   obj[key]=old
 def test_release_close_boundary_and_half_day_supported(self):
  self.row['releaseTiming']['publishedAt']='2026-10-16T16:00:00-04:00';mod.validate_earnings_prices(self.row)
  self.row['priceReaction']['regular']['closedAt']='2026-10-16T13:00:00-04:00';self.row['releaseTiming']['publishedAt']='2026-10-16T13:05:00-04:00';mod.validate_earnings_prices(self.row)
 def test_utc_date_mapped_to_et_and_winter_offset(self):
  self.row['releaseTiming']['publishedAt']='2026-10-16T20:05:00Z';self.row['priceReaction']['afterHours']['observedAt']='2026-10-16T23:59:00Z';mod.validate_earnings_prices(self.row)
  self.row['releaseDate']='2026-12-16';self.row['releaseTiming']['publishedAt']='2026-12-16T21:05:00Z';self.row['priceReaction']['regular'].update(date='2026-12-16',previousDate='2026-12-15',closedAt='2026-12-16T16:00:00-05:00');self.row['priceReaction']['afterHours']['observedAt']='2026-12-17T00:30:00Z';mod.validate_earnings_prices(self.row)
 def test_regular_session_mismatch_and_wrong_return_rejected(self):
  reg=self.row['priceReaction']['regular']
  for key,value in [('date','2026-10-15'),('previousDate','2026-10-16'),('changePct',5),('close',None),('previousClose',0)]:
   old=reg[key];reg[key]=value
   with self.assertRaises(AssertionError):mod.validate_earnings_prices(self.row)
   reg[key]=old
 def test_unknown_session_without_invented_time_allowed(self):
  self.row['releaseTiming']={'session':'unknown','publishedAt':None,'sourceIds':[]};self.row['priceReaction']['afterHours'].update(status='unverified',price=None,changePct=None,observedAt=None,sourceIds=[]);mod.validate_earnings_prices(self.row)

if __name__=='__main__':unittest.main()
