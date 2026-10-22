import copy
from datetime import datetime
import json
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import kofia_official as k
from korean_session_gate import holiday_dates,is_completed_session
from validate_korean_market import validate

class OfficialLiquidity(unittest.TestCase):
    def setUp(self):
        self.html=(ROOT/'tests/fixtures/kofia-headlines-20261020.html').read_text()
        self.release=k.parse(self.html,'2026-10-21T17:15:17+09:00')
    def test_exact_totals(self):
        self.assertEqual(self.release['date'],'2026-10-20')
        self.assertEqual(self.release['officialInvestorDeposits'],90297588)
        self.assertEqual(self.release['officialMarginLoans'],30513862)
    def test_missing_stale_mismatch_rejected(self):
        for text,now in [(self.html.replace('백만원','억원'),'2026-10-21T17:00:00+09:00'),(self.html.replace('10/20','10/21',1),'2026-10-21T17:00:00+09:00'),(self.html,'2026-11-20T17:00:00+09:00'),(self.html,'2026-10-19T17:00:00+09:00')]:
            with self.assertRaises(ValueError):k.parse(text,now)
    def test_preserves_panels_splits_and_noop(self):
        old=json.loads((ROOT/'data/korea-market.json').read_text());original=copy.deepcopy(old)
        new=k.apply(old,self.release)
        self.assertEqual(old,original)
        for key in old.keys()-{'liquidity','sources'}:self.assertEqual(old[key],new[key])
        for key in ('creditKOSPI','creditKOSDAQ'):self.assertEqual(old['liquidity']['series'][key],new['liquidity']['series'][key])
        self.assertEqual(new['liquidity']['series']['deposits']['rows'][-1]['value'],902975.88)
        self.assertEqual(validate(new),[])
        later=dict(self.release,retrievedAt='2026-10-21T19:00:00+09:00')
        self.assertEqual(k.apply(new,later),new)
    def test_collector_transport_and_truncation(self):
        from email.message import Message
        from unittest.mock import patch
        class Response:
            status=200
            def __init__(self, data):
                self.data=data;self.headers=Message()
                self.headers['Content-Type']='text/html; charset=utf-8'
                self.headers['Content-Length']=str(len(data))
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read(self):return self.data
        html=('<html><body>'+self.html+'</body></html>').encode()
        with patch('kofia_official.urllib.request.urlopen',side_effect=[TimeoutError('timeout'),Response(html)]):
            release=k.collect('2026-10-21T17:15:17+09:00')
            self.assertEqual(release['transport'],'http')
            self.assertEqual(release['officialMarginLoans'],30513862)
            self.assertEqual(len(release['sourceSha256']),64)
        with patch('kofia_official.urllib.request.urlopen',side_effect=[Response(html[:-10]),Response(html[:-10])]):
            with self.assertRaises(ValueError):k.collect('2026-10-21T17:15:17+09:00')
    def test_no_rollback(self):
        p=json.loads((ROOT/'data/korea-market.json').read_text())
        p['liquidity']['validationSummary']['latestOfficialRelease']['date']='2026-10-21'
        with self.assertRaises(ValueError):k.apply(p,self.release)

class SessionGate(unittest.TestCase):
    def test_liquidity_window_does_not_advance_etf_gate(self):
        dates={'KOSPI':'2026-10-21','KOSDAQ':'2026-10-21'}
        now=datetime.fromisoformat('2026-10-21T15:40:00+09:00')
        self.assertTrue(is_completed_session(now,set(),dates,earliest=(15,30)))
        self.assertFalse(is_completed_session(now,set(),dates))
        self.assertFalse(is_completed_session(now,{'2026-10-21'},dates,earliest=(15,30)))
        self.assertFalse(is_completed_session(now,set(),dict(dates,KOSDAQ='2026-10-20'),earliest=(15,30)))
        source=(ROOT/'scripts/refresh_korean_scheduled.py').read_text()
        self.assertIn("earliest=(15,30) if args.kind == 'liquidity' else (17,30)",source)
    def test_actual_session_calendar(self):
        holidays=holiday_dates(json.loads((ROOT/'tests/fixtures/krx-holidays-2026.json').read_text()),2026)
        for day in ('2026-06-03','2026-07-17','2026-10-09'):self.assertIn(day,holidays)
        dates={'KOSPI':'2026-10-21','KOSDAQ':'2026-10-21'}
        self.assertTrue(is_completed_session(datetime.fromisoformat('2026-10-21T17:30:00+09:00'),holidays,dates))
        self.assertFalse(is_completed_session(datetime.fromisoformat('2026-10-21T15:00:00+09:00'),holidays,dates))
        self.assertFalse(is_completed_session(datetime.fromisoformat('2026-10-21T18:00:00+09:00'),holidays,dict(dates,KOSDAQ='2026-10-20')))
        self.assertFalse(is_completed_session(datetime.fromisoformat('2026-10-09T18:00:00+09:00'),holidays,{'KOSPI':'2026-10-09','KOSDAQ':'2026-10-09'}))
        with self.assertRaises(ValueError):holiday_dates({'block1':[]},2026)

if __name__=='__main__':unittest.main()

class WorkflowSafety(unittest.TestCase):
    def test_scope_and_no_new_permissions(self):
        workflow=(ROOT/'.github/workflows/korean-close-data.yml').read_text()
        self.assertIn('group: market-data-updates',workflow)
        self.assertIn('remote_head" != "$EXPECTED_HEAD',workflow)
        self.assertIn('git add data/korean_etf_charts.json data/korea-market.json',workflow)
        for forbidden in ('pages: write','id-token:', 'secrets.', '--force', 'pull --rebase'):
            self.assertNotIn(forbidden,workflow)
        generic=(ROOT/'.github/workflows/update.yml').read_text()
        self.assertIn("cron: '0 22 * * 1-5'",generic)
        self.assertNotIn('python scripts/update_korean_etf_charts.py',generic)
        self.assertNotIn('SKIP_KR_LIQUIDITY',generic)
        self.assertIn('OFFICIAL_KR_LIQUIDITY',generic)
        self.assertIn('contents: read',workflow)
        self.assertIn("if: github.event_name == 'push'",workflow)
        self.assertIn("cron: '0 9,10",workflow)
        self.assertIn("cron: '40 6-8 * * 1-5'",workflow)
    def test_timestamp_only_noop(self):
        from refresh_korean_scheduled import substantive
        self.assertEqual(substantive({'updatedAt':'a','funds':[{'metadataRetrievedAt':'a','representatives':{'marketCapObservedAt':'a','value':1}}]}),substantive({'updatedAt':'b','funds':[{'metadataRetrievedAt':'b','representatives':{'marketCapObservedAt':'b','value':1}}]}))

from update_korean_market import official_credit_splits

class CreditPolicy(unittest.TestCase):
    def fixture(self):
        return {'deposits':[{'date':'2026-10-20','value':1}],
                'creditKOSPI':[{'date':d,'value':200.0} for d in ('2026-10-19','2026-10-20','2026-10-21')],
                'creditKOSDAQ':[{'date':d,'value':100.0} for d in ('2026-10-19','2026-10-20','2026-10-21')]}
    def test_keeps_only_verified_dates_and_no_deposit(self):
        rows=official_credit_splits(self.fixture(),{'date':'2026-10-20','officialMarginLoans':30000})
        self.assertNotIn('deposits',rows)
        self.assertEqual([r['date'] for r in rows['creditKOSPI']],['2026-10-19','2026-10-20'])
    def test_mismatch_excludes_both(self):
        rows=official_credit_splits(self.fixture(),{'date':'2026-10-20','officialMarginLoans':30100})
        self.assertEqual([r['date'] for r in rows['creditKOSDAQ']],['2026-10-19'])
    def test_missing_market_not_inferred(self):
        data=self.fixture();data['creditKOSDAQ']=[]
        self.assertEqual(official_credit_splits(data,{'date':'2026-10-20','officialMarginLoans':30000}),{'creditKOSPI':[],'creditKOSDAQ':[]})
    def test_one_million_tolerance(self):
        rows=official_credit_splits(self.fixture(),{'date':'2026-10-20','officialMarginLoans':30001})
        self.assertEqual(rows['creditKOSPI'][-1]['date'],'2026-10-20')
    def test_missing_primary_total_fails(self):
        with self.assertRaises(ValueError):official_credit_splits(self.fixture(),{})
