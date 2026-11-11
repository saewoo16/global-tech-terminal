import json
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
class November11Release(unittest.TestCase):
 def test_session_and_companion_charts(self):
  data=json.loads((ROOT/'data/us_analysis.json').read_text());entry=next(e for e in data['entries'] if e['date']=='2026-11-11')
  self.assertEqual(entry['sessionVerification']['closedAt'],'2026-11-11T16:00:00-05:00')
  self.assertEqual(entry['reportCutoffAt'],'2026-11-12T07:00:00+09:00')
  self.assertEqual(entry['coverage']['dailyValid'],503)
  self.assertEqual(entry['breadth']['counts'],{'advancing':332,'declining':168,'unchanged':3})
  self.assertEqual(len(entry['sectors']['rows']),40)
  self.assertTrue(all(r['calculation']['asOf']=='2026-11-11' for r in entry['sectors']['rows']))
  self.assertEqual(entry['coverage']['newHighCount'],16)
  self.assertEqual(entry['coverage']['nearOnlyCount'],51)
  self.assertTrue(all(r['releaseDate']=='2026-11-11' for r in entry['earnings']['rows']))
if __name__=='__main__':unittest.main()
