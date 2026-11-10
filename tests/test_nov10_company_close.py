import json,unittest
from pathlib import Path
R=Path(__file__).resolve().parents[1]
class November10CompanyClose(unittest.TestCase):
 def test_verified_prices(self):
  e=json.loads((R/'data/price-refresh-evidence-20261110-asia.json').read_text());self.assertEqual(e['count'],113)
  for r in e['records']:
   self.assertEqual(r['point'][0],'2026-11-10');self.assertTrue(r['validation']['sessionCompleted']);self.assertTrue(r['validation']['independentCurrentAndPreviousClose'])
 def test_official_quarters(self):
  s=json.loads((R/'data/financial_backfill_zlatest_20261110_asia_official.json').read_text())
  expected={'TSE:6758':(3429446,622329),'TSE:4186':(77856,17192),'TSE:6855':(10853,3008),'TSE:285A':(2480035,1994710),'TSE:6965':(70313,10827)}
  self.assertEqual(set(s['companies']),set(expected))
  for k,(rev,op) in expected.items():
   q=s['companies'][k]['quarters'][0];self.assertEqual((q['revenue'],q['operatingIncome']),(rev,op));self.assertEqual(q['date'],'2026-09-30');self.assertEqual(q['periodStart'],'2026-07-01');self.assertTrue(q['sourceUrl'].startswith('https://'));self.assertEqual(q['reportedCurrency'],'JPY')
if __name__=='__main__':unittest.main()
