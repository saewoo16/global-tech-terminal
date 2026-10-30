import unittest,json,pathlib,datetime as dt
ROOT=pathlib.Path(__file__).resolve().parents[1]
class October30CompanyFilingAudit(unittest.TestCase):
 def test_official_facts_and_compatible_fourth_quarter(self):
  d=json.loads((ROOT/'data/financial_backfill_zlatest_20261030_us_extra.json').read_text());self.assertEqual(set(d['companies']),{'NASDAQ:UCTT','NYSE:RBLX','NASDAQ:VIAV'})
  for s,c in d['companies'].items():
   self.assertEqual(len(c['quarters']),4);self.assertTrue(c['replaceQuarters']);self.assertEqual(c['reportingCurrency'],'USD')
   for q in c['quarters']:
    self.assertIn('sec.gov',q['sourceUrl']);self.assertEqual(q['reportedCurrency'],'USD');self.assertLessEqual(q['publishedAt'],'2026-10-30');self.assertTrue(q['observedAt'].startswith('2026-10-30T'))
    if 'sourceFacts'in q:
     for k in ['revenue','operatingIncome']:
      f=q['sourceFacts'][k];self.assertEqual(f['end'],q['date']);self.assertEqual(f['start'],q['periodStart']);self.assertAlmostEqual(q[k],f['val']/1e6)
    else:
     for k in ['revenue','operatingIncome']:
      x=q['derivation']['inputs'][k];self.assertEqual(x['annual']['start'],x['nineMonths']['start']);self.assertEqual(x['annual']['end'],q['date']);self.assertAlmostEqual(q[k],(x['annual']['val']-x['nineMonths']['val'])/1e6)
 def test_viav_exact_fiscal_operating_income(self):
  d=json.loads((ROOT/'data/financial_backfill_zlatest_20261030_us_extra.json').read_text());q=d['companies']['NASDAQ:VIAV']['quarters'];self.assertEqual([x['operatingIncome']for x in q],[61.3,24.8,11.4,7.6]);self.assertEqual([x['date']for x in q],['2026-06-27','2026-03-28','2025-12-27','2025-09-27'])
if __name__=='__main__':unittest.main()
