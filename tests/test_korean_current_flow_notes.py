import json,pathlib,unittest
class CurrentFlowNotes(unittest.TestCase):
 def test_nov10_current_notes_keep_period_dates(self):
  k=json.loads((pathlib.Path(__file__).resolve().parents[1]/'data/korea-market.json').read_text())
  if k['asOf']!='2026-11-10':return
  self.assertIn('11/10',k['rankings']['note']);self.assertIn('11/3~11/9',k['rankings']['note']);self.assertIn('10/13~11/9',k['rankings']['note'])
  self.assertFalse(any(n.startswith('11/9 시장 수급은 17:43') for n in k['limitations']))
  self.assertIn('KRX 공식',k['themes']['notes'][7]);self.assertIn('19:46~19:47',k['themes']['notes'][7])
