import json,pathlib,unittest
P=pathlib.Path(__file__).resolve().parents[1]
class CompanyNov02(unittest.TestCase):
 def test_completed_sessions_and_no_financial_relabel(self):
  m=json.loads((P/'data/market.json').read_text())['stocks']; ev=json.loads((P/'data/price-refresh-evidence-20261102-asia.json').read_text())
  self.assertEqual(len(ev['records']),113)
  for r in ev['records']:
   self.assertEqual(r['status'],'verified')
   s=m[r['symbol']];self.assertGreaterEqual(s['prices'][-1][0],'2026-11-02')
  for r in ev['records']:
   if 'rejectedYahooCandleReason' in r:
    b=r['completeIndependentTarget'];self.assertLessEqual(b['low'],min(b['open'],b['close']));self.assertGreaterEqual(b['high'],max(b['open'],b['close']))
 def test_kyocera_official_single_quarter(self):
  b=json.loads((P/'data/financial_backfill_zlatest_20261102_asia_official.json').read_text())
  q=next(q for q in b['companies']['TSE:6971']['quarters'] if q['date']=='2026-09-30')
  self.assertEqual(q['revenue'],1078337-525383);self.assertEqual(q['operatingIncome'],65609-49101);self.assertEqual(q['publishedAt'],'2026-11-02')

 def test_keyence_dates_and_delta_op(self):
  b=json.loads((P/"data/financial_backfill_zlatest_20261102_asia_official.json").read_text())["companies"]
  self.assertEqual([q["date"] for q in b["TSE:6861"]["quarters"]],["2026-09-20","2026-06-20","2026-03-20","2025-12-20"])
  q=b["TWSE:2308"]["quarters"];self.assertEqual([x["operatingIncome"] for x in q],[32600,30570.042,28417.303,26418.465]);self.assertIn("0.1 billion",q[0]["sourcePrecision"])
