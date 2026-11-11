"""Date-scoped evidence for the November 7 catch-up of completed November 6 sessions."""
import datetime as dt
import json
from pathlib import Path
import unittest
from zoneinfo import ZoneInfo
ROOT=Path(__file__).resolve().parents[1]
class CompanyNovember6Refresh(unittest.TestCase):
 def setUp(self):
  self.m=json.loads((ROOT/'data/market.json').read_text());self.e=json.loads((ROOT/'data/price-refresh-evidence-20261106-us-europe.json').read_text());self.a=json.loads((ROOT/'data/price-refresh-evidence-20261106-asia.json').read_text())
 def test_all_listings_have_actual_completed_target(self):
  records=self.e['records']+self.a['records'];self.assertEqual(len(records),247);self.assertEqual(len({r['symbol']for r in records}),247)
  for r in records:
   self.assertTrue(r['status'].startswith('verified'));self.assertTrue(r['validation']['identity']);self.assertTrue(r['validation']['sessionCompleted']);self.assertEqual(r['sourceSessionDate'],'2026-11-06')
   self.assertLess(dt.datetime.fromtimestamp(r['sourceRegularPeriod']['end'],dt.timezone.utc),dt.datetime.fromisoformat(r['observedAt']))
   stock=self.m['stocks'][{'NYSE:SHOP':'NASDAQ:SHOP'}.get(r['symbol'],r['symbol'])];self.assertGreaterEqual(stock['prices'][-1][0],'2026-11-06')
   self.assertAlmostEqual(dict(stock['prices'])['2026-11-06'],r['rawTarget']['adjustedClose'],places=4)
 def test_full_simo_adjustment_and_csco_preservation(self):
  records={r['symbol']:r for r in self.e['records']};s=records['NASDAQ:SIMO'];self.assertEqual(s['status'],'verified_full_adjustment');rec=s['reconciliation'];self.assertEqual(rec['dividendPerADS'],.575);self.assertEqual(len(rec['historyReplacement']),rec['storedDatesVerified']);self.assertGreater(rec['storedDatesVerified'],1200)
  self.assertEqual(records['NASDAQ:CSCO']['status'],'verified_preserved_history');self.assertGreater(records['NASDAQ:CSCO']['reconciliation']['verifiedUnchangedRecentAnchorDates'],20)
 def test_fx_uses_source_timezone(self):
  fx=self.e['fxVerification'];self.assertEqual(fx['date'],'2026-11-06');self.assertEqual(fx['timezone'],'Europe/London');self.assertEqual(fx['close'],1356.34)
  self.assertLess(dt.datetime.fromtimestamp(fx['sourceRegularPeriod']['end'],dt.timezone.utc),dt.datetime.fromisoformat(fx['observedAt']))
 def test_official_standalone_quarters(self):
  s=json.loads((ROOT/'data/financial_backfill_zlatest_20261107_us_official.json').read_text());self.assertEqual(len(s['companies']),6)
  for sym,r in s['companies'].items():
   q=r['quarters'][0];self.assertEqual(q['reportedCurrency'],'USD');self.assertEqual(q['sourceType'],'filing');self.assertLessEqual(q['publishedAt'],q['verifiedAt']);self.assertTrue(q['sourceUrl'].startswith('https://'));self.assertIn('GAAP',q['basis']);self.assertEqual(q['revenue'],next(v for v in self.m['stocks'][sym]['quarters']if v['date']==q['date'])['revenue'])
  self.assertEqual(s['companies']['NASDAQ:ENTG']['quarters'][0]['date'],'2026-09-26');self.assertIn('잠정',s['companies']['NASDAQ:MKSI']['financialNote'])
 def test_reuse_and_distinct_dates_documented(self):
  self.assertEqual(sum(r['reused']for r in self.e['records']),67);self.assertEqual(self.e['count'],134);self.assertTrue(self.e['preservation']['allMarketCapValuesAndObservationDatesPreserved'])
