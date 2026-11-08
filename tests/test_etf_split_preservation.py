"""Offline collector regressions; fixtures are captures, never live requests.

SOXX/ITA capture slices retain the actual mixed raw basis from Nov 5. New
sessions and the TEST fund below are explicitly synthetic test scenarios only.
"""
import copy
import datetime as dt
import importlib.util
import json
import pathlib
import tempfile
import unittest
from unittest.mock import patch

ROOT=pathlib.Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location('split_collector',ROOT/'scripts/update_overseas_etf_charts.py')
m=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(m)
FIXTURES=ROOT/'tests/fixtures/etf_split_preservation'
NOW=dt.datetime.fromisoformat('2026-11-06T22:00:00+00:00')
KEYS=('open','high','low','close','volume')


def stamp(date, time='09:30:00'):
    return int(dt.datetime.fromisoformat(date+'T'+time+'-05:00').timestamp())


class SplitPreservationTests(unittest.TestCase):
    def fixture(self, code='SOXX'):
        return json.loads((FIXTURES/(code+'.json')).read_text())

    def build(self, fixture, now=NOW):
        with patch.object(m,'fetch_chart',side_effect=[
            (fixture['dailyResponse'],fixture['dailyUrl']),
            (fixture['intradayResponse'],fixture['intradayUrl']),
        ]) as fetch:
            result=m.build_fund({'ticker':fixture['previous']['code'],'name':'Offline fixture'}, {}, now, fixture['previous'])
            self.assertEqual(fetch.call_count,2)
        return result

    def normalized(self, fixture):
        raw=fixture['dailyResponse'];quote=raw['indicators']['quote'][0]
        previous={bar['date']:bar for bar in fixture['previous']['daily']}
        for i,timestamp in enumerate(raw['timestamp']):
            date=dt.datetime.fromtimestamp(timestamp,m.NY).date().isoformat()
            for key in KEYS:quote[key][i]=previous[date][key]
        return fixture

    def append_session(self, fixture, date='2026-11-06', factor=1.01):
        # Deliberately constructed scenario, NOT a Nov 6 market observation.
        raw=fixture['dailyResponse'];last=fixture['previous']['daily'][-1]
        bar={'date':date,**{key:last[key]*factor for key in ('open','high','low','close')},'volume':123456}
        raw['timestamp'].append(stamp(date))
        for key in KEYS:raw['indicators']['quote'][0][key].append(bar[key])
        raw['meta']['currentTradingPeriod']={'regular':{'start':stamp(date),'end':stamp(date,'16:00:00')}}
        return bar

    def assert_rejected(self, fixture, reason):
        before=copy.deepcopy(fixture['previous'])
        with patch.object(m,'fetch_chart',return_value=(fixture['dailyResponse'],fixture['dailyUrl'])) as fetch:
            with self.assertRaisesRegex(ValueError,reason):
                m.build_fund({'ticker':fixture['dailyResponse']['meta']['symbol'],'name':'Offline fixture'}, {}, NOW, fixture['previous'])
            self.assertEqual(fetch.call_count,1)
        self.assertEqual(fixture['previous'],before)

    def ordinary(self, preserved=True):
        bars=[{'date':date,'open':price,'high':price+1,'low':price-1,'close':price,'volume':1000}
              for date,price in [('2026-11-04',100),('2026-11-05',101)]]
        url='https://example.test/chart/TEST'
        previous={'code':'TEST','currency':'USD','daily':bars,'metadataAsOf':'2026-11-05',
            'metadataRetrievedAt':'2026-11-05T22:00:00+00:00','dailySourceUrl':url,
            'dailyAdjustment':'Split-adjusted price-only OHLC; not dividend total returns.',
            'sourceUrls':[url],'sourceTitles':['Test observations'],
            'dailyHistoryPreservation':{'through':'2026-11-04','count':1,'sourceUrl':'https://example.test/snapshot',
                                       'sha256':'a'*64,'splitNormalized':False},
            'dailyBarSources':[{'date':'2026-11-05','sourceUrl':url,'observedAt':'2026-11-05T22:00:00+00:00'}]}
        if not preserved:previous.pop('dailyHistoryPreservation')
        raw={'meta':{'symbol':'TEST','currency':'USD','instrumentType':'ETF'},
             'timestamp':[stamp(bar['date']) for bar in bars],
             'indicators':{'quote':[{key:[bar[key] for bar in bars] for key in KEYS}]}}
        return {'previous':previous,'dailyResponse':raw,'dailyUrl':url,'intradayResponse':{},'intradayUrl':url+'/5m'}

    def test_captured_mixed_soxx_history_is_preserved_without_range_shrink(self):
        fixture=self.fixture();previous=copy.deepcopy(fixture['previous'])
        naive,_=m.period_returns(m.daily_bars(fixture['dailyResponse'],NOW))
        self.assertAlmostEqual(naive['day'],-70.71557185141169)
        fund=self.build(fixture)
        self.assertEqual(fund['daily'],previous['daily']);self.assertEqual(len(fund['daily']),254)
        self.assertEqual(fund['returns'],previous['returns'])
        self.assertAlmostEqual(fund['quoteChangePct'],-12.146715554235076)
        self.assertEqual(fund['returnAnchors'],previous['returnAnchors'])
        self.assertEqual(fund['dailyCoverage']['start'],'2025-11-03')
        self.assertEqual(fixture['previous'],previous)

    def test_captured_ita_without_yahoo_split_event_uses_official_preserved_basis(self):
        fixture=self.fixture('ITA')
        self.assertNotIn('splits',fixture['dailyResponse']['events'])
        naive,_=m.period_returns(m.daily_bars(fixture['dailyResponse'],NOW))
        self.assertAlmostEqual(naive['day'],-67.99943535883892)
        fund=self.build(fixture)
        self.assertEqual(fund['daily'],fixture['previous']['daily'])
        self.assertEqual(fund['returns'],fixture['previous']['returns'])
        self.assertAlmostEqual(fund['quoteChangePct'],-3.9983060765167666)

    def test_already_normalized_response_is_never_divided_again_or_total_returned(self):
        for code in ('SOXX','ITA'):
            with self.subTest(code=code):
                fixture=self.normalized(self.fixture(code))
                fixture['dailyResponse']['indicators']['adjclose']=[{'adjclose':[1]*len(fixture['dailyResponse']['timestamp'])}]
                fund=self.build(fixture)
                self.assertEqual(fund['daily'],fixture['previous']['daily'])
                self.assertEqual(fund['returns'],fixture['previous']['returns'])
                self.assertEqual(fund['dailyAdjustment'],fixture['previous']['dailyAdjustment'])

    def test_provenance_and_observation_times_survive_repeated_same_session_refresh(self):
        fixture=self.fixture();previous=copy.deepcopy(fixture['previous']);fund=self.build(fixture)
        for key in ('corporateActions','dailyHistoryPreservation','dailyBarSources','metadataRetrievedAt','dailyAdjustment'):
            self.assertEqual(fund[key],previous[key])
        self.assertEqual(fund['dailyHistoryRefresh']['checkedAt'],NOW.isoformat())
        self.assertEqual(fund['dailyHistoryRefresh']['status'],'preserved')
        self.assertEqual(fund['dailyHistoryRefresh']['appendedDates'],[])
        original_titles=dict(zip(previous['sourceUrls'],previous['sourceTitles']))
        current_titles=dict(zip(fund['sourceUrls'],fund['sourceTitles']))
        self.assertTrue(original_titles.items()<=current_titles.items())
        self.assertIn(previous['dailyHistoryPreservation']['sourceUrl'],fund['sourceUrls'])
        fixture['previous']=fund;again=self.build(fixture, NOW+dt.timedelta(minutes=5))
        self.assertEqual(again['metadataRetrievedAt'],previous['metadataRetrievedAt'])
        self.assertEqual(again['dailyBarSources'],previous['dailyBarSources'])
        self.assertEqual(again['sourceUrls'],fund['sourceUrls'])
        self.assertEqual(again['sourceTitles'],fund['sourceTitles'])

    def test_synthetic_new_completed_session_appends_with_its_own_provenance(self):
        for code in ('SOXX','ITA'):
            with self.subTest(code=code):
                fixture=self.fixture(code);old=copy.deepcopy(fixture['previous']);new=self.append_session(fixture)
                fund=self.build(fixture)
                self.assertEqual(fund['daily'],old['daily']+[new]);self.assertEqual(fund['quotePrice'],new['close'])
                self.assertAlmostEqual(fund['returns']['day'],1)
                self.assertEqual(fund['returnAnchors']['day'],'2026-11-05')
                self.assertEqual(fund['metadataRetrievedAt'],NOW.isoformat())
                self.assertEqual(fund['metadataAsOf'],'2026-11-06')
                self.assertEqual(fund['dailyHistoryPreservation'],old['dailyHistoryPreservation'])
                self.assertEqual(fund['corporateActions'],old['corporateActions'])
                self.assertEqual(fund['dailyBarSources'][:-1],old['dailyBarSources'])
                self.assertEqual(fund['dailyBarSources'][-1],{'date':'2026-11-06','sourceUrl':fixture['dailyUrl'],'observedAt':NOW.isoformat()})
                self.assertEqual(fund['dailyHistoryRefresh']['appendedDates'],['2026-11-06'])
                self.assertEqual(fund['dailyCoverage']['count'],255)
                fixture['previous']=fund;again=self.build(fixture,NOW+dt.timedelta(minutes=5))
                self.assertEqual(again['dailyBarSources'],fund['dailyBarSources'])
                self.assertEqual(again['metadataRetrievedAt'],NOW.isoformat())

    def test_open_new_session_is_not_appended_or_redated(self):
        fixture=self.fixture();self.append_session(fixture)
        fund=self.build(fixture,dt.datetime.fromisoformat('2026-11-06T15:00:00+00:00'))
        self.assertEqual(fund['daily'],fixture['previous']['daily'])
        self.assertEqual(fund['metadataRetrievedAt'],fixture['previous']['metadataRetrievedAt'])

    def test_new_splits_and_known_event_ratio_conflicts_fail_closed(self):
        fixture=self.fixture();fixture['dailyResponse']['events']['splits']['later']={
            'date':stamp('2026-11-06'),'numerator':2,'denominator':1}
        self.assert_rejected(fixture,'unsupported further split')
        fixture=self.fixture();next(iter(fixture['dailyResponse']['events']['splits'].values()))['numerator']=2
        self.assert_rejected(fixture,'conflicting source split ratio')

    def test_unsupported_history_and_internally_mixed_ohlc_fail_closed(self):
        fixture=self.fixture()
        # Still ordered/positive OHLC, but fields now disagree on split basis.
        for key in ('open','low'):fixture['dailyResponse']['indicators']['quote'][0][key][-2]/=3
        self.assert_rejected(fixture,'basis conflict')
        fixture=self.fixture()
        for key in ('open','high','low','close'):fixture['dailyResponse']['indicators']['quote'][0][key][-1]/=2
        self.assert_rejected(fixture,'basis conflict')

    def test_unannounced_new_session_discontinuity_is_not_guessed(self):
        fixture=self.fixture();self.append_session(fixture,factor=.5)
        self.assert_rejected(fixture,'new-session price/basis discontinuity')

    def test_append_requires_valid_latest_prior_basis_overlap(self):
        fixture=self.fixture();self.append_session(fixture)
        raw=fixture['dailyResponse'];i=-2
        raw['indicators']['quote'][0]['high'][i]=raw['indicators']['quote'][0]['low'][i]
        self.assert_rejected(fixture,'latest preserved session absent')
        fixture=self.fixture();new=self.append_session(fixture);raw=fixture['dailyResponse']
        raw['timestamp']=[raw['timestamp'][-1]]
        raw['indicators']['quote']=[{key:[new[key]] for key in KEYS}]
        self.assert_rejected(fixture,'no valid overlapping')

    def test_missing_or_bad_current_raw_candle_keeps_whole_original_candle(self):
        fixture=self.fixture();raw=fixture['dailyResponse']
        raw['indicators']['quote'][0]['high'][-1]=raw['indicators']['quote'][0]['low'][-1]
        fund=self.build(fixture)
        self.assertEqual(fund['daily'],fixture['previous']['daily'])
        self.assertEqual(fund['dailyBarSources'],fixture['previous']['dailyBarSources'])

    def test_no_append_does_not_clear_unresolved_prior_refresh_error(self):
        fixture=self.fixture();fixture['previous'].update(refreshStatus='stale',refreshError='Next completed session not verified')
        fund=self.build(fixture)
        self.assertEqual(fund['refreshStatus'],'stale')
        self.assertEqual(fund['refreshError'],fixture['previous']['refreshError'])

    def test_source_symbol_must_identify_the_requested_fund(self):
        for symbol in ('ITA',None):
            with self.subTest(symbol=symbol):
                fixture=self.fixture();fixture['dailyResponse']['meta']['symbol']=symbol
                with patch.object(m,'fetch_chart',return_value=(fixture['dailyResponse'],fixture['dailyUrl'])):
                    with self.assertRaisesRegex(ValueError,'symbol'):
                        m.build_fund({'ticker':'SOXX','name':'Offline fixture'}, {}, NOW,fixture['previous'])

    def test_malformed_or_mismatched_provenance_cannot_silently_remove_protection(self):
        mutations={
            'missing_history':lambda p:p.pop('dailyHistoryPreservation'),
            'missing_action':lambda p:p.pop('corporateActions'),
            'false_normalized':lambda p:p['dailyHistoryPreservation'].update(splitNormalized=False),
            'bad_count':lambda p:p['dailyHistoryPreservation'].update(count=252),
            'bad_through':lambda p:p['dailyHistoryPreservation'].update(through='2026-11-03'),
            'bad_hash':lambda p:p['dailyHistoryPreservation'].update(sha256='f'*64),
            'bad_action_ratio':lambda p:p['corporateActions'][0].update(numerator=0),
            'bool_action_ratio':lambda p:p['corporateActions'][0].update(numerator=True),
            'bad_adjusted_through':lambda p:p['corporateActions'][0].update(adjustedThrough='2026-11-03'),
            'bad_volume_factor':lambda p:p['corporateActions'][0].update(volumeMultiplier=1),
            'bad_snapshot':lambda p:p['corporateActions'][0].update(sourceSnapshotUrl='https://example.test/wrong'),
            'multiple_actions':lambda p:p['corporateActions'].append(copy.deepcopy(p['corporateActions'][0])),
            'bad_code':lambda p:p.update(code='ITA'),
            'bad_currency':lambda p:p.update(currency='EUR'),
            'bad_tail_date':lambda p:p.update(metadataAsOf='2026-11-04'),
            'naive_observed_at':lambda p:p.update(metadataRetrievedAt='2026-11-05T21:42:00'),
            'bad_titles':lambda p:p['sourceTitles'].pop(),
            'missing_new_bar_source':lambda p:p.update(dailyBarSources=[]),
            'duplicate_source':lambda p:p['dailyBarSources'].append(copy.deepcopy(p['dailyBarSources'][0])),
            'unknown_source_date':lambda p:p['dailyBarSources'][0].update(date='2026-11-06'),
            'future_source_time':lambda p:p['dailyBarSources'][0].update(observedAt='2099-11-05T22:00:00+00:00'),
            'missing_source_time':lambda p:p['dailyBarSources'][0].pop('observedAt'),
            'bad_source_url':lambda p:p['dailyBarSources'][0].update(sourceUrl='not a URL'),
            'malformed_source':lambda p:p.update(dailyBarSources=[None]),
            'duplicate_candle':lambda p:p['daily'].append(copy.deepcopy(p['daily'][-1])),
            'invalid_candle':lambda p:p['daily'][0].update(close=-1),
        }
        for label,mutate in mutations.items():
            with self.subTest(label=label):
                fixture=self.fixture();mutate(fixture['previous'])
                self.assert_rejected(fixture,'Preserved daily history:')

    def test_invalid_new_completed_source_session_never_silently_disappears(self):
        for invalid in (None, True, -1, float('nan')):
            with self.subTest(invalid=invalid):
                fixture=self.fixture();self.append_session(fixture)
                fixture['dailyResponse']['indicators']['quote'][0]['close'][-1]=invalid
                self.assert_rejected(fixture,'invalid or missing new completed candle')
        # Synthetic two-session scenario: do not skip a broken earlier new
        # candle even when a later valid candle could otherwise be appended.
        fixture=self.fixture();self.append_session(fixture,date='2026-11-06')
        self.append_session(fixture,date='2026-11-09')
        fixture['dailyResponse']['indicators']['quote'][0]['close'][-2]=None
        with patch.object(m,'fetch_chart',return_value=(fixture['dailyResponse'],fixture['dailyUrl'])):
            with self.assertRaisesRegex(ValueError,'invalid or missing new completed candle on 2026-11-06'):
                m.build_fund({'ticker':'SOXX','name':'Synthetic test'}, {},
                             dt.datetime.fromisoformat('2026-11-09T22:00:00+00:00'),fixture['previous'])

    def test_new_session_requires_its_own_valid_regular_close_metadata(self):
        for regular in ({}, {'start':stamp('2026-11-05'),'end':stamp('2026-11-05','16:00:00')},
                        {'start':stamp('2026-11-06'),'end':True},
                        {'start':stamp('2026-11-06','16:00:00'),'end':stamp('2026-11-06')}):
            with self.subTest(regular=regular):
                fixture=self.fixture();self.append_session(fixture)
                fixture['dailyResponse']['meta']['currentTradingPeriod']['regular']=regular
                self.assert_rejected(fixture,'invalid new-session regular trading period')
        # A provider's premature 13:00 close on a normal 16:00 session must
        # fail both direct daily filtering and the protected append path.
        fixture=self.fixture();self.append_session(fixture)
        fixture['dailyResponse']['meta']['currentTradingPeriod']['regular']['end']=stamp('2026-11-06','13:00:00')
        now=dt.datetime.fromisoformat('2026-11-06T19:00:00+00:00')
        self.assertNotIn('2026-11-06',[b['date'] for b in m.daily_bars(fixture['dailyResponse'],now)])
        before=copy.deepcopy(fixture['previous'])
        with self.assertRaisesRegex(ValueError,'invalid new-session regular trading period'):
            self.build(fixture,now)
        self.assertEqual(fixture['previous'],before)
        # A real calendar early close, using synthetic prices only.
        fixture=self.fixture();new=self.append_session(fixture,date='2026-11-27')
        fixture['dailyResponse']['meta']['currentTradingPeriod']['regular']['end']=stamp('2026-11-27','13:00:00')
        self.assertEqual(self.build(fixture,dt.datetime.fromisoformat('2026-11-27T19:00:00+00:00'))['daily'][-1],new)
        before_close=self.build(fixture,dt.datetime.fromisoformat('2026-11-27T17:59:00+00:00'))
        self.assertEqual(before_close['daily'],fixture['previous']['daily'])

    def test_source_timezone_interval_and_duplicate_sessions_fail_closed(self):
        for key,value in (('exchangeTimezoneName','Asia/Seoul'),('dataGranularity','5m')):
            with self.subTest(key=key):
                fixture=self.fixture();fixture['dailyResponse']['meta'][key]=value
                self.assert_rejected(fixture,'invalid source instrument/currency/timezone/interval')
        fixture=self.fixture();raw=fixture['dailyResponse'];raw['timestamp'].append(raw['timestamp'][-1])
        for key in KEYS:raw['indicators']['quote'][0][key].append(raw['indicators']['quote'][0][key][-1])
        self.assert_rejected(fixture,'duplicate source sessions')

    def test_malformed_source_split_metadata_fails_closed(self):
        for events in (None, {'splits':[]}, {'splits':{'bad':None}},
                       {'splits':{'bad':{'date':True,'numerator':3,'denominator':1}}},
                       {'splits':{'bad':{'date':stamp('2026-11-05'),'numerator':1,'denominator':1}}}):
            with self.subTest(events=events):
                fixture=self.fixture();fixture['dailyResponse']['events']=events
                self.assert_rejected(fixture,'Preserved daily history:')

    def test_refresh_marker_prevents_accidental_removal_of_history_protection(self):
        fixture=self.ordinary();fixture['previous']=self.build(fixture)
        fixture['previous'].pop('dailyHistoryPreservation')
        self.assert_rejected(fixture,'missing history provenance')

    def test_all_current_funds_preserve_history_and_append_synthetic_session(self):
        # Actual committed prior history; all NEW next-session candles here are
        # synthetic compatibility tests, never captured or published prices.
        snapshot=json.loads((ROOT/'data/overseas_etf_charts.json').read_text())
        self.assertGreaterEqual(len(snapshot['funds']),38)
        for previous in snapshot['funds']:
            with self.subTest(code=previous['code']):
                raw={'meta':{'symbol':previous['code'],'currency':'USD','instrumentType':'ETF'},
                     'timestamp':[stamp(b['date']) for b in previous['daily']],
                     'indicators':{'quote':[{key:[b.get(key) for b in previous['daily']] for key in KEYS}]}}
                fixture={'previous':copy.deepcopy(previous),'dailyResponse':raw,'dailyUrl':previous['dailySourceUrl'],
                         'intradayResponse':{},'intradayUrl':previous['dailySourceUrl']}
                next_date=dt.date.fromisoformat(previous['daily'][-1]['date'])+dt.timedelta(days=1)
                while next_date.weekday()>=5:next_date+=dt.timedelta(days=1)
                new=self.append_session(fixture,date=next_date.isoformat())
                now=max(dt.datetime.combine(next_date,dt.time(22),dt.timezone.utc),
                        dt.datetime.fromisoformat(previous['metadataRetrievedAt'])+dt.timedelta(days=1))
                result=self.build(fixture,now)
                self.assertEqual(result['daily'],previous['daily']+[new])
                for key in ('dailyHistoryPreservation','corporateActions','dailyAdjustment'):
                    self.assertEqual(result.get(key),previous.get(key))
                self.assertEqual(result['dailyBarSources'][:-1],previous['dailyBarSources'])
                self.assertEqual(result['dailyCoverage']['count'],len(previous['daily'])+1)

    def test_ordinary_marked_history_preserves_history_and_advances(self):
        fixture=self.ordinary();old=copy.deepcopy(fixture['previous'])
        # A small source revision is a basis match, not permission to overwrite.
        fixture['dailyResponse']['indicators']['quote'][0]['close'][0]=100.2
        new=self.append_session(fixture)
        fund=self.build(fixture)
        self.assertEqual(fund['daily'],old['daily']+[new])
        self.assertEqual(fund['dailyHistoryPreservation'],old['dailyHistoryPreservation'])
        self.assertNotIn('corporateActions',fund)

    def test_ordinary_unmarked_history_retains_existing_fresh_candle_behavior(self):
        fixture=self.ordinary(preserved=False)
        fixture['dailyResponse']['indicators']['quote'][0]['close'][0]=100.2
        new=self.append_session(fixture)
        fund=self.build(fixture)
        self.assertEqual(fund['daily'][0]['close'],100.2)
        self.assertEqual(fund['daily'][-1],new)
        self.assertNotIn('dailyHistoryPreservation',fund)

    def test_old_already_reflected_split_event_does_not_block_ordinary_history(self):
        fixture=self.ordinary();fixture['dailyResponse']['events']={'splits':{
            'old':{'date':stamp('2026-11-04'),'numerator':2,'denominator':1}}}
        new=self.append_session(fixture)
        self.assertEqual(self.build(fixture)['daily'][-1],new)

    def test_main_retains_whole_fund_stale_on_basis_conflict_while_other_fund_advances(self):
        fixture=self.fixture();ordinary=self.ordinary(preserved=False)
        for key in ('open','high','low','close'):fixture['dailyResponse']['indicators']['quote'][0][key][-1]/=2
        new=self.append_session(ordinary)
        class FrozenDatetime(dt.datetime):
            @classmethod
            def now(cls,tz=None):return NOW if tz else NOW.replace(tzinfo=None)
        def fetch(code,interval,period):
            value=fixture if code=='SOXX' else ordinary
            return (value['dailyResponse'],value['dailyUrl']) if interval=='1d' else (value['intradayResponse'],value['intradayUrl'])
        with tempfile.TemporaryDirectory() as directory:
            dest=pathlib.Path(directory)/'charts.json';analysis=pathlib.Path(directory)/'analysis.json'
            dest.write_text(json.dumps({'funds':[fixture['previous']]}))
            analysis.write_text(json.dumps({'entries':[{'date':'2026-11-06','sectors':{'rows':[
                {'ticker':code,'name':code,'instrumentType':'etf'} for code in ('SOXX','TEST')]}}]}))
            with patch.object(m,'fetch_chart',side_effect=fetch),patch.object(m.dt,'datetime',FrozenDatetime),patch('builtins.print'),patch('sys.argv',[
                'collector','--output',str(dest),'--analysis',str(analysis)]):m.main()
            result=json.loads(dest.read_text());funds={f['code']:f for f in result['funds']}
        old=funds['SOXX'];self.assertEqual(old['refreshStatus'],'stale');self.assertIn('basis conflict',old['refreshError'])
        for key in ('daily','dailyBarSources','dailyHistoryPreservation','corporateActions','returns','metadataRetrievedAt'):
            self.assertEqual(old[key],fixture['previous'][key])
        self.assertEqual(funds['TEST']['daily'][-1],new)
        self.assertEqual(result['errors'][0]['code'],'SOXX')
        self.assertEqual(result['coverage']['staleCodes'],['SOXX'])


if __name__=='__main__':unittest.main()
