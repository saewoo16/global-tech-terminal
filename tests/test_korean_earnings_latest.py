import copy,json,unittest
from pathlib import Path
from scripts.manage_briefings import validate_document
ROOT=Path(__file__).resolve().parents[1]
class KoreanEarnings(unittest.TestCase):
 def setUp(self):
  self.d=json.loads((ROOT/'data/briefings.json').read_text());self.e=next(e for e in self.d['entries'] if e['market']=='KR' and e['date']=='2026-10-29')
 def test_real_data(self):
  validate_document(self.d)
  self.assertGreaterEqual(len(self.e['earnings']['rows']),3)
  for r in self.e['earnings']['rows']:
   self.assertEqual(r['releaseDate'],'2026-10-29');self.assertEqual(len(r['quarterlyHistory']['rows']),4)
 def test_previous_release_rejected(self):
  self.e['earnings']['rows'][0]['releaseDate']='2026-10-28'
  with self.assertRaises(ValueError):validate_document(self.d)
 def test_duplicate_company_rejected(self):
  self.e['earnings']['rows'].append(copy.deepcopy(self.e['earnings']['rows'][0]))
  with self.assertRaises(ValueError):validate_document(self.d)
 def test_wrong_margin_rejected(self):
  self.e['earnings']['rows'][0]['quarterlyHistory']['rows'][0]['operatingMargin']=0
  with self.assertRaises(ValueError):validate_document(self.d)
 def test_unverified_call_rejected(self):
  r=self.e['earnings']['rows'][0];r['callStatus']='release_summary';r['callHighlights']=['Unsupported call']
  with self.assertRaises(ValueError):validate_document(self.d)
 def test_missing_quarter_keeps_null(self):
  q=self.e['earnings']['rows'][0]['quarterlyHistory']['rows'][0];q.update(revenue=None,operatingIncome=None,operatingMargin=None);validate_document(self.d)
 def test_unverified_membership_rejected(self):
  self.e['earnings']['rows'][0]['membershipVerified']=False
  with self.assertRaises(ValueError):validate_document(self.d)
if __name__=='__main__':unittest.main()
