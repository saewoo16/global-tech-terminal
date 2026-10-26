import json,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class ReconciledFinancialTests(unittest.TestCase):
 def test_source_values(self):
  stock=json.loads((ROOT/'data/market.json').read_text())['stocks']
  for symbol,date,revenue,op,currency in [('NASDAQ:TXN','2026-09-30',6055,2874,'USD'),('NYSE:SAP','2026-09-30',10270,2930,'EUR'),('SIX:ABBN','2026-09-30',9701,1846,'USD')]:
   q=stock[symbol]['quarters'][0]
   self.assertEqual((q['date'],q['revenue'],q['operatingIncome'],q['reportedCurrency']),(date,revenue,op,currency))
   self.assertTrue(q['sourceUrl'].startswith('https://'))
 def test_abb_comparable_continuing_operations(self):
  snapshot=json.loads((ROOT/'data/financial_backfill_zlatest_20261025_abb.json').read_text())
  qs=snapshot['companies']['SIX:ABBN']['quarters']
  self.assertEqual([(q['revenue'],q['operatingIncome']) for q in qs],[(9701,1846),(9475,1585),(8734,1780),(9052,1505)])
  self.assertTrue(all('Robotics excluded' in q['basis'] for q in qs))
  self.assertEqual(sum(q['operatingIncome'] for q in qs[:3]),5211)
