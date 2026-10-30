import unittest,json,pathlib
ROOT=pathlib.Path(__file__).resolve().parents[1]
class October30CompanyOfficialSupplement(unittest.TestCase):
 def test_scope_and_reported_quarters(self):
  d=json.loads((ROOT/'data/financial_backfill_zlatest_20261030_us_official.json').read_text());c=d['companies'];self.assertEqual(len(c),5);self.assertEqual(sum(len(x['quarters'])for x in c.values()),14)
  for k,v in c.items():
   for q in v['quarters']:
    self.assertTrue(q['sourceUrl'].startswith('https://'));self.assertLessEqual(q['date'],'2026-09-30');self.assertTrue(q.get('observedAt'));self.assertIn(q['reportedCurrency'],['USD','EUR'])
  for k in ['EURONEXT:AI','EURONEXT:SU']:self.assertTrue(all(q['operatingIncome']is None for q in c[k]['quarters']))
  self.assertEqual([q['operatingIncome']for q in c['MIL:PRY']['quarters']],[614,500,406]);self.assertEqual([q['operatingIncome']for q in c['NASDAQ:FORM']['quarters']],[81.597,57.799,16.648,23.49]);self.assertEqual([q['operatingIncome']for q in c['NASDAQ:TTMI']['quarters']],[162.253,109.055,72.449,80.749])
if __name__=='__main__':unittest.main()
