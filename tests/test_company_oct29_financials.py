import json, pathlib, unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
class October29CompanyFinancials(unittest.TestCase):
 def test_official_operating_income_and_fiscal_ends(self):
  m=json.loads((ROOT/'data/market.json').read_text())['stocks']
  expected={'NASDAQ:INTC':[('2026-09-26',2522),('2026-06-27',1796),('2026-03-28',-3136),('2025-12-27',580)],'NASDAQ:LIN':[('2026-09-30',2150),('2026-06-30',2554),('2026-03-31',2439),('2025-12-31',2018)],'NYSE:STM':[('2026-09-26',367),('2026-06-27',187),('2026-03-28',70),('2025-12-31',125)],'NASDAQ:COHU':[('2026-09-26',12.801),('2026-06-27',.292),('2026-03-28',-11.154),('2025-12-27',-15.491)]}
  for symbol, rows in expected.items():
   bydate={q['date']:q for q in m[symbol]['quarters']}
   for date,op in rows:
    if date in bydate:self.assertAlmostEqual(bydate[date]['operatingIncome'],op,places=5)
 def test_source_snapshot_scope_precision_and_preliminary(self):
  s=json.loads((ROOT/'data/financial_backfill_zlatest_20261029_evening.json').read_text())
  self.assertEqual(len(s['companies']),10)
  for v in s['companies'].values():
   for q in v['quarters']:
    self.assertTrue(q['sourceUrl'].startswith('https://'))
    self.assertTrue(q.get('observedAt'))
    self.assertLessEqual(q['date'],s['asOf'])
  self.assertIn('estimated',json.dumps(s['companies']['EURONEXT:DSY']).lower())
  a=s['companies']['TSE:6857']['quarters'][0]
  self.assertEqual(a['revenue'],845200-367473)
  self.assertEqual(a['operatingIncome'],456809-189990)
if __name__=='__main__':unittest.main()
