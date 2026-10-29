import json,unittest,datetime as dt
from pathlib import Path
from zoneinfo import ZoneInfo
ROOT=Path(__file__).resolve().parents[1]
class October29AsianCloses(unittest.TestCase):
 def test_verified_exchange_scope_and_full_precision(self):
  x=json.loads((ROOT/'data/price-refresh-evidence-20261029-asia.json').read_text());self.assertEqual(x['count'],113);self.assertEqual(len({r['symbol'] for r in x['records']}),113)
  for r in x['records']:
   self.assertIn(r['symbol'].split(':')[0],['KRX','TSE','TWSE','TPEX','HKEX','SSE','SZSE']);self.assertEqual(r['status'],'verified');self.assertFalse(r['overlapRevisions']);self.assertEqual(r['point'],['2026-10-29',round(r['rawTarget']['adjustedClose'],5)]);self.assertEqual(r['previousPoint'],r['previousStoredPoint']);self.assertEqual(len(r['rawSha256']),64)
   self.assertGreater(dt.datetime.fromisoformat(r['observedAt']),dt.datetime.fromisoformat(r['regularSessionEnd']));self.assertEqual(dt.datetime.fromtimestamp(r['rawTarget']['timestamp'],ZoneInfo(r['exchangeTimezoneName'])).date().isoformat(),'2026-10-29')
 def test_latest_data_never_regresses_before_verified_session(self):
  m=json.loads((ROOT/'data/market.json').read_text())['stocks'];x=json.loads((ROOT/'data/price-refresh-evidence-20261029-asia.json').read_text())
  for r in x['records']:self.assertGreaterEqual(m[r['symbol']]['prices'][-1][0],'2026-10-29')
