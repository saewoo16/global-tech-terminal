import copy
import datetime as dt
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
with patch.dict(sys.modules, {'yfinance': types.ModuleType('yfinance')}):
    import update_data as u

class LatestDailyTests(unittest.TestCase):
    def result(self, value=172.24000549316406):
        return {'meta': {'exchangeTimezoneName':'Europe/Paris', 'currentTradingPeriod':{'regular':{'start':1792479600,'end':1792510200}}},'timestamp':[1792479600], 'indicators':{'adjclose':[{'adjclose':[value]}], 'quote':[{'close':[999]}]}}
    def test_coverage_distinguishes_age_from_verified_session(self):
        from audit_coverage import audit
        r=audit([{'symbol':'T:X','name':'X','country':'X'}],{'stocks':{'T:X':{'prices':[['2026-10-19',1]],'latestCompletedSession':'2026-10-20'}}})
        self.assertTrue(r['companies'][0]['behind_verified_session'])
        self.assertEqual(r['summary']['behind_verified_sessions'],1)
        self.assertIn('calendar',r['freshnessMethodology']['stalePrice'])

    def test_actual_adjusted_close_after_session(self):
        self.assertEqual(u.completed_daily_points(self.result(), dt.datetime(2026,10,20,18,tzinfo=dt.timezone.utc)), [['2026-10-20',172.24001]])
    def test_no_intraday_or_unadjusted_substitute(self):
        self.assertEqual(u.completed_daily_points(self.result(),dt.datetime(2026,10,20,10,tzinfo=dt.timezone.utc)), [])
        self.assertEqual(u.completed_daily_points(self.result(None)), [])
    def test_missing_session_metadata_rejected(self):
        r=self.result();del r['meta']['currentTradingPeriod']
        self.assertEqual(u.completed_daily_points(r), [])
    def test_prior_session_bar_accepted(self):
        r=self.result();r['meta']['currentTradingPeriod']['regular']={'start':1792566000,'end':1792596600}
        self.assertEqual(len(u.completed_daily_points(r,dt.datetime(2026,10,21,0,tzinfo=dt.timezone.utc))),1)
    def test_history_preserved_and_latest_appended(self):
        obj=types.SimpleNamespace(ticker='AI.PA',history=lambda **kwargs: None)
        with patch.object(u,'chart_fallback',return_value=([['2026-10-19',173.39999]],{})), patch.object(u,'latest_completed_daily',return_value=[['2026-10-20',172.24001]]):
            self.assertEqual(u.fetch_prices(obj),[['2026-10-19',173.39999],['2026-10-20',172.24001]])
    def test_failure_preserves_history(self):
        obj=types.SimpleNamespace(ticker='AI.PA',history=lambda **kwargs: None)
        with patch.object(u,'chart_fallback',return_value=([['2026-10-19',173.39999]],{})), patch.object(u,'latest_completed_daily',return_value=[]):
            self.assertEqual(u.fetch_prices(obj),[['2026-10-19',173.39999]])

if __name__=='__main__':unittest.main()
