import unittest,json,pathlib,datetime as dt
ROOT=pathlib.Path(__file__).resolve().parents[1]
class CompletedCompanyCloses(unittest.TestCase):
 def test_all_source_observations_follow_regular_close(self):
  e=json.loads((ROOT/'data/price-refresh-evidence-20261029-us-europe.json').read_text());self.assertEqual(len(e['records']),134);self.assertEqual(len({r['symbol'] for r in e['records']}),134)
  for r in e['records']:
   self.assertEqual(r['status'],'verified');self.assertEqual(r['sourceSessionDate'],'2026-10-29');self.assertGreaterEqual(dt.datetime.fromisoformat(r['observedAt']),dt.datetime.fromisoformat(r['regularSessionEnd']));self.assertEqual(r['point'][0],'2026-10-29');self.assertGreater(r['sourcePrecisionValue'],0)
 def test_entg_adjustment_retains_full_historical_window(self):
  e=json.loads((ROOT/'data/price-refresh-evidence-20261029-us-europe.json').read_text());r=next(r for r in e['records'] if r['symbol']=='NASDAQ:ENTG');h=r['historicalAdjustment'];self.assertEqual(h['sourceDividendEvent']['amount'],.1);self.assertEqual(h['rawAdjustedPoints'][0][0],h['originalFirstDate']);self.assertEqual(len(h['rawAdjustedPoints']),1255);self.assertEqual(h['rawAdjustedPoints'][-1][0],'2026-10-29')
if __name__=='__main__':unittest.main()
