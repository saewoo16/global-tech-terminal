"""Keep verified Nov 3 calls on their original release card and cutoff."""
import json
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
class November3CallFollowup(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  payload=json.loads((ROOT/'data/us_analysis.json').read_text())
  cls.entry=next(e for e in payload['entries'] if e['date']=='2026-11-03')
  cls.rows={r['ticker']:r for r in cls.entry['earnings']['rows']}
 def test_pfizer_official_full_transcript_is_supplement(self):
  r=self.rows['PFE'];e=r['callEvidence']
  self.assertEqual(r['releaseDate'],'2026-11-03')
  self.assertEqual(r['callPresentationPhase'],'supplement')
  self.assertEqual(e['type'],'official-ir-hosted-edited-transcript')
  self.assertTrue(e['qaVerified']);self.assertTrue(e['fullTranscriptVerified'])
  self.assertTrue(e['postCutoffSupplement']);self.assertIsNone(e['publishedAt'])
  self.assertEqual(e['observedAt'],'2026-11-03T22:36:17Z')
  self.assertEqual(self.entry['reportCutoffAt'],'2026-11-04T07:00:00+09:00')
  ids={s['id']:s for s in self.entry['sources']}
  self.assertTrue(all(s in ids for s in r['callSourceIds']))
  self.assertIn('s206.q4cdn.com/795948973/',ids[r['callSourceIds'][0]]['url'])
 def test_revvity_margin_display_preserves_precision(self):
  m=next(m for m in self.rows['RVTY']['metrics'] if m['label']=='매출총이익률')
  self.assertEqual(m['value'],'57.43%')
  self.assertAlmostEqual(m['raw']['value'],57.42620033776971,places=12)
if __name__=='__main__':unittest.main()
