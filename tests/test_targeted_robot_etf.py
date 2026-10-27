import copy
import math
import datetime as dt
import json
import pathlib
import unittest
from scripts import update_korean_etf_charts as mod


def assert_weight_snapshot(test, snapshot):
 """Validate a dated live snapshot, not the names ranked on its initial day."""
 test.assertEqual(snapshot['basis'], 'portfolioWeight')
 test.assertEqual(snapshot['status'], 'verified')
 date = dt.date.fromisoformat(snapshot['universeAsOf'])
 observed = dt.datetime.fromisoformat(snapshot['asOf'].replace('Z', '+00:00'))
 test.assertIsNotNone(observed.tzinfo)
 test.assertLessEqual(date, observed.astimezone(dt.timezone(dt.timedelta(hours=9))).date())
 holdings = snapshot['holdings']
 test.assertGreaterEqual(len(holdings), 3)
 test.assertEqual(snapshot['verifiedCount'], len(holdings))
 test.assertEqual(snapshot['universeCount'], len(holdings))
 test.assertEqual(snapshot['missingComponents'], [])
 identities = []
 for row in holdings:
  test.assertTrue(row['name'])
  identity = row.get('isin') or row.get('code') or row['name']
  identities.append(identity)
  test.assertFalse((row.get('isin') or '').startswith(('KRD', 'KR4', 'KR5')))
  test.assertFalse(any(word in row['name'].upper() for word in ('현금', '예금', 'CASH')))
  weight = row['weightPct']
  test.assertIsInstance(weight, (int, float))
  test.assertNotIsInstance(weight, bool)
  test.assertTrue(math.isfinite(weight))
  test.assertGreaterEqual(weight, 0)
  test.assertLessEqual(weight, 100)
 test.assertEqual(len(identities), len(set(identities)))
 ranked = sorted(holdings, key=lambda row: (-row['weightPct'], row.get('isin') or row['name']))
 test.assertEqual(holdings, ranked)
 test.assertEqual(snapshot['members'], ranked[:3])

class TargetedRobotETFTest(unittest.TestCase):
 def test_targeted_fund_is_additive_and_source_dated(self):
  data=json.loads((pathlib.Path(__file__).resolve().parents[1]/'data/korean_etf_charts.json').read_text())
  funds={f['code']:f for f in data['funds']}
  self.assertGreaterEqual(len(funds),39)
  self.assertTrue({'0148J0','0207G0','0177X0','421320'}<=funds.keys())
  space=funds['421320']
  self.assertEqual(space['name'],'PLUS 우주항공')
  self.assertEqual(space['listedAt'],'2022-03-29')
  self.assertEqual(space['category'],'우주항공')
  assert_weight_snapshot(self, funds['0207G0']['representatives'])
  f=funds['0177X0'];e=f['selectionEvidence']
  self.assertEqual(f['name'],'ACE K휴머노이드로봇산업TOP2+')
  self.assertEqual(f['category'],'로봇 TOP2+')
  self.assertEqual(f['listedAt'],'2026-04-07')
  self.assertTrue(all(row['date']>=f['listedAt'] for row in f['daily']))
  self.assertEqual(e['asOf'],'2026-10-26')
  self.assertEqual(e['sourceType'],'public_market_data_provider')
  target=[r for r in e['holdings'] if r['name'] in e['targetNames']]
  self.assertEqual(len(target),6);self.assertAlmostEqual(sum(r['weightPct'] for r in target),53.42)
  self.assertEqual(next(r['weightPct'] for r in e['holdings'] if r['name']=='현대차'),20.75)
  self.assertIn('순수 중소형주 ETF는 아닙니다',e['disclosure'])
  self.assertEqual(f['sourceUrls'][0],mod.official('0177X0',f['name']))
  self.assertIn(('0177X0','로봇 TOP2+','theme'),mod.UNIVERSE)
  self.assertEqual(f['representatives']['basis'],'portfolioWeight')
  assert_weight_snapshot(self, f['representatives'])
 def test_current_candle_is_excluded_before_regular_close(self):
  rows=[{'date':'2026-10-23'},{'date':'2026-10-26'},{'date':'2026-10-27'}]
  before=dt.datetime.fromisoformat('2026-10-26T15:29:59+09:00')
  after=dt.datetime.fromisoformat('2026-10-26T15:30:00+09:00')
  self.assertEqual(mod.completed_daily(rows,before),rows[:1])
  self.assertEqual(mod.completed_daily(rows,after),rows[:2])
  self.assertEqual(mod.completed_daily(rows,before.astimezone(dt.timezone.utc)),rows[:1])
  self.assertEqual(rows[-1]['date'],'2026-10-27')

class WeightRepresentativesTest(unittest.TestCase):
 def row(self,name,weight,count=4,isin=None):
  return {'componentName':name,'componentItemCode':name,'weight':weight,'componentCount':str(count),'referenceDate':'2026-10-26','componentIsinCode':isin or name}
 def build(self,rows):
  from scripts.korean_etf_representatives import build_weight_representatives
  return build_weight_representatives('x',rows,'2026-10-26T00:00:00Z')
 def test_weight_rank_includes_foreign_and_excludes_cash(self):
  r=self.build([self.row('Japanese',30,isin='JP123'),self.row('Korean',10,isin='KR123'),self.row('Other',20),self.row('현금',40)])
  self.assertEqual([m['name'] for m in r['members']],['Japanese','Other','Korean'])
  self.assertEqual(r['basis'],'portfolioWeight');self.assertEqual(r['status'],'verified')
 def test_invalid_weight_never_falls_back_to_cap(self):
  for invalid in [None,'NaN',-1,101,'unknown']:
   r=self.build([self.row('A',invalid,count=1)])
   self.assertEqual(r['status'],'partial');self.assertEqual(r['members'],[])
 def test_partial_and_mixed_dates_fail_closed(self):
  self.assertEqual(self.build([self.row('A',20)])['members'],[])
  rows=[self.row('A',20,count=2),self.row('B',10,count=2)];rows[1]['referenceDate']='2026-10-23'
  self.assertEqual(self.build(rows)['status'],'partial')
 def test_old_market_cap_snapshot_not_reused(self):
  from unittest.mock import patch
  from scripts import korean_etf_representatives as rep
  old={'basis':'marketCap','members':[{'name':'large','marketCapKRW':100}]}
  funds=[{'code':'x','sourceUrls':['https://example.com']}]
  with patch.object(rep,'collect_weight_representatives',side_effect=ValueError('offline')):mod.refresh_representatives(funds,{'x':{'representatives':old}})
  self.assertEqual(funds[0]['representatives']['members'],[])


class LiveWeightRankRegressionTest(unittest.TestCase):
 def snapshot(self, weights=(20.75, 19.04, 13.71, 12.0)):
  from scripts.korean_etf_representatives import build_weight_representatives
  rows = [{'componentName': name, 'componentItemCode': str(i),
           'componentIsinCode': 'KR7' + str(i), 'weight': weight,
           'referenceDate': '2026-10-27', 'componentCount': '4'}
          for i, (name, weight) in enumerate(zip(('현대차', '로보티즈', '에스피지', '새편입종목'), weights))]
  return build_weight_representatives('0177X0', rows, '2026-10-27T09:00:00Z')
 def test_changed_weight_order_and_new_top_three_are_valid(self):
  for weights, names in [((20.75, 19.04, 13.71, 12.0), ['현대차', '로보티즈', '에스피지']),
                         ((19.97, 20.60, 13.68, 12.0), ['로보티즈', '현대차', '에스피지']),
                         ((19.97, 20.60, 13.68, 30.0), ['새편입종목', '로보티즈', '현대차'])]:
   with self.subTest(weights=weights):
    snapshot = self.snapshot(weights)
    assert_weight_snapshot(self, snapshot)
    self.assertEqual([r['name'] for r in snapshot['members']], names)
 def test_invalid_published_snapshots_are_rejected(self):
  valid = self.snapshot()
  mutations = {}
  s = copy.deepcopy(valid); s['members'].reverse(); mutations['wrong_members_order'] = s
  s = copy.deepcopy(valid); s['holdings'].reverse(); mutations['wrong_holdings_order'] = s
  s = copy.deepcopy(valid); s['holdings'][1] = copy.deepcopy(s['holdings'][0]); mutations['duplicate'] = s
  s = copy.deepcopy(valid); s['holdings'][0]['name'] = '원화현금'; mutations['cash'] = s
  s = copy.deepcopy(valid); s['holdings'][0]['isin'] = 'KR4000'; mutations['derivative'] = s
  s = copy.deepcopy(valid); s['universeAsOf'] = '2026-10-28'; mutations['future_date'] = s
  s = copy.deepcopy(valid); s['status'] = 'partial'; mutations['partial'] = s
  for weight in [float('nan'), float('inf'), -1, 101, '20', None, True]:
   s = copy.deepcopy(valid); s['holdings'][0]['weightPct'] = weight; mutations['weight_' + str(weight)] = s
  for reason, snapshot in mutations.items():
   with self.subTest(reason=reason), self.assertRaises(AssertionError):
    assert_weight_snapshot(self, snapshot)
 def test_duplicate_and_cash_source_rows_fail_closed_or_are_excluded(self):
  from scripts.korean_etf_representatives import build_weight_representatives
  rows = [{'componentName': name, 'componentItemCode': str(i), 'componentIsinCode': isin,
           'weight': weight, 'referenceDate': '2026-10-27', 'componentCount': '4'}
          for i, (name, isin, weight) in enumerate([
           ('A', 'KR7001', 20), ('B', 'KR7002', 15), ('C', 'KR7003', 10), ('원화현금', 'KRD001', 55)])]
  s = build_weight_representatives('x', rows, '2026-10-27T09:00:00Z')
  assert_weight_snapshot(self, s)
  self.assertEqual([r['name'] for r in s['members']], ['A', 'B', 'C'])
  rows[1]['componentIsinCode'] = rows[0]['componentIsinCode']
  s = build_weight_representatives('x', rows, '2026-10-27T09:00:00Z')
  self.assertEqual(s['status'], 'partial')
  self.assertEqual(s['members'], [])
