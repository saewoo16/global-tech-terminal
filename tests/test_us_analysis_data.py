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
if __name__=='__main__':unittest.main()
