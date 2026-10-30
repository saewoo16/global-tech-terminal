import copy,json,pathlib,sys,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from validate_korean_market import validate

class SectorCorrection(unittest.TestCase):
 def fixture_payload(self):
  # A dated repair regression must not pin the live daily dashboard to October29.
  # These four rows are preserved from the published commit, not regenerated
  # from whatever source/collection method the current session uses.
  fixture=json.loads((ROOT/'tests/fixtures/korean_sector_correction_20261029.json').read_text())
  d=json.loads((ROOT/'data/korea-market.json').read_text())
  d['sectorReturns']=copy.deepcopy(fixture['sectorReturns'])
  sources={r['id']:r for r in d['sources']}
  sources.update({r['id']:r for r in fixture['sources']})
  d['sources']=list(sources.values())
  return d

 def test_four_raw_close_recoveries_have_precise_crosschecked_boundaries(self):
  d=self.fixture_payload();rows={r['id']:r for r in d['sectorReturns']['rows']};self.assertEqual(validate(d),[])
  evidence=json.loads((ROOT/'data/korea-sector-correction-evidence-20261029.json').read_text())
  checks={r['code']:r for r in evidence['rawCrossChecks']}
  for key in ('autos','steel','chart-etf-139260','chart-etf-117460'):
   r=rows[key];self.assertEqual(r['asOf'],'2026-10-29');c=r['calculation'];component=c['constituentData'][0];self.assertEqual(component['collectionMethod'],'naver_mobile_daily_actual_close_crosschecked_yahoo_raw')
   check=checks[component['ticker'].split('.')[0]]
   self.assertEqual(component['evidenceSha256'],check['naverSha256'])
   self.assertEqual(component['observations'],check['verifiedObservations'])
   for period,base in c['bases'].items():self.assertAlmostEqual(r[period],100*(component['observations'][c['end']]['close']/component['observations'][base]['close']-1),places=9)
  self.assertAlmostEqual(rows['chart-etf-139260']['day'],100*(121645/122215-1),places=9)

 def test_crosschecked_raw_method_requires_evidence_hash(self):
  d=self.fixture_payload();self.assertEqual(validate(d),[])
  row=next(r for r in d['sectorReturns']['rows'] if r['id']=='chart-etf-139260')
  row['calculation']['constituentData'][0]['evidenceSha256']=''
  self.assertTrue(any('non-adjusted source basis' in e for e in validate(d)))
