import json,pathlib,unittest
P=pathlib.Path(__file__).resolve().parents[1]
class CompanyNov03(unittest.TestCase):
 def test_complete_sessions_and_repairs(self):
  e=json.loads((P/'data/price-refresh-evidence-20261102-us-europe.json').read_text());m=json.loads((P/'data/market.json').read_text())['stocks']
  self.assertEqual(len(e['records']),134)
  self.assertEqual(len(e['independentCompleteCandleRepairs']),6)
  for r in e['records']:
   self.assertEqual(r['status'],'verified');self.assertEqual(r['point'][0],'2026-11-02');self.assertGreaterEqual(m[r['symbol']]['prices'][-1][0],'2026-11-02')
   if r.get('alternativeCompleteBar'):
    b=r['alternativeCompleteBar'];self.assertLessEqual(b['low'],min(b['open'],b['close']));self.assertGreaterEqual(b['high'],max(b['open'],b['close']))
 def test_on_official_quarters(self):
  b=json.loads((P/'data/financial_backfill_zlatest_20261103_us_official.json').read_text())['companies']['NASDAQ:ON']
  self.assertEqual([q['date'] for q in b['quarters']],['2026-10-02','2026-07-03','2026-04-03','2025-12-31'])
  self.assertEqual([q['operatingIncome'] for q in b['quarters']],[378.3,258.6,-53.4,200.1])
