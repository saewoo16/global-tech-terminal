"""Session-boundary regression fixtures, never published market observations."""
import copy
import datetime as dt
import importlib.util
import pathlib
import unittest

PATH=pathlib.Path(__file__).resolve().parents[1]/'scripts/update_overseas_etf_charts.py'
spec=importlib.util.spec_from_file_location('etf_guards',PATH)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

def stamp(value):return dt.datetime.fromisoformat(value).timestamp()
def period(date, end='16:00'):
    return {'start':stamp(date+'T09:30:00-05:00'),'end':stamp(date+'T'+end+':00-05:00')}
def raw(date, end='16:00'):
    return {'meta':{'currentTradingPeriod':{'regular':period(date,end)}}}

class SessionGuards(unittest.TestCase):
    def test_early_close_excludes_1300_and_1305(self):
        data=raw('2026-11-27','13:00')
        data.update(timestamp=[stamp('2026-11-27T'+t+':00-05:00') for t in ['09:25','09:30','12:55','13:00','13:05']],
                    indicators={'quote':[{'close':[100]*5,'volume':[1]*5}]})
        points=m.intraday_points(data,dt.datetime.fromisoformat('2026-11-28T00:00:00+00:00'),'2026-11-27')
        self.assertEqual([p['time'][11:16] for p in points],['09:30','12:55'])

    def test_missing_wrong_date_or_conflicting_bounds_fail_closed(self):
        base={'timestamp':[stamp('2026-11-27T12:55:00-05:00')], 'indicators':{'quote':[{'close':[100]}]}}
        for meta in [{},raw('2026-11-30')['meta'],
                     {'currentTradingPeriod':{'regular':period('2026-11-27','13:00')},
                      'tradingPeriods':{'regular':[[period('2026-11-27')]]}}]:
            data=dict(base,meta=meta)
            self.assertEqual(m.intraday_points(data,dt.datetime.fromisoformat('2026-11-28T00:00:00+00:00'),'2026-11-27'),[])

    def test_historical_regular_periods_supported_without_prepost(self):
        data={'meta':{'tradingPeriods':{'regular':[[period('2026-11-27','13:00')]],
                                     'post':[[period('2026-11-27','20:00')]]}}}
        self.assertEqual(m.regular_session_periods(data),{'2026-11-27':tuple(period('2026-11-27','13:00').values())})

    def test_matching_stale_analysis_and_funds_cannot_claim_complete(self):
        funds=[{'code':'A','daily':[{'date':'2026-11-05','close':100}],
                'intraday':{'date':'2026-11-05','points':[]}}]
        before=copy.deepcopy(funds)
        result=m.apply_session_coverage(funds,['A'],'2026-11-05',dt.datetime.fromisoformat('2026-11-08T05:00:00+00:00'))
        self.assertEqual(result['status'],'partial')
        self.assertEqual(result['freshnessStatus'],'verified')
        self.assertEqual(result['latestCompletedSession'],'2026-11-06')
        self.assertEqual(funds[0]['daily'],before[0]['daily'])
        self.assertEqual(funds[0]['intraday'],before[0]['intraday'])

    def test_newly_observed_completed_session_is_independent_of_old_tails(self):
        now=dt.datetime.fromisoformat('2026-11-06T22:00:00+00:00')
        observation=m.session_observation(raw('2026-11-06'),now,'https://query1.finance.yahoo.com/')
        funds=[{'code':'A','daily':[{'date':'2026-11-05'}],'sessionObservation':observation}]
        result=m.apply_session_coverage(funds,['A'],'2026-11-05',now)
        self.assertEqual(result['targetSession'],'2026-11-06')
        self.assertEqual(result['staleCodes'],['A'])
        self.assertEqual(result['freshnessStatus'],'verified')
        funds[0]['daily'].append({'date':'2026-11-06'})
        self.assertEqual(m.apply_session_coverage(funds,['A'],'2026-11-05',now)['status'],'complete')
        # Sunday freshness comes independently from the reviewed exchange calendar.
        later=dt.datetime.fromisoformat('2026-11-08T05:00:00+00:00')
        self.assertEqual(m.apply_session_coverage(funds,['A'],'2026-11-05',later)['status'],'complete')

    def test_unreviewed_year_fails_closed_without_mutating_history(self):
        funds=[{'code':'A','daily':[{'date':'2027-11-05'}]}]
        result=m.apply_session_coverage(funds,['A'],'2027-11-05',dt.datetime.fromisoformat('2027-11-08T23:00:00+00:00'))
        self.assertEqual(result['status'],'unverified')
        self.assertIsNone(result['latestCompletedSession'])

    def test_open_early_close_session_and_weekend_are_not_inferred(self):
        for instant in ['2026-11-27T17:59:00+00:00','2026-11-28T22:00:00+00:00']:
            self.assertEqual(m.session_observation(raw('2026-11-27','13:00'),dt.datetime.fromisoformat(instant),'https://example.test')['status'],'unverified')
        now=dt.datetime.fromisoformat('2026-11-27T18:00:00+00:00')
        self.assertEqual(m.session_observation(raw('2026-11-27','13:00'),now,'https://example.test')['completedSession'],'2026-11-27')

if __name__=='__main__':unittest.main()
