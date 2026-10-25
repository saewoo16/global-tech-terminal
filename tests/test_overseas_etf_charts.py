import datetime as dt
import importlib.util
import json
import math
import pathlib
import unittest
from unittest.mock import patch

PATH=pathlib.Path(__file__).resolve().parents[1]/'scripts/update_overseas_etf_charts.py'
spec=importlib.util.spec_from_file_location('overseas',PATH);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class OverseasETFTests(unittest.TestCase):
    def test_returns_have_actual_calendar_and_session_anchors(self):
        bars=[{'date':d,'close':p} for d,p in [('2026-09-23',100),('2026-10-16',102),('2026-10-19',103),('2026-10-20',104),('2026-10-21',105),('2026-10-22',106),('2026-10-23',107)]]
        values,anchors=m.period_returns(bars)
        self.assertEqual(anchors,{'day':'2026-10-22','week':'2026-10-16','month':'2026-09-23'})
        self.assertAlmostEqual(values['month'],7);self.assertAlmostEqual(values['week'],(107/102-1)*100)
    def test_calendar_month_clamps_day_and_missing_returns_are_null(self):
        values,anchors=m.period_returns([{'date':'2026-02-27','close':100},{'date':'2026-03-31','close':110}])
        self.assertAlmostEqual(values['month'],10);self.assertEqual(anchors['month'],'2026-02-27');self.assertAlmostEqual(values['week'],10)
        self.assertEqual(m.period_returns([])[0],{'day':None,'week':None,'month':None})
    def test_week_uses_calendar_anchor_across_holiday(self):
        bars=[{'date':date,'close':price} for date,price in [('2026-10-09',100),('2026-10-13',110),('2026-10-14',111),('2026-10-15',112),('2026-10-16',113),('2026-10-19',114)]]
        values,anchors=m.period_returns(bars)
        self.assertEqual(anchors['week'],'2026-10-09')
        self.assertAlmostEqual(values['week'],14)
    def test_prior_same_session_intraday_survives_failure(self):
        stamps=[int(dt.datetime.fromisoformat(t).timestamp()) for t in ['2026-10-22T09:30:00-04:00','2026-10-23T09:30:00-04:00']]
        raw={'timestamp':stamps,'meta':{'instrumentType':'ETF','currency':'USD','fullExchangeName':'NYSEArca'},'indicators':{'quote':[{'open':[100,101],'high':[102,103],'low':[99,100],'close':[101,102],'volume':[1,2]}]}}
        old={'intraday':{'date':'2026-10-23','asOf':'2026-10-23T15:55:00-04:00','status':'verified','points':[{'time':'2026-10-23T09:30:00-04:00','price':100},{'time':'2026-10-23T15:55:00-04:00','price':102}]}}
        with patch.object(m,'fetch_chart',side_effect=[(raw,'https://example.test/daily'),RuntimeError('source unavailable')]):
            fund=m.build_fund({'ticker':'TEST','name':'Test'}, {}, dt.datetime(2026,10,25,tzinfo=dt.timezone.utc),old)
        self.assertEqual(fund['intraday']['points'],old['intraday']['points'])
        self.assertEqual(fund['intraday']['asOf'],old['intraday']['asOf'])
        self.assertEqual(fund['intraday']['refreshStatus'],'stale')

    def test_issuer_full_brand(self):
        self.assertEqual(m.issuer_name('First Trust NASDAQ Cybersecurity ETF'),'First Trust')
        self.assertEqual(m.issuer_name('State Street Energy ETF'),'State Street')
        self.assertEqual(m.issuer_name('Global X Cloud Computing ETF'),'Global X')

    def test_intraday_filters_extended_hours_and_other_dates(self):
        times=['2026-10-23T09:25:00-04:00','2026-10-23T09:30:00-04:00','2026-10-23T15:55:00-04:00','2026-10-23T16:00:00-04:00','2026-10-22T12:00:00-04:00']
        raw={'timestamp':[int(dt.datetime.fromisoformat(t).timestamp()) for t in times],'indicators':{'quote':[{'close':[100]*5,'volume':[20]*5}]}}
        points=m.intraday_points(raw,dt.datetime(2026,10,25,tzinfo=dt.timezone.utc),'2026-10-23')
        self.assertEqual(len(points),2);self.assertIn('09:30',points[0]['time']);self.assertEqual(points[0]['volume'],20)
    def test_daily_rejects_invalid_and_unfinished_bars(self):
        stamps=[int(dt.datetime.fromisoformat(t).timestamp()) for t in ['2026-10-22T09:30:00-04:00','2026-10-23T09:30:00-04:00']]
        raw={'timestamp':stamps,'meta':{'currentTradingPeriod':{'regular':{'end':int(dt.datetime.fromisoformat('2026-10-23T16:00:00-04:00').timestamp())}}},'indicators':{'quote':[{'open':[100,101],'high':[102,103],'low':[99,100],'close':[101,102],'volume':[1,2]}]}}
        before=dt.datetime.fromisoformat('2026-10-23T12:00:00-04:00');after=dt.datetime.fromisoformat('2026-10-23T16:01:00-04:00')
        self.assertEqual(len(m.daily_bars(raw,before)),1);self.assertEqual(len(m.daily_bars(raw,after)),2)
        raw['indicators']['quote'][0]['close'][0]=float('nan');self.assertEqual(len(m.daily_bars(raw,before)),0)
class OverseasETFSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.payload=json.loads((PATH.parents[1]/'data/overseas_etf_charts.json').read_text())
    def test_snapshot_actual_etfs_and_finite_prices(self):
        self.assertEqual(self.payload['timezone'],'America/New_York')
        self.assertEqual(self.payload['currency'],'USD')
        funds=self.payload['funds']
        self.assertGreaterEqual(len(funds),38)
        self.assertEqual(len({f['code'] for f in funds}),len(funds))
        for fund in funds:
            self.assertNotIn(',',fund['code'])
            self.assertIn(fund['group'],('industry','theme'))
            daily=fund['daily'];self.assertGreaterEqual(len(daily),2)
            self.assertEqual([d['date'] for d in daily],sorted(set(d['date'] for d in daily)))
            for bar in daily:
                self.assertTrue(all(math.isfinite(bar[k]) and bar[k]>0 for k in ('open','high','low','close')))
                self.assertLessEqual(bar['low'],min(bar['open'],bar['close']))
                self.assertGreaterEqual(bar['high'],max(bar['open'],bar['close']))
    def test_snapshot_returns_and_intraday_dates_match(self):
        for fund in self.payload['funds']:
            values,anchors=m.period_returns(fund['daily'])
            self.assertEqual(values,fund['returns']);self.assertEqual(anchors,fund['returnAnchors'])
            for point in fund['intraday']['points']:
                self.assertEqual(point['time'][:10],fund['intraday']['date'])
                self.assertTrue(math.isfinite(point['price']) and point['price']>0)
                self.assertTrue('09:30'<=point['time'][11:16]<'16:00')
            if fund.get('holdings'):
                self.assertLessEqual(fund['holdings']['asOf'],fund['metadataRetrievedAt'][:10])

if __name__=='__main__':unittest.main()
