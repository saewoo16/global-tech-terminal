import copy
import json
import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from apply_financial_backfills import apply
class October27CompanyFilings(unittest.TestCase):
 def setUp(self):
  self.snapshot=json.loads((ROOT/'data/financial_backfill_zlatest_20261027_us.json').read_text())
 def test_four_source_backed_quarters(self):
  self.assertEqual(set(self.snapshot['companies']),{'NASDAQ:CDNS','NASDAQ:RMBS','NASDAQ:AMKR','NYSE:CLS'})
  market=json.loads((ROOT/'data/market.json').read_text())
  for symbol,record in self.snapshot['companies'].items():
   self.assertEqual(len(record['quarters']),4)
   self.assertEqual(market['stocks'][symbol]['quarters'],record['quarters'])
   for q in record['quarters']:
    self.assertTrue(q['sourceUrl'].startswith('https://'))
    self.assertEqual(q['sourceType'],'filing')
    self.assertEqual(q['reportedCurrency'],'USD')
    self.assertIn('sourceFacts',q)
 def test_snapshot_survives_feed_without_destroying_newer_quarter(self):
  for symbol,record in self.snapshot['companies'].items():
   old=copy.deepcopy(record['quarters'])
   for q in old:q.update(sourceType='aggregator',revenue=1,operatingIncome=2)
   item={'prices':[['2026-10-26',123]],'quarters':old,'financialCheckedAt':'2026-10-26T23:39:21+00:00','marketCapUSD':12345}
   result=apply({'stocks':{symbol:item}},[{'asOf':self.snapshot['asOf'],'companies':{symbol:record}}])['stocks'][symbol]
   self.assertEqual(result['quarters'],record['quarters'])
   self.assertEqual(result['financialCheckedAt'],'2026-10-26T23:39:21+00:00')
   self.assertEqual(result['prices'],[['2026-10-26',123]])
   self.assertEqual(result['marketCapUSD'],12345)
