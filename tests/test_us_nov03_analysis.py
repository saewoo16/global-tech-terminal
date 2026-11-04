"""Regression checks for the verified Nov 3 ET close snapshot."""
import datetime as dt
import json
import unittest
from pathlib import Path
from zoneinfo import ZoneInfo
ROOT=Path(__file__).resolve().parents[1]
class November3Analysis(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.payload=json.loads((ROOT/'data/us_analysis.json').read_text());cls.entry=next(e for e in cls.payload['entries']if e['date']=='2026-11-03');cls.ev=json.loads((ROOT/'data/us-close-evidence-20261103.json').read_text());cls.etfs=json.loads((ROOT/'data/overseas_etf_charts.json').read_text())
 def test_cutoff_and_completed_session(self):
  e=self.entry;self.assertEqual(e['sessionVerification']['previousSession'],'2026-11-02');self.assertEqual(e['sessionVerification']['closedAt'],'2026-11-03T16:00:00-05:00');self.assertEqual(e['reportCutoffAt'],'2026-11-04T07:00:00+09:00');self.assertGreaterEqual(dt.datetime.fromisoformat(self.payload['updatedAt']),dt.datetime.fromisoformat(e['reportCutoffAt']));self.assertEqual(len(e['indices']),4)
 def test_earnings_are_actual_session_not_prior_releases(self):
  rows=self.entry['earnings']['rows'];self.assertEqual(len(rows),len({r['ticker']for r in rows}));self.assertFalse({'AAPL','PLTR','CE','TSM','SPCX'}&{r['ticker']for r in rows})
  for r in rows:
   self.assertEqual(r['releaseDate'],'2026-11-03');self.assertEqual([m['label']for m in r['metrics']],['매출','매출총이익','매출총이익률','영업이익','EPS']);self.assertEqual(len(r['quarterlyHistory']['rows']),4)
   # Primary display adapter must not activate the archived Boeing OP exception.
   self.assertIsNot(r['metrics'][3].get('raw',{}).get('consensusComparable'),True)
   if r.get('releaseTiming',{}).get('publishedAt'):self.assertEqual(dt.datetime.fromisoformat(r['releaseTiming']['publishedAt']).astimezone(ZoneInfo('America/New_York')).date().isoformat(),r['releaseDate'])
 def test_close_breadth_and_missing_kvue(self):
  rows=self.ev['screens']['dailyRows'];counts={k:0 for k in ['advancing','declining','unchanged']}
  for r in rows:
   self.assertEqual(r['asOf'],'2026-11-03');self.assertEqual(r['previousSession'],'2026-11-02');self.assertAlmostEqual(r['changePct'],(r['close']/r['previousClose']-1)*100,places=7);counts['advancing'if r['close']>r['previousClose']else'declining'if r['close']<r['previousClose']else'unchanged']+=1
  self.assertEqual(self.entry['breadth']['counts'],counts);self.assertEqual(self.entry['breadth']['validCount'],502);self.assertEqual(self.entry['breadth']['missingTickers'],['KVUE']);self.assertNotIn('OKTA',{r['ticker']for r in rows})
 def test_etf_actual_bars_and_returns(self):
  self.assertEqual(len(self.etfs['funds']),38)
  for f in self.etfs['funds']:
   self.assertGreaterEqual(f['daily'][-1]['date'],'2026-11-03');bars={b['date']:b for b in f['daily']}
   for b in f['daily']:self.assertLessEqual(b['low'],min(b['open'],b['close']));self.assertGreaterEqual(b['high'],max(b['open'],b['close']))
   for p in ['day','week','month']:self.assertAlmostEqual(f['returns'][p],(f['daily'][-1]['close']/bars[f['returnAnchors'][p]]['close']-1)*100,places=7)
 def test_sector_dates_and_anchors(self):
  self.assertEqual(len(self.entry['sectors']['rows']),40)
  for r in self.entry['sectors']['rows']:
   self.assertEqual(r['calculation']['asOf'],'2026-11-03');self.assertEqual(r['calculation']['anchors'],{'day':'2026-11-02','week':'2026-10-27','month':'2026-10-02'})
if __name__=='__main__':unittest.main()
