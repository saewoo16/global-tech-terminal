import copy,json,pathlib,sys,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from validate_korean_market import validate
class SectorCorrection(unittest.TestCase):
 def test_four_raw_close_recoveries_have_precise_crosschecked_boundaries(self):
  d=json.loads((ROOT/'data/korea-market.json').read_text());rows={r['id']:r for r in d['sectorReturns']['rows']};self.assertEqual(validate(d),[])
  for key in ('autos','steel','chart-etf-139260','chart-etf-117460'):
   r=rows[key];self.assertEqual(r['asOf'],'2026-10-29');c=r['calculation'];component=c['constituentData'][0];self.assertEqual(component['collectionMethod'],'naver_mobile_daily_actual_close_crosschecked_yahoo_raw')
   for period,base in c['bases'].items():self.assertAlmostEqual(r[period],100*(component['observations'][c['end']]['close']/component['observations'][base]['close']-1),places=9)
  self.assertAlmostEqual(rows['chart-etf-139260']['day'],100*(121645/122215-1),places=9)
 def test_crosschecked_raw_method_requires_evidence_hash(self):
  d=json.loads((ROOT/'data/korea-market.json').read_text());row=next(r for r in d['sectorReturns']['rows'] if r['id']=='chart-etf-139260');row['calculation']['constituentData'][0]['evidenceSha256']='';self.assertTrue(any('non-adjusted source basis' in e for e in validate(d)))
