"""The close-only production path never needs a minute feed."""
import datetime as dt
import unittest
from unittest.mock import patch
from scripts import update_korean_etf_charts as kr
from scripts import update_overseas_etf_charts as us

class DailyOnlyRefresh(unittest.TestCase):
    def test_kr_minute_route_is_not_called_and_prior_metadata_is_not_redated(self):
        xml=b'<protocol><chartdata><item data="20261119|101|105|99|104|33"/><item data="20261120|104|105|97|98|30"/></chartdata></protocol>'
        previous={'intraday':{'date':'2026-11-19','points':[{'price':104}]},'metadataAsOf':'2026-11-19','quotePrice':104}
        with patch.object(kr,'fetch',return_value=xml) as read:
            got=kr.build_fund(('091160','test','industry'),{'091160':{'itemname':'Test','nowVal':999}},dt.date(2026,11,20),previous=previous,daily_only=True)
        self.assertEqual(read.call_count,1)
        self.assertIn('timeframe=day',read.call_args.args[0])
        self.assertEqual(got['daily'][-1]['date'],'2026-11-20')
        self.assertEqual(got['intraday'],previous['intraday'])
        self.assertEqual((got['metadataAsOf'],got['quotePrice']),('2026-11-19',104))

    def test_us_minute_route_is_not_called_and_prior_observations_survive(self):
        raw={'meta':{'instrumentType':'ETF','currency':'USD','symbol':'TEST'}}
        bars=[{'date':day,'open':98,'high':106,'low':94,'close':close,'volume':30}
              for day,close in [('2026-11-18',100),('2026-11-19',98)]]
        previous={'intraday':{'date':'2026-11-18','points':[{'price':100}],'sourceUrl':'https://example.com/old'}}
        with patch.object(us,'fetch_chart',return_value=(raw,'https://example.com/daily')) as read, patch.object(us,'daily_bars',return_value=bars), patch.object(us,'session_observation',return_value=None):
            got=us.build_fund({'ticker':'TEST','name':'Test'}, {}, dt.datetime(2026,11,20,tzinfo=dt.timezone.utc), previous, daily_only=True)
        read.assert_called_once_with('TEST','1d','1y')
        self.assertEqual(got['daily'][-1]['date'],'2026-11-19')
        self.assertEqual(got['intraday'],previous['intraday'])
        self.assertAlmostEqual(got['returns']['day'],-2)
