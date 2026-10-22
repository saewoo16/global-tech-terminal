import json
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class MongoDBCoverage(unittest.TestCase):
    def test_company_explorer_mapping_and_verified_snapshot(self):
        companies=json.loads((ROOT/'data/companies.json').read_text())
        matches=[r for r in companies if r['symbol']=='NASDAQ:MDB']
        self.assertEqual(len(matches),1)
        self.assertEqual(matches[0]['ticker'],'MDB')
        self.assertEqual(matches[0]['category'],'AI·데이터')
        self.assertIn('Atlas',matches[0]['business'])
        snapshot=json.loads((ROOT/'data/financial_backfill_zmongodb_20261022.json').read_text())
        qs=snapshot['companies']['NASDAQ:MDB']['quarters']
        self.assertEqual([(q['date'],q['revenue'],q['operatingIncome']) for q in qs],[('2026-07-31',771.773,28.4),('2026-04-30',687.616,-24.804),('2026-01-31',695.072,0.304),('2025-10-31',628.309,-18.424)])
        for q in qs:
            self.assertTrue(q['sourceUrl'].startswith('https://investors.mongodb.com/'))
            self.assertEqual(q['reportedCurrency'],'USD')
            self.assertLess(q['periodStart'],q['date'])
            self.assertLessEqual(q['publishedAt'],q['verifiedAt'])
    def test_chart_and_financial_dates_are_independent(self):
        s=json.loads((ROOT/'data/market.json').read_text())['stocks']['NASDAQ:MDB']
        self.assertGreater(len(s['prices']),1000)
        self.assertGreaterEqual(s['prices'][-1][0],'2026-10-21')
        self.assertEqual(s['lastPriceDate'],s['prices'][-1][0])
        self.assertGreater(s['marketCapUSD'],0)
        self.assertEqual(s['priceCurrency'],'USD')
        self.assertEqual(len(s['quarters']),4)
if __name__=='__main__':unittest.main()
