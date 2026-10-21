import copy
import datetime as dt
import importlib.util
import json
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('validate_us',ROOT/'scripts/validate_us_analysis.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
class USAnalysisTests(unittest.TestCase):
 def setUp(self):
  self.data=json.loads((ROOT/'data/us_analysis.json').read_text())
  self.historical=next(e for e in self.data['entries'] if e['date']=='2026-10-16')
 def test_real_snapshot(self):self.assertEqual(mod.validate(self.data),len(self.data['entries']))
 def test_future_updates_do_not_require_retired_cap500_panel(self):
  for entry in self.data['entries']:entry.pop('marketCapUnusualMovers',None)
  self.assertEqual(mod.validate(self.data),len(self.data['entries']))
 def test_weekend_rejected(self):
  self.historical['date']='2026-10-17'
  with self.assertRaises(AssertionError):mod.validate(self.data)
 def test_open_session_rejected(self):
  self.historical['sessionStatus']='open'
  with self.assertRaises(AssertionError):mod.validate(self.data)
 def test_false_new_high_rejected(self):
  row=next(r for r in self.historical['highs']['rows'] if r['classification']=='new_high');row['dayHigh']=row['priorHigh52']
  with self.assertRaises(AssertionError):mod.validate(self.data)
 def test_source_mismatch_rejected(self):
  self.historical['summary'][0]['sourceIds']=['invented']
  with self.assertRaises(AssertionError):mod.validate(self.data)
 def test_cap500_cannot_be_relabelled(self):
  self.historical['highs']['rows'][0]['ticker']='NOT_A_MEMBER'
  with self.assertRaises(AssertionError):mod.validate(self.data)
 def test_real_coverage_and_exact_top_tens(self):
  e=self.historical;self.assertEqual(len(e['constituents']),503);self.assertEqual(e['coverage']['dailyValid'],503)
  self.assertEqual(len(e['highs']['rows']),45)
  for side in ['gainers','losers']:self.assertEqual(len(e['movers'][side]),10)
 def test_financial_reporting_bases(self):
  rows={r['ticker']:r for r in self.historical['earnings']['rows']};self.assertEqual(len(rows),5)
  tfc=rows['TFC']['metrics'];self.assertEqual(tfc[6]['value'],'$0.56');self.assertEqual(tfc[7]['value'],'$1.16');self.assertTrue(tfc[5]['value'].startswith('약 '));self.assertEqual(rows['RF']['metrics'][5]['value'],'631 백만 USD')


 def test_new_daily_entries_preserve_historical_fixture(self):
  later=copy.deepcopy(self.historical)
  date=max(dt.date.fromisoformat(e['date']) for e in self.data['entries'])+dt.timedelta(days=1)
  while date.weekday()>=5:date+=dt.timedelta(days=1)
  later['date']=date.isoformat();self.data['entries'].insert(0,later)
  self.assertEqual(mod.validate(self.data),len(self.data['entries']))
  self.assertEqual(next(e for e in self.data['entries'] if e['date']=='2026-10-16'),self.historical)

class FXAndUnusualMoversTests(unittest.TestCase):
 """Synthetic screen/FX examples are test-only, never production observations."""
 def setUp(self):
  self.fx=[{'name':'Fixture FX','value':1.1234,'changePct':0,'observedAt':'2026-10-19T21:15:00Z','basis':'Provider observation; previous provider daily reference','sourceIds':['fixture_quote']}]
  self.screen={'criteria':'Absolute price move >=5% and volume ratio >=2','note':'Synthetic test-only checked universe',
   'coverage':{'universe':'S&P 500','selected':503,'volumeValid':503,'missingCount':0,'previousSession':'2026-10-16'},
   'rows':[{'name':'Fixture Company','ticker':'TEST','sector':'Fixture sector','changePct':5,'volumeCurrent':2000001,'volumePrevious':1000000,'volumeRatio':2.000001,'reasonVerified':False,'sourceIds':['fixture_quote']}],
   'sourceIds':['fixture_quote']}
 def validate_screen(self):mod.validate_unusual_movers(self.screen,set(),dt.date(2026,10,19))
 def test_fx_observation_accepts_provider_time_without_exchange_close_assumption(self):mod.validate_fx(self.fx)
 def test_fx_missing_time_source_and_basis_rejected(self):
  for key,value in [('observedAt',None),('observedAt','2026-10-19T21:15:00'),('sourceIds',[]),('basis',''),('value',0),('value',True),('changePct','0')]:
   with self.subTest(key=key,value=value):
    rows=copy.deepcopy(self.fx);rows[0][key]=value
    with self.assertRaises((AssertionError,ValueError)):mod.validate_fx(rows)
 def test_unknown_fx_is_not_zero(self):
  self.fx[0].update(value=None,changePct=None,observedAt=None,sourceIds=[]);mod.validate_fx(self.fx)
  self.fx[0]['changePct']=0
  with self.assertRaises(AssertionError):mod.validate_fx(self.fx)
 def test_unusual_exact_values_and_negative_boundary(self):
  self.validate_screen();self.screen['rows'][0]['changePct']=-5;self.validate_screen()
  self.screen['rows'][0].update(volumeCurrent=2000000,volumeRatio=2);self.validate_screen()
 def test_unusual_below_threshold_cannot_round_into_screen(self):
  row=self.screen['rows'][0]
  row['changePct']=4.999999
  with self.assertRaises(AssertionError):self.validate_screen()
  row.update(changePct=-5,volumeCurrent=1999999,volumeRatio=1.999999)
  with self.assertRaises(AssertionError):self.validate_screen()
 def test_invalid_volume_or_ratio_rejected(self):
  for key,value in [('volumeCurrent',None),('volumeCurrent',2000000.5),('volumeCurrent',2**53),('volumePrevious',0),('volumePrevious',True),('volumePrevious','1000000'),('volumeRatio',2),('volumeRatio',float('nan'))]:
   with self.subTest(key=key,value=value):
    old=self.screen['rows'][0][key];self.screen['rows'][0][key]=value
    with self.assertRaises(AssertionError):self.validate_screen()
    self.screen['rows'][0][key]=old
 def test_scope_coverage_and_duplicate_rows_rejected(self):
  for key,value in [('universe','US market'),('volumeValid',504),('missingCount',1),('selected',True),('previousSession','2026-10-19')]:
   with self.subTest(key=key,value=value):
    old=self.screen['coverage'][key];self.screen['coverage'][key]=value
    with self.assertRaises(AssertionError):self.validate_screen()
    self.screen['coverage'][key]=old
  self.screen['rows'].append(copy.deepcopy(self.screen['rows'][0]))
  with self.assertRaises(AssertionError):self.validate_screen()
 def test_empty_complete_and_incomplete_scopes_are_explicit(self):
  self.screen['rows']=[];self.validate_screen()
  self.screen['coverage'].update(volumeValid=0,missingCount=503);self.validate_screen()
 def test_optional_blocks_use_normal_source_and_membership_validation(self):
  data=json.loads((ROOT/'data/us_analysis.json').read_text());e=next(e for e in data['entries'] if e['date']=='2026-10-16')
  e['fx']=copy.deepcopy(self.fx)
  with self.assertRaises(AssertionError):mod.validate(data)
  e['fx'][0]['sourceIds']=[e['sources'][0]['id']]
  self.assertEqual(mod.validate(data),len(data['entries']))
  e['unusualMovers']=copy.deepcopy(self.screen);screen=e['unusualMovers']
  screen['coverage']['previousSession']='2026-10-15';screen['sourceIds']=[e['sources'][0]['id']];screen['rows'][0]['sourceIds']=screen['sourceIds']
  with self.assertRaises(AssertionError):mod.validate(data)
  screen['rows'][0]['ticker']=e['constituents'][0]['ticker']
  self.assertEqual(mod.validate(data),len(data['entries']))

class EarningsSessionTests(unittest.TestCase):
 """All after-close values below are synthetic fixtures, never published stock quotes."""
 def setUp(self):
  self.row={'releaseDate':'2026-10-16',
   'releaseTiming':{'session':'after_close','publishedAt':'2026-10-16T16:05:00-04:00','sourceIds':['fixture_release']},
   'priceReaction':{'currency':'USD','regular':{'date':'2026-10-16','previousDate':'2026-10-15','closedAt':'2026-10-16T16:00:00-04:00','close':110,'previousClose':100,'changePct':10,'sourceIds':['fixture_close']},
    'afterHours':{'status':'verified','price':104.5,'changePct':-5,'observedAt':'2026-10-16T17:10:00-04:00','sourceIds':['fixture_quote']}}}
 def test_synthetic_after_close(self):mod.validate_earnings_prices(self.row)
 def test_oct16_snapshot_all_before_open(self):
  data=json.loads((ROOT/'data/us_analysis.json').read_text())
  for row in next(e for e in data['entries'] if e['date']=='2026-10-16')['earnings']['rows']:
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
