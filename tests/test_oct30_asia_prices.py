import json,unittest,datetime as dt
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class October30AsianPrices(unittest.TestCase):
 def test_completed_adjusted_prices_and_honest_candle_fallback(self):
  ev=json.loads((ROOT/'data/price-refresh-evidence-20261030-asia.json').read_text());m=json.loads((ROOT/'data/market.json').read_text())['stocks']
  self.assertEqual(len(ev['records']),113);self.assertEqual(len({r['symbol'] for r in ev['records']}),113)
  for r in ev['records']:
   self.assertEqual(r['status'],'verified',r['symbol']);self.assertEqual(r['point'][0],'2026-10-30');self.assertGreaterEqual(m[r['symbol']]['lastPriceDate'],'2026-10-30');self.assertEqual(r['point'][1],round(r['rawTarget']['adjustedClose'],5));self.assertEqual(len(r['rawSha256']),64)
   observed=dt.datetime.fromisoformat(r['observedAt']);self.assertGreater(observed,dt.datetime.fromisoformat(r['exchangeCloseCutoff']));self.assertGreater(observed.timestamp(),r['sourceRegularPeriod']['end'])
   q=r.get('completeIndependentTarget',r['rawTarget']);self.assertLessEqual(q['low'],min(q['open'],q['close']));self.assertGreaterEqual(q['high'],max(q['open'],q['close']))
   if 'rejectedYahooCandleReason' in r:self.assertIn('gtimg.cn',r['independentSourceUrl']);self.assertLess(abs(q['close']-r['rawTarget']['adjustedClose']),0.005)
 def test_western_session_not_pulled_into_asia_refresh(self):
  m=json.loads((ROOT/'data/market.json').read_text())['stocks'];ev=json.loads((ROOT/'data/price-refresh-evidence-20261030-asia.json').read_text())
  self.assertTrue(all(r['symbol'].split(':')[0] in ['KRX','TSE','TWSE','TPEX','SSE','SZSE','HKEX'] for r in ev['records']))
