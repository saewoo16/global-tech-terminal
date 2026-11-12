import unittest,json,math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class Nov11Heatmap(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.d=json.loads((ROOT/'data/korea-market.json').read_text());cls.day=cls.d['heatmaps']['asOf'];cls.previous=cls.d['heatmaps']['previousSession'];cls.e=json.loads((ROOT/cls.d['heatmaps']['evidenceFiles'][0]).read_text());cls.q={r['code']:r for r in cls.e['quotes']}
 def test_full_retained_universe_attempted(self):
  self.assertEqual(self.e['eligibleCount'],2610);self.assertTrue(self.e['fullUniverseAttempt'])
  for k,m in self.d['heatmaps']['markets'].items():
   c=m['coverage'];self.assertEqual(c['sampleCount'],len(m['rows'])+len(c['excluded']))
   self.assertTrue(set(r['code']for r in m['rows']).issubset(self.q))
 def test_complete_ohlc_and_exact_returns(self):
  for m in self.d['heatmaps']['markets'].values():
   for r in m['rows']:
    q=self.q[r['code']]['observations']
    for date in [self.day,self.previous]:
     a=q[date];self.assertTrue(0<a['low']<=min(a['open'],a['close'])<=max(a['open'],a['close'])<=a['high']);self.assertGreater(a['volume'],0)
    self.assertEqual(r['asOf'],self.day);self.assertEqual(r['close'],q[self.day]['close']);self.assertEqual(r['previousClose'],q[self.previous]['close']);self.assertAlmostEqual(r['changePct'],100*(r['close']/r['previousClose']-1),places=10)
 def test_share_and_classification_dates_not_redated(self):
  h=self.d['heatmaps'];self.assertEqual(h['classification']['asOf'],'2026-10-17');self.assertTrue(h['sharesSnapshotRetrievedAt'].startswith('2026-11-06'))
  for m in h['markets'].values():
   for r in m['rows']:
    self.assertTrue(r['sharesSnapshotRetrievedAt'].startswith('2026-11-06'));self.assertEqual(r['marketCapKRW'],r['close']*r['sharesOutstanding'])
 def test_raw_source_completed_before_observation(self):
  import datetime
  for r in self.e['quotes']:
   end=r['meta'].get('currentTradingPeriod',{}).get('regular',{}).get('end')
   if end:self.assertLess(end,datetime.datetime.fromisoformat(r['retrievedAt']).timestamp())
 def test_independent_overrides_keep_original_bad_bar(self):
  for x in self.e['independentCrosschecks']:
   if 'error'in x:continue
   a=x['originalYahooOHLC'];b=x['independentOHLC'];self.assertFalse(a['low']<=min(a['open'],a['close'])<=max(a['open'],a['close'])<=a['high']);self.assertEqual(a['close'],b['close']);self.assertEqual(x['sourceTimestamp'],self.day.replace('-','.')+' 15:30');self.assertEqual(self.q[x['code']]['observations'][self.day],b)
