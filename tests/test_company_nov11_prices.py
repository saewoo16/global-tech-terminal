import json, unittest, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from update_data import preserve_verified_price_history
class CompanyPriceRefresh(unittest.TestCase):
 def test_history_revisions_are_not_silently_spliced(self):
  old=[['2026-11-06',341.72],['2026-11-10',350]]
  kept,reason=preserve_verified_price_history(old,[['2026-11-06',340.67383],['2026-11-11',352]])
  self.assertEqual(kept,old);self.assertTrue(reason)
 def test_compatible_new_points_append_preserving_precision(self):
  old=[['2026-11-10',350.12345]]
  got,reason=preserve_verified_price_history(old,[['2026-11-10',350.123449],['2026-11-11',352]])
  self.assertEqual(got,old+[['2026-11-11',352]]);self.assertIsNone(reason)
 def test_current_listing_and_all_completed_prices(self):
  d=json.loads((ROOT/'data/market.json').read_text());cs=json.loads((ROOT/'data/companies.json').read_text())
  self.assertIn('NASDAQ:SHOP',d['stocks']);self.assertNotIn('NYSE:SHOP',d['stocks'])
  self.assertTrue(any(c['symbol']=='NASDAQ:SHOP' for c in cs))
  for s in d['stocks'].values():self.assertGreaterEqual(s['prices'][-1][0],'2026-11-11')
