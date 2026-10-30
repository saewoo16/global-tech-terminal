import hashlib,json,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class Oct29EarningsDetail(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.entry=next(e for e in json.loads((ROOT/'data/us_analysis.json').read_text())['entries'] if e['date']=='2026-10-29')
  cls.rows={r['ticker']:r for r in cls.entry['earnings']['rows']}
 def test_session_scope_and_cutoff(self):
  self.assertEqual(len(self.rows),60)
  for r in self.rows.values():
   self.assertEqual(r['releaseDate'],'2026-10-29')
   self.assertEqual(r['reportCutoffAt'],'2026-10-30T07:00:00+09:00')
 def test_market_panels_unchanged(self):
  market={k:v for k,v in self.entry.items() if k not in ['earnings','sources']}
  self.assertEqual(hashlib.sha256(json.dumps(market,sort_keys=True,ensure_ascii=False).encode()).hexdigest(),'bb048d60bc3431a164e07eaedf40a412b23c12b7874a95a164fdf80cf447b797')
 def test_sbux_comparable_eps_and_true_nondisclosure(self):
  r=self.rows['SBUX'];m=r['consensusMetrics'][0]
  self.assertEqual(m['raw']['value'],.8);self.assertEqual(m['raw']['yearAgoQuarter'],.52);self.assertEqual(m['raw']['previousQuarter'],.85)
  self.assertEqual(m['yoy'],'+53.85%');self.assertEqual(m['qoq'],'-5.88%')
  for m in r['metrics'][1:3]:self.assertEqual(m['value'],'미공시');self.assertIsNone(m['raw']['value'])
  self.assertTrue(r['suppressPresentationSummary']);self.assertEqual(r['displayReleaseHighlights'],[])
 def test_verified_full_cost_derivations(self):
  for ticker,expected in [('GILD',6729),('INCY',1448.460),('LHX',1612)]:
   r=self.rows[ticker];rev=r['metrics'][0]['raw']['value'];gp=r['metrics'][1]['raw']['value'];gpm=r['metrics'][2]['raw']['value']
   self.assertAlmostEqual(gp,expected);self.assertAlmostEqual(gpm,gp/rev*100)
 def test_loss_comparisons_do_not_claim_positive_growth(self):
  for t in ['CARR','INCY']:
   self.assertEqual(self.rows[t]['metrics'][4]['yoy'],'적자 전환')
 def test_guidance_keeps_range_and_basis(self):
  g=next(g for g in self.rows['SBUX']['guidanceMetrics'] if g.get('consensusComparable'))
  self.assertEqual((g['low'],g['high'],g['consensusValue']),(3.15,3.25,3.14));self.assertNotIn('value',g)
  self.assertIn('Non-GAAP',g['basis'])
 def test_all_sixty_have_review_evidence(self):
  audits=json.loads((ROOT/'data/earnings-detail-audit-20261029.json').read_text())['audit']
  self.assertEqual({a['ticker'] for a in audits if a.get('ticker')},set(self.rows))
