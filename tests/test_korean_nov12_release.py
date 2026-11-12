"""Nov12 release evidence checks; prior panels remain archived rather than redated."""
import gzip,hashlib,json,unittest
from pathlib import Path
R=Path(__file__).resolve().parents[1]
class November12Release(unittest.TestCase):
 def test_prior_panel_snapshot_is_preserved(self):
  m=json.loads((R/'data/korea-analysis-snapshot-before-20261112-manifest.json').read_text());raw=(R/m['file']).read_bytes();self.assertEqual(hashlib.sha256(raw).hexdigest(),m['sha256']);p=json.loads(gzip.decompress(raw));self.assertEqual(p['asOf'],'2026-11-11');self.assertEqual(p['sectorReturns']['asOf'],'2026-11-11')
 def test_actual_index_close_crosscheck(self):
  b=json.loads((R/'data/briefings.json').read_text());e=next(e for e in b['entries']if e['market']=='KR' and e['date']=='2026-11-12');v={r['name']:r for r in e['indices']};self.assertEqual(v['KOSPI']['close'],5342.73);self.assertEqual(v['KOSDAQ']['close'],696.53)
  for row in v.values():self.assertEqual(row['marketStatus'],'CLOSE');self.assertEqual(row['sessionDate'],'2026-11-12');self.assertAlmostEqual(row['close']-row['previousClose'],row['change'],places=6)
 def test_earnings_do_not_invent_missing_quarters(self):
  b=json.loads((R/'data/briefings.json').read_text());e=next(e for e in b['entries']if e['market']=='KR' and e['date']=='2026-11-12');self.assertEqual(len(e['earnings']['rows']),16)
