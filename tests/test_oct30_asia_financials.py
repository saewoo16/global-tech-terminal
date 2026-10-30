import json,unittest,datetime as dt
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class OfficialAsiaOctober30(unittest.TestCase):
 def test_official_source_period_arithmetic(self):
  d=json.loads((ROOT/'data/financial_backfill_zlatest_20261030_asia.json').read_text());m=json.loads((ROOT/'data/market.json').read_text())['stocks']
  self.assertGreaterEqual(len(d['companies']),7)
  for symbol,c in d['companies'].items():
   self.assertEqual(len(m[symbol]['quarters']),4)
   for q in c['quarters']:
    self.assertLessEqual(q['publishedAt'],'2026-10-30');self.assertEqual(q['reportedCurrency'],c['reportingCurrency']);self.assertTrue(q['sourceUrl'].startswith('https://'));self.assertEqual(len(q['sourceSha256']),64)
    actual=next(v for v in m[symbol]['quarters'] if v['date']==q['date']);self.assertEqual(actual['revenue'],q['revenue']);self.assertEqual(actual['operatingIncome'],q['operatingIncome'])
    if q.get('derivation'):
     for k in ['revenue','operatingIncome']:
      v=q['derivation'][k]
      if 'sixMonths' in v:self.assertEqual(v['sixMonths']-v['firstQuarter'],q[k])
      else:self.assertIn('thousand TWD / 1000',q['derivation']['method']);self.assertEqual(v['raw']/1000,q[k])
      self.assertEqual(v['value'],q[k])
