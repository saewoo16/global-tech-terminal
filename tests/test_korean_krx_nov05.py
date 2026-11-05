"""Fixed-session regression: provisional KRX amounts and honest partial themes."""
import csv,json,pathlib,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
class November5KrxTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.root=ROOT/'data/korea-krx-evidence-20261105'
  cls.market=json.loads((ROOT/'data/korea-market.json').read_text())
  cls.evidence=json.loads((cls.root/'verified-daily-theme-flows.json').read_text())
 def test_raw_money_arithmetic_and_mapping(self):
  r=json.loads((self.root/'rankings-evidence.json').read_text());mp={x['itemcode']:x for x in r['marketMapping']}
  for who in ['foreign','institution']:
   raw=list(csv.DictReader((self.root/(who+'-20261105.csv')).read_text(encoding='cp949').splitlines()))
   for x in raw:
    self.assertIn(x['종목코드'],mp)
    self.assertEqual(int(x['거래대금_순매수']),int(x['거래대금_매수'])-int(x['거래대금_매도']))
   daily=self.market['rankings']['daily']['2026-11-05'][who]
   for market,sosok in [('KOSPI','0'),('KOSDAQ','1')]:
    wanted=sorted([x for x in raw if mp[x['종목코드']]['sosok']==sosok],key=lambda x:int(x['거래대금_순매수']),reverse=True)[:15]
    self.assertEqual([x['종목코드'] for x in wanted],[x['code'] for x in daily['byMarket'][market]])
 def test_missing_institution_amounts_remain_null(self):
  rows=self.market['themes']['daily']['2026-11-05']['rows']
  self.assertEqual(sum(r['coverage']['foreign']['status']=='complete' for r in rows),13)
  self.assertEqual(sum(r['coverage']['institution']['status']=='complete' for r in rows),3)
  for r in rows:
   c=r['coverage']['institution']
   if c['availableCount']<c['expectedCount']:
    self.assertIsNone(r['institution']);self.assertIsNone(c['netBuyKRW'])
    self.assertEqual(c['knownSubtotalKRW'],sum(x['netBuyKRW'] for x in c['memberFlows'] if x['netBuyKRW'] is not None))
 def test_actual_observation_times_and_provisional_scope(self):
  e=self.evidence
  self.assertEqual(e['asOf'],e['start']);self.assertEqual(e['start'],e['end'])
  self.assertEqual(e['collectionWindowUTC']['individualEnd'],'2026-11-05T09:59:47.674Z')
  self.assertEqual(e['sourceStatus'],'intraday_post_regular_close_provisional')
  self.assertIn('not a claim of final',e['finalDataNote'])
