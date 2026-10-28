"""Retain dated raw rankings without weakening date/coverage validation."""
import copy,json,pathlib,sys,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from validate_korean_market import validate
class DatedArchive(unittest.TestCase):
 def setUp(self):self.data=json.loads((ROOT/'data/korea-market.json').read_text())
 def test_more_than_five_snapshots_preserved(self):
  self.assertIn('2026-10-21',self.data['rankings']['daily']);self.assertGreater(len(self.data['rankings']['dates']),5);self.assertEqual(validate(self.data),[])
 def test_unsorted_duplicate_and_mismatched_dates_rejected(self):
  for kind in ['reverse','duplicate','missing']:
   p=copy.deepcopy(self.data);dates=p['rankings']['dates']
   if kind=='reverse':dates.reverse()
   elif kind=='duplicate':dates.append(dates[-1])
   else:dates.pop(0)
   self.assertTrue(any('rankings:' in e for e in validate(p)))
