import unittest,json,pathlib,datetime as dt
ROOT=pathlib.Path(__file__).resolve().parents[1]
class October30WesternCompanyCloses(unittest.TestCase):
 def test_completed_source_sessions_and_prices(self):
  ev=json.loads((ROOT/'data/price-refresh-evidence-20261030-us-europe.json').read_text());m=json.loads((ROOT/'data/market.json').read_text())['stocks']
  self.assertEqual(len(ev['records']),134);self.assertEqual(len({r['symbol']for r in ev['records']}),134)
  self.assertEqual(sum('reusedSource'in r for r in ev['records']),66)
  for r in ev['records']:
   self.assertEqual(r['status'],'verified',r['symbol']);self.assertEqual(r['sourceSessionDate'],'2026-10-30');self.assertEqual(r['point'][0],'2026-10-30');self.assertGreaterEqual(m[r['symbol']]['lastPriceDate'],'2026-10-30');self.assertEqual(r['point'][1],round(r['rawTarget']['adjustedClose'],5))
   obs=dt.datetime.fromisoformat(r['observedAt']);self.assertGreaterEqual(obs,dt.datetime.fromisoformat(r['exchangeCloseCutoff']));self.assertGreaterEqual(obs.timestamp(),r['sourceRegularPeriod']['end']);self.assertEqual(len(r['rawSha256']),64)
   q=r.get('replacementCompleteCandle',r['rawTarget']);self.assertGreater(q['low'],0);self.assertLessEqual(q['low'],min(q['open'],q['close']));self.assertGreaterEqual(q['high'],max(q['open'],q['close']))
 def test_dlr_complete_independent_candle(self):
  ev=json.loads((ROOT/'data/price-refresh-evidence-20261030-us-europe.json').read_text());r=next(r for r in ev['records']if r['symbol']=='NYSE:DLR');q=r['replacementCompleteCandle']
  self.assertGreater(r['rawTarget']['open'],r['rawTarget']['high']);self.assertEqual(q['currency'],'USD');self.assertLess(abs(q['close']-r['rawTarget']['close']),.001);self.assertLess(abs(q['close']-q['change_abs']-r['rawPrevious']['close']),.001)
if __name__=='__main__':unittest.main()
