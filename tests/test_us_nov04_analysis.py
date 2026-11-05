"""Source and preservation checks for the November 4 completed US session."""
import json, math, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class November4Analysis(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.payload=json.loads((ROOT/'data/us_analysis.json').read_text());cls.entry=next(e for e in cls.payload['entries'] if e['date']=='2026-11-04');cls.ev=json.loads((ROOT/'data/us-close-evidence-20261104.json').read_text());cls.audit=json.loads((ROOT/'data/overseas-etf-audit-20261104.json').read_text())
 def test_actual_session_and_membership_change(self):
  e=self.entry;self.assertEqual(e['sessionVerification']['closedAt'],'2026-11-04T16:00:00-05:00');self.assertEqual(e['sessionVerification']['previousSession'],'2026-11-03');members={r['ticker'] for r in e['constituents']};self.assertEqual(len(members),503);self.assertIn('OKTA',members);self.assertNotIn('KVUE',members);self.assertEqual(len({r['cik'] for r in e['constituents']}),500)
 def test_full_breadth_and_actual_highs(self):
  e=self.entry;rows=self.ev['screens']['dailyRows'];self.assertEqual(len(rows),503);self.assertEqual(e['breadth']['counts'],{'advancing':376,'declining':127,'unchanged':0});self.assertEqual(sum(r['newHigh'] for r in rows),65);self.assertEqual(sum(r['nearHigh'] for r in rows),42);self.assertEqual(e['coverage']['shortHistoryTickers'],['FDXF','HONA','VYLR'])
 def test_current_ohlc_repairs_are_complete_and_volume_excluded(self):
  rows={r['ticker']:r for r in self.ev['screens']['dailyRows']};repairs=self.ev['screens']['currentSessionBarRepairs'];self.assertEqual(len(repairs),25)
  for r in repairs:
   b=r['replacementTradingViewBar'];self.assertLessEqual(b['low'],min(b['open'],b['close']));self.assertGreaterEqual(b['high'],max(b['open'],b['close']));self.assertIsNone(rows[r['ticker']]['volumeRatio']);self.assertFalse(rows[r['ticker']]['volumeComparisonVerified'])
 def test_unusual_filters_reproduce(self):
  expected={r['ticker'] for r in self.ev['screens']['dailyRows'] if r['volumeComparisonVerified'] and abs(r['changePct'])>=5 and r['volumeRatio']>=2};self.assertEqual(expected,{r['ticker'] for r in self.entry['unusualMovers']['rows']});self.assertEqual(self.entry['unusualMovers']['coverage']['volumeValid'],478)
 def test_sector_comparisons_and_holdings_keep_actual_dates(self):
  for r in self.entry['sectors']['rows']:
   c=r['calculation'];self.assertEqual(c['asOf'],'2026-11-04');self.assertEqual(c['anchors'],{'day':'2026-11-03','week':'2026-10-28','month':'2026-10-02'})
   for k,d in c['anchors'].items():
    returns=[(v['bars']['2026-11-04']['adjustedClose']/v['bars'][d]['adjustedClose']-1)*100 for v in c['components']];self.assertAlmostEqual(r[k],round(sum(returns)/len(returns),2),places=8)
   if r.get('instrumentType')=='etf':
    h=r['holdings'];self.assertEqual(h['asOf'],'2026-11-04' if r['ticker']=='BATT' else '2026-11-03');self.assertEqual(len(h['top5']),5);self.assertEqual([v['weightPct'] for v in h['top5']],sorted([v['weightPct'] for v in h['top5']],reverse=True))
 def test_etf_actual_daily_and_intraday_coverage(self):
  # These counts describe the immutable 11/4 audit, not the rolling live file.
  # Later valid intraday observations and daily sessions must be able to advance.
  audit=self.audit;self.assertEqual(audit['asOf'],'2026-11-04');self.assertEqual(len(audit['rows']),38);self.assertEqual(audit['coverage']['currentFundCount'],38);self.assertEqual(audit['coverage']['intradayCurrentFundCount'],28)
  self.assertEqual(len({r['ticker'] for r in audit['rows']}),38)
  self.assertEqual(sum(r['intradayDate']=='2026-11-04' and r['intradayCount']>=2 for r in audit['rows']),28)
  for row in audit['rows']:
   self.assertEqual(row['actualLastSession'],'2026-11-04');self.assertEqual(row['dailyCount'],253);self.assertIn(row['intradayDate'],['2026-11-03','2026-11-04']);self.assertTrue(row['sourceUrl']);self.assertTrue(row['rawSha256'])
   for bar in [row['lastOHLCV'],*row['comparisonBars'].values()]:
    self.assertTrue(all(math.isfinite(bar[k]) and bar[k]>0 for k in ('open','high','low','close')));self.assertTrue(bar['low']<=min(bar['open'],bar['close'])<=max(bar['open'],bar['close'])<=bar['high'])
 def test_live_etf_sessions_cannot_regress_below_verified_audit(self):
  live=json.loads((ROOT/'data/overseas_etf_charts.json').read_text());funds={f['code']:f for f in live['funds']}
  for row in self.audit['rows']:
   self.assertIn(row['ticker'],funds)
   fund=funds[row['ticker']]
   self.assertGreaterEqual(fund['daily'][-1]['date'],row['actualLastSession'])
   # All audited funds already have a full year of history. Preserve the
   # collector's established long-history threshold, not a frozen bar count.
   self.assertGreaterEqual(len(fund['daily']),200)
   self.assertGreaterEqual(fund['dailyCoverage']['requestedMonths'],12)
   self.assertFalse(fund['dailyCoverage']['shortHistory'])
 def test_regular_move_not_attributed_to_after_close(self):
  app=next(r for r in self.entry['movers']['gainers'] if r['ticker']=='APP');self.assertFalse(app['reasonVerified']);self.assertIn('장후',app['reason'])
if __name__=='__main__':unittest.main()
