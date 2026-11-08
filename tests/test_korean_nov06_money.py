"""Fixed public Nov6 observation, retained after a separate official KRX import."""
import hashlib,json,pathlib,sys,unittest
from decimal import Decimal
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from korean_rankings_source import preferred

class November6MoneyTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.market=json.loads((ROOT/'data/korea-market.json').read_text())
  cls.evidence=json.loads((ROOT/'data/korea-money-evidence-20261106.json').read_text())
  cls.rankEvidence=json.loads((ROOT/'data/korea-rankings-evidence-20261106.json').read_text())
  cls.publicDaily=json.loads((ROOT/'data/korea-krx-evidence-20261106/previous-public-daily-snapshot.json').read_text())['daily']
  cls.raw={x['file']:x for x in cls.evidence['rawResponses']}
 def test_actual_observation_times_and_source_windows(self):
  self.assertEqual(len(self.raw),12)
  for filename,o in self.raw.items():
   self.assertEqual(o['httpStatus'],200)
   self.assertTrue(o['observedAt'].startswith('2026-11-08T00:4'))
   period=filename.split('-')[0]
   expected={'DAY':'20261106','WEEK':'20261102','MONTH':'20261012'}[period]
   for side,rows in o['payload']['sections'].items():
    self.assertGreaterEqual(len(rows),15)
    for row in rows:
     self.assertEqual((row['bizdateFrom'],row['bizdateTo']),(expected,'20261106'))
     self.assertIsNot(row.get('estimated'),True)
     self.assertEqual(Decimal(row['accTradeAmount']),int(row['accTradeAmount']))
 def test_prior_daily_observations_unchanged(self):
  for family,days in self.evidence['preservedDailySnapshots'].items():
   self.assertEqual(len(days),16)
   for day,want in days.items():
    actual=hashlib.sha256(json.dumps(self.market[family]['daily'][day],ensure_ascii=False,sort_keys=True).encode()).hexdigest()
    self.assertEqual(actual,want,(family,day))
 def test_rankings_equal_source_top15(self):
  for api,key in [('DAY','2026-11-06'),('WEEK','aggregate5d'),('MONTH','monthly')]:
   section=self.publicDaily['rankings'] if api=='DAY' else self.market['rankings'][key]
   for inv,who in [('FOREIGNER','foreign'),('ORGANIZATION','institution')]:
    for market in ('KOSPI','KOSDAQ'):
     raw=self.raw[f'{api}-{market}-{inv}.json']['payload']['sections']['buyRankList']
     expected=[x for x in raw if x['type']=='ST' and not preferred(x)][:15]
     rows=section[who]['byMarket'][market]
     self.assertEqual([r['code'] for r in rows],[r['itemcode'] for r in expected])
     for row,source in zip(rows,expected):
      self.assertEqual(row['valueKRW'],int(source['accTradeAmount']))
      self.assertEqual(Decimal(str(row['value']))*100000000,row['valueKRW'])
 def test_theme_amounts_match_source_and_missing_are_null(self):
  for api,key in [('DAY','2026-11-06'),('WEEK','aggregate5d'),('MONTH','monthly')]:
   section=self.publicDaily['themes'] if api=='DAY' else self.market['themes'][key]
   for inv,who in [('FOREIGNER','foreign'),('ORGANIZATION','institution')]:
    source={x['itemcode']:int(x['accTradeAmount']) for market in ('KOSPI','KOSDAQ') for side in ('buyRankList','sellRankList') for x in self.raw[f'{api}-{market}-{inv}.json']['payload']['sections'][side] if x['type']=='ST'}
    for row in section['rows']:
     c=row['coverage'][who];known=[];missing=[]
     for member in c['memberFlows']:
      expected=source.get(member['code'])
      self.assertEqual(member['netBuyKRW'],expected)
      (known if expected is not None else missing).append(member)
     self.assertEqual(c['availableCount'],len(known))
     self.assertEqual(c['expectedCount'],len(known)+len(missing))
     self.assertEqual(c['missingMembers'],[x['code'] for x in missing])
     self.assertEqual(c['knownSubtotalKRW'],sum(x['netBuyKRW'] for x in known))
     if missing:self.assertIsNone(c['netBuyKRW']);self.assertIsNone(row[who])
     else:self.assertEqual(c['netBuyKRW'],c['knownSubtotalKRW'])
 def test_partial_counts_not_full_coverage(self):
  rows=self.publicDaily['themes']['rows']
  self.assertEqual(len(rows),13)
  self.assertEqual(self.publicDaily['themes']['status'],'partial')
  for who in ('foreign','institution'):
   self.assertEqual([r['name'] for r in rows if r['coverage'][who]['status']=='complete'],['정유'])
  self.assertEqual(sum(r['memberCount'] for r in rows),1239)
  self.assertEqual(len({m['code'] for r in rows for m in r['coverage']['foreign']['memberFlows']}),1065)
 def test_turnover_is_source_amount_not_price_times_volume(self):
  section=self.market['rankings']['daily']['2026-11-06']['tradedValue']
  self.assertEqual(section['status'],'verified')
  raw={x['file']:x for x in self.evidence['turnoverRawResponses']}
  universe=[x for x in raw['universe.json']['payload'] if x['type']=='ST' and not preferred(x) and x['sosok'] in ('0','1')]
  self.assertEqual(len(universe),2610)
  expected=sorted(universe,key=lambda x:int(x['tradeAmount']),reverse=True)[:20]
  self.assertEqual([x['code'] for x in section['rows']],[x['itemcode'] for x in expected])
  for row,source in zip(section['rows'],expected):
   self.assertEqual(Decimal(str(row['value']))*100000000,int(source['tradeAmount']))
  self.assertEqual(section['coverage']['end'],'2026-11-06')
 def test_sell_evidence_keeps_negative_sign_and_order(self):
  for period in self.rankEvidence['periods'].values():
   for investor in period.values():
    for rows in investor['sellByMarket'].values():
     self.assertEqual(len(rows),15)
     amounts=[r['valueKRW'] for r in rows]
     self.assertTrue(all(a<0 for a in amounts));self.assertEqual(amounts,sorted(amounts))
 def test_membership_and_price_dates_remain_explicit(self):
  self.assertEqual(self.market['themes']['membershipAsOf'],'2026-10-19')
  self.assertIn('11/6 완료 종가',self.market['indexMovers']['note'])

if __name__=='__main__':unittest.main()
