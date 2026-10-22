import copy,json,sys,unittest,datetime as dt
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from validate_us_analysis import validate,validate_earnings_prices
class October22AnalysisTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.data=json.loads((ROOT/'data/us_analysis.json').read_text());cls.e=next(e for e in cls.data['entries']if e['date']=='2026-10-22');cls.ev=json.loads((ROOT/'data/us-close-evidence-20261022.json').read_text())
 def test_session_and_panels(self):
  validate(self.data);e=self.e;self.assertEqual(e['sessionVerification']['previousSession'],'2026-10-21');self.assertEqual(e['reportCutoffAt'],'2026-10-22T22:00:00Z');self.assertEqual(e['coverage']['dailyValid'],503)
  self.assertEqual(len(e['sectors']['rows']),40);self.assertEqual(len(e['constituents']),503)
  for r in self.ev['screens']['dailyRows']:self.assertEqual(r['asOf'],e['date']);self.assertEqual(r['previousSession'],'2026-10-21')
 def test_earnings_actual_et_date_and_current_scope(self):
  rows=self.e['earnings']['rows'];ts={r['ticker']for r in rows};self.assertEqual(len(rows),len(ts));self.assertIn('BE',ts);self.assertIn('PG',ts);self.assertIn('WDC',ts)
  self.assertFalse(ts & {'META','TSLA','SPCX','FCX','GD','INTC','DLR','POOL','TFX'})
  for r in rows:self.assertEqual(r['releaseDate'],'2026-10-22');self.assertEqual(len(r['quarterlyHistory']['rows']),4)
 def test_neutral_initial_quotes_and_late_supplements(self):
  bars={r['ticker']:r for r in self.ev['screens']['dailyRows']}
  for r in self.e['earnings']['rows']:
   p=r['priceReaction'];self.assertEqual(p['regular']['close'],bars[r['ticker']]['close']);a=p.get('subsequentAfterHours')or p['afterHours'];self.assertEqual(a['status'],'verified');self.assertAlmostEqual(a['changePct'],(a['price']/p['regular']['close']-1)*100)
   if 'subsequentAfterHours' in p:self.assertGreater(a['collectedAt'],'2026-10-22T22:00:00')
  r=copy.deepcopy(next(r for r in self.e['earnings']['rows']if r['ticker']=='PG'));validate_earnings_prices(r);r['priceReaction']['afterHours']['collectedAt']='2026-10-22T22:01:00Z'
  with self.assertRaises(AssertionError):validate_earnings_prices(r)
 def test_prior_entries_preserved(self):
  self.assertEqual(len(next(e for e in self.data['entries']if e['date']=='2026-10-21')['earnings']['rows']),20)
