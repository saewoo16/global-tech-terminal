import json
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
class October28CompanyFinancials(unittest.TestCase):
 def setUp(self):
  self.snapshot=json.loads((ROOT/'data/financial_backfill_zlatest_20261028.json').read_text())['companies']
 def test_exact_new_issuer_values(self):
  expected={'TSE:7751':('2026-09-30',1158815,97089),'TSE:4063':('2026-09-30',758260,212120),'HKEX:522':('2026-09-30',5247.045,798.571),'KRX:000660':('2026-09-30',104615500,83333800),'NASDAQ:NXPI':('2026-09-27',3786,1228),'NASDAQ:TER':('2026-09-27',1305.950,401.968),'NASDAQ:STX':('2026-10-02',4233,2064),'EURONEXT:ASM':('2026-09-30',1159.4,378.9),'NYSE:GLW':('2026-09-30',4855,911)}
  self.assertEqual(set(self.snapshot),set(expected))
  for s,v in expected.items():
   q=self.snapshot[s]['quarters'][0];self.assertEqual((q['date'],q['revenue'],q['operatingIncome']),v)
   self.assertTrue(q['sourceUrl'].startswith('https://'));self.assertTrue(q.get('observedAt'))
 def test_preliminary_and_prior_verification_preserved(self):
  for s in ['TSE:4063','HKEX:522','KRX:000660']:
   self.assertFalse(self.snapshot[s]['replaceQuarters']);self.assertEqual(len(self.snapshot[s]['quarters']),1)
  s=self.snapshot['KRX:000660'];self.assertIn('잠정',s['financialNote']);self.assertEqual(s['quarters'][0]['releaseStatus'],'preliminary')
 def test_gaap_operating_income_not_provider_adjusted(self):
  expected={'NASDAQ:NXPI':[1228,1071,1505,744],'NASDAQ:STX':[2064,1559,998,843],'NASDAQ:TER':[401.968,437.810,473.002,293.200]}
  for s,values in expected.items():self.assertEqual([q['operatingIncome'] for q in self.snapshot[s]['quarters']],values)
