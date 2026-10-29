import json
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
class October29CompanyFinancials(unittest.TestCase):
 def setUp(self):
  self.s=json.loads((ROOT/'data/financial_backfill_zlatest_20261029.json').read_text())['companies']
 def test_exact_official_latest_quarters(self):
  expected={'NASDAQ:MSFT':(92279,45915),'NASDAQ:GOOGL':(127577,40576),'NASDAQ:KLAC':(4136.015,1861.670),'NYSE:NOW':(4106,385),'NYSE:APH':(10229.7,3020.8),'NASDAQ:ADP':(5490.7,None),'NYSE:VRT':(4312.8,983.8),'NYSE:TEL':(5312,1093),'NASDAQ:FLEX':(8491,414),'NASDAQ:FTNT':(2078.4,704.3),'NASDAQ:EQIX':(2571,600),'KRX:009150':(3763300,691000),'TSE:6723':(435917,565311)}
  self.assertEqual(set(self.s),set(expected))
  for symbol,values in expected.items():
   q=self.s[symbol]['quarters'][0];self.assertEqual((q['revenue'],q['operatingIncome']),values)
   self.assertTrue(q['sourceUrl'].startswith('https://'));self.assertTrue(q['observedAt']);self.assertEqual(q['verifiedAt'],'2026-10-29')
 def test_real_fiscal_dates_and_missing_adp_op(self):
  self.assertEqual([q['date'] for q in self.s['NYSE:TEL']['quarters']],['2026-09-25','2026-06-26','2026-03-27','2025-12-26'])
  self.assertEqual(self.s['NASDAQ:FLEX']['quarters'][0]['date'],'2026-09-25')
  self.assertIsNone(self.s['NASDAQ:ADP']['quarters'][0]['operatingIncome'])
  self.assertTrue(self.s['NASDAQ:ADP']['quarters'][0]['operatingIncomeNotDisclosed'])
 def test_retention_has_no_unverified_historical_copy(self):
  for s in ['NASDAQ:MSFT','NASDAQ:GOOGL','NASDAQ:KLAC','NYSE:NOW','NYSE:APH','NASDAQ:ADP','NASDAQ:FLEX','NASDAQ:FTNT','KRX:009150','TSE:6723']:self.assertEqual(len(self.s[s]['quarters']),1)
  self.assertEqual([q['operatingIncome'] for q in self.s['NYSE:TEL']['quarters']],[1093,981,954,963])
