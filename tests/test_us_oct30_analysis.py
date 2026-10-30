import datetime as dt
import json
import unittest
from pathlib import Path
from zoneinfo import ZoneInfo
ROOT=Path(__file__).resolve().parents[1]
class October30Analysis(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.payload=json.loads((ROOT/'data/us_analysis.json').read_text());cls.entry=next(e for e in cls.payload['entries'] if e['date']=='2026-10-30');cls.ev=json.loads((ROOT/'data/us-close-evidence-20261030.json').read_text());cls.etfs=json.loads((ROOT/'data/overseas_etf_charts.json').read_text())
 def test_cutoff_and_session(self):
  self.assertEqual(self.entry['sessionVerification']['previousSession'],'2026-10-29');c=dt.datetime.fromisoformat(self.entry['reportCutoffAt']);self.assertEqual(c.astimezone(ZoneInfo('Asia/Seoul')).isoformat(),'2026-10-31T07:00:00+09:00');self.assertGreaterEqual(dt.datetime.fromisoformat(self.payload['updatedAt']),c)
 def test_earnings_date_and_no_recycled_releases(self):
  rows=self.entry['earnings']['rows'];self.assertEqual(len(rows),len({r['ticker']for r in rows}));self.assertFalse({'AMZN','INTC','RDDT'} & {r['ticker']for r in rows})
  for r in rows:
   self.assertEqual(r['releaseDate'],'2026-10-30');self.assertEqual(len(r['quarterlyHistory']['rows']),4)
   self.assertEqual([m['label']for m in r['metrics']],['매출','매출총이익','매출총이익률','영업이익','EPS'])
 def test_breadth_and_same_session_prices(self):
  rows=self.ev['screens']['dailyRows'];counts={k:0 for k in ['advancing','declining','unchanged']}
  for r in rows:
   self.assertEqual(r['asOf'],'2026-10-30');self.assertEqual(r['previousSession'],'2026-10-29');self.assertAlmostEqual(r['changePct'],(r['close']/r['previousClose']-1)*100,places=7);counts['advancing'if r['close']>r['previousClose']else'declining'if r['close']<r['previousClose']else'unchanged']+=1
  self.assertEqual(self.entry['breadth']['counts'],counts)
 def test_etfs_every_actual_tail_and_anchors(self):
  self.assertEqual(len(self.etfs['funds']),38)
  for f in self.etfs['funds']:
   self.assertGreaterEqual(f['daily'][-1]['date'],'2026-10-30');bars={b['date']:b for b in f['daily']}
   for b in f['daily']:self.assertLessEqual(b['low'],min(b['open'],b['close']));self.assertGreaterEqual(b['high'],max(b['open'],b['close']))
   for p in ['day','week','month']:
    self.assertAlmostEqual(f['returns'][p],(f['daily'][-1]['close']/bars[f['returnAnchors'][p]]['close']-1)*100,places=7)
 def test_sector_actual_dates(self):
  self.assertEqual(len(self.entry['sectors']['rows']),40)
  for r in self.entry['sectors']['rows']:self.assertEqual(r['calculation']['asOf'],'2026-10-30')
if __name__=='__main__':unittest.main()
