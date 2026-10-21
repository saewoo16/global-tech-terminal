import datetime as dt,json,pathlib,unittest,importlib.util,tempfile,sys
from unittest.mock import patch
ROOT=pathlib.Path(__file__).resolve().parents[1]
PATH=ROOT/'data/korean_etf_charts.json'
if not PATH.exists():PATH=pathlib.Path(__file__).with_name('korean_etf_charts.json')
class ETFChartsTest(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.data=json.loads(PATH.read_text());cls.funds=cls.data['funds']
 def test_broad_coverage(self):
  self.assertGreaterEqual(len(self.funds),30)
  self.assertTrue({'445290','305720','455850','449450','0207G0'}<={f['code'] for f in self.funds})
 def test_user_exclusions_do_not_return(self):
  codes={f['code'] for f in self.funds}
  self.assertFalse(codes & {'069500','229200','462010','471990','463250'})
  self.assertTrue({'455860','455850','475300','475310','449450','0207G0'} <= codes)
 def test_representative_market_caps(self):
  for f in self.funds:
   r=f.get('representatives')
   if not r or r.get('status')=='unavailable':continue
   self.assertIn(r['scope'],{'etf','sector'})
   if r['scope']=='etf':self.assertIn('ETF',r['label'])
   self.assertTrue(r['asOf']);self.assertTrue(r['universeAsOf']);self.assertTrue(r['sourceUrls'])
   self.assertLessEqual(len(r['members']),3)
   caps=[m['marketCapKRW'] for m in r['members']]
   self.assertTrue(all(c>0 for c in caps));self.assertEqual(caps,sorted(caps,reverse=True))
   self.assertLessEqual(r['verifiedCount'],r['universeCount'])
 def test_real_ohlc(self):
  for f in self.funds:
   rows=f['daily'];self.assertTrue(rows,f['code']);self.assertEqual(len(rows),len({r['date'] for r in rows}));self.assertEqual(rows,sorted(rows,key=lambda x:x['date']))
   for r in rows:self.assertTrue(0<r['low']<=min(r['open'],r['close'])<=max(r['open'],r['close'])<=r['high']);self.assertGreaterEqual(r['volume'],0)
   self.assertEqual(rows[-1]['date'],f['dailyCoverage']['end'])
 def test_actual_intraday(self):
  for f in self.funds:
   i=f['intraday'];ps=i['points'];self.assertGreater(len(ps),1);self.assertEqual(i['exchange'],'KRX');self.assertEqual(len(ps),len({p['time'] for p in ps}))
   for p in ps:self.assertGreater(p['price'],0);self.assertTrue(p['time'].startswith(i['date']));self.assertTrue(p['time'].endswith('+09:00'));self.assertGreaterEqual(p.get('volume',0),0)
   self.assertEqual(sum(p.get('volume',0) for p in ps),ps[-1]['cumulativeVolume'])
 def test_no_aum_confusion(self):
  for f in self.funds:self.assertIsNone(f['aumKRW']);self.assertGreater(f['marketCapKRW'],0);self.assertEqual(len(f['sourceUrls']),4)
 def test_short_history_is_honest(self):
  space=next(f for f in self.funds if f['code']=='0207G0');self.assertTrue(space['dailyCoverage']['shortHistory']);self.assertEqual(space['daily'][0]['date'],'2026-06-16')
 def test_representative_refresh_failure_keeps_original_dates(self):
  from scripts import update_korean_etf_charts as mod
  from scripts import korean_etf_representatives as rep
  old={'scope':'etf','label':'ETF 내 시총 상위','asOf':'2026-10-20T07:00:00Z','universeAsOf':'2026-10-20','members':[{'name':'A','marketCapKRW':100}]}
  funds=[{'code':'TEST','sourceUrls':['https://example.com'] }]
  with patch.object(rep,'fetch_market_snapshot',side_effect=ValueError('offline')):
   mod.refresh_representatives(funds,{'TEST':{'representatives':old}})
  got=funds[0]['representatives'];self.assertEqual(got['asOf'],old['asOf']);self.assertEqual(got['members'],old['members']);self.assertEqual(got['refreshStatus'],'stale')
 def test_partial_refresh_preserves_previous_fund(self):
  script=ROOT/'scripts/update_korean_etf_charts.py'
  if not script.exists():script=pathlib.Path(__file__).with_name('update_korean_etf_charts.py')
  spec=importlib.util.spec_from_file_location('etf_collector_test',script);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
  old=self.funds[0];fresh=self.funds[1]
  with tempfile.TemporaryDirectory() as tmp:
   dest=pathlib.Path(tmp)/'snapshot.json';dest.write_text(json.dumps({'funds':[old]}))
   def build(spec,*args):
    if spec[0]==old['code']:raise ValueError('Simulated provider failure')
    return fresh
   with patch.object(mod,'UNIVERSE',[(old['code'],'x','industry'),(fresh['code'],'y','industry')]),patch.object(mod,'fetch',return_value=b'{"result":{"etfItemList":[]}}'),patch.object(mod,'build_fund',side_effect=build),patch.object(mod,'refresh_representatives'),patch.object(sys,'argv',['collector','--output',str(dest)]):mod.main()
   got=json.loads(dest.read_text());self.assertEqual(len(got['funds']),2);retained=next(f for f in got['funds'] if f['code']==old['code']);self.assertEqual(retained['daily'],old['daily']);self.assertEqual(retained['refreshStatus'],'stale');self.assertEqual(len(got['errors']),1)
if __name__=='__main__':unittest.main()
