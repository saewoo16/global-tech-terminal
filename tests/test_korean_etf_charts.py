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
  self.assertTrue({'445290','305720','455850','471990','463250','0207G0'}<={f['code'] for f in self.funds})
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
   with patch.object(mod,'UNIVERSE',[(old['code'],'x','industry'),(fresh['code'],'y','industry')]),patch.object(mod,'fetch',return_value=b'{"result":{"etfItemList":[]}}'),patch.object(mod,'build_fund',side_effect=build),patch.object(sys,'argv',['collector','--output',str(dest)]):mod.main()
   got=json.loads(dest.read_text());self.assertEqual(len(got['funds']),2);retained=next(f for f in got['funds'] if f['code']==old['code']);self.assertEqual(retained['daily'],old['daily']);self.assertEqual(retained['refreshStatus'],'stale');self.assertEqual(len(got['errors']),1)
if __name__=='__main__':unittest.main()
