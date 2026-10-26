import datetime as dt
import json
import pathlib
import unittest
from scripts import update_korean_etf_charts as mod

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
  self.assertEqual([r['name'] for r in funds['0207G0']['representatives']['members']],['에이치브이엠','스피어','인텔리안테크'])
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
  self.assertEqual([r['name'] for r in f['representatives']['members']],['현대차','로보티즈','에스피지'])
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
