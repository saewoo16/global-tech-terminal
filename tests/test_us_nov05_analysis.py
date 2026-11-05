import json,unittest,math
from pathlib import Path
R=Path(__file__).resolve().parents[1]
def load(p):return json.loads((R/p).read_text())
class November5USAnalysis(unittest.TestCase):
 def setUp(self):
  self.e=next(e for e in load('data/us_analysis.json')['entries'] if e['date']=='2026-11-05')
  self.ev=load('data/us-close-evidence-20261105.json')
 def test_session_breadth_and_scope(self):
  e=self.e;self.assertEqual(e['reportCutoffAt'],'2026-11-06T07:00:00+09:00');self.assertEqual(e['sessionVerification']['closedAt'],'2026-11-05T16:00:00-05:00');self.assertEqual(e['breadth']['counts'],{'advancing':73,'declining':430,'unchanged':0});self.assertEqual(e['coverage']['dailyValid'],503)
  self.assertEqual(len({r['cik'] for r in self.ev['screens']['dailyRows']}),500)
 def test_split_returns_are_same_basis(self):
  proof=load('data/us-etf-split-evidence-20261105.json')
  for ticker,f in proof['funds'].items():
   prices={p['date']:p for p in f['prices']};self.assertEqual(f['split']['numerator'],3)
   for p in f['prices']:self.assertAlmostEqual(p['close'],p['originalClose']/p['priceDivisor'])
   for row in self.e['sectors']['rows']:
    if row.get('ticker')==ticker:
     self.assertAlmostEqual(row['day'],f['returns']['day'],places=2)
     self.assertGreater(row['day'],-20)
 def test_earnings_date_and_archive(self):
  for row in self.e['earnings']['rows']:
   self.assertEqual(row['releaseDate'],'2026-11-05');self.assertEqual(row['presentationVersion'],3)
  dates=[e['date'] for e in load('data/us_analysis.json')['entries']]
  self.assertEqual(len(dates),len(set(dates)));self.assertIn('2026-11-04',dates)
 def test_verified_etf_evidence_is_date_scoped(self):
  a=load('data/overseas-etf-audit-20261105.json');self.assertIn('2026-11-05',json.dumps(a));self.assertIn('SOXX',json.dumps(a));self.assertIn('ITA',json.dumps(a))
