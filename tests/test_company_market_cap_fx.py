import copy
import datetime as dt
import io
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import unquote, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import update_data as updater


UTC = dt.timezone.utc
# The provider dates these London (BST) bars one calendar day ahead of their UTC dates.
SESSION_START = dt.datetime(2026, 10, 20, 23, tzinfo=UTC)
SESSION_END = SESSION_START + dt.timedelta(hours=23, minutes=59)
BEFORE_CLOSE = SESSION_START + dt.timedelta(hours=20)
AFTER_CLOSE = SESSION_END + dt.timedelta(seconds=1)
PREVIOUS_BAR = SESSION_START - dt.timedelta(days=1)


def chart(symbol='EURUSD=X', currency='USD', values=(1.084567891234, 1.09987654321)):
    return {
        'meta': {
            'symbol': symbol, 'currency': currency, 'instrumentType': 'CURRENCY',
            'dataGranularity': '1d', 'exchangeTimezoneName': 'Europe/London',
            'currentTradingPeriod': {'regular': {'start': int(SESSION_START.timestamp()),
                                                 'end': int(SESSION_END.timestamp())}},
            'regularMarketPrice': 555,
        },
        'timestamp': [int(PREVIOUS_BAR.timestamp()), int(SESSION_START.timestamp())],
        'indicators': {'adjclose': [{'adjclose': list(values)}], 'quote': [{'close': [555, 666]}]},
    }


def chart_response(request, timeout, *, charts):
    ticker = unquote(urlsplit(request.full_url).path.rsplit('/', 1)[-1])
    result = [charts[ticker]] if ticker in charts else None
    return io.BytesIO(json.dumps({'chart': {'result': result}}).encode())


class CompanyMarketCapFXTest(unittest.TestCase):
    def test_direct_rate_from_latest_completed_bar_is_not_rounded(self):
        with patch.object(updater, 'urlopen', side_effect=lambda *a, **kw: chart_response(
                *a, **kw, charts={'EURUSD=X': chart()})) as open_url:
            rate, evidence = updater.completed_market_cap_fx('EUR', BEFORE_CLOSE)
            open_url.assert_called_once()
        self.assertEqual(rate, 1.084567891234)
        self.assertEqual(evidence['sourceRate'], rate)
        self.assertEqual(evidence['asOf'], '2026-10-20')
        self.assertEqual(evidence['observedAt'], BEFORE_CLOSE.isoformat())
        self.assertEqual(evidence['sourceBarTimestamp'], int(PREVIOUS_BAR.timestamp()))
        self.assertEqual(evidence['sourceCurrentRegularEnd'], int(SESSION_END.timestamp()))
        self.assertEqual((evidence['baseCurrency'], evidence['quoteCurrency']), ('EUR', 'USD'))
        self.assertEqual((evidence['sourceBaseCurrency'], evidence['sourceQuoteCurrency']), ('EUR', 'USD'))
        self.assertEqual(evidence['sourceTicker'], 'EURUSD=X')
        self.assertIn('/EURUSD%3DX?', evidence['sourceUrl'])
        self.assertIn('Yahoo Finance', evidence['source'])

    def test_just_closed_bar_is_eligible_but_future_bars_are_not(self):
        result = chart()
        result['timestamp'].append(int((SESSION_START + dt.timedelta(days=1)).timestamp()))
        result['indicators']['adjclose'][0]['adjclose'].append(9999)
        with patch.object(updater, 'urlopen', side_effect=lambda *a, **kw: chart_response(
                *a, **kw, charts={'EURUSD=X': result})):
            rate, evidence = updater.completed_market_cap_fx('EUR', AFTER_CLOSE)
        self.assertEqual((rate, evidence['asOf']), (1.09987654321, '2026-10-21'))

    def test_next_session_metadata_alone_does_not_confirm_todays_bar(self):
        result = chart()
        regular = result['meta']['currentTradingPeriod']['regular']
        regular['start'] += 86400
        regular['end'] += 86400
        with patch.object(updater, 'urlopen', side_effect=lambda *a, **kw: chart_response(
                *a, **kw, charts={'EURUSD=X': result})):
            rate, evidence = updater.completed_market_cap_fx('EUR', BEFORE_CLOSE)
        self.assertEqual((rate, evidence['asOf']), (1.084567891234, '2026-10-20'))

    def test_inverse_alias_retains_raw_source_direction_and_value(self):
        raw = 1422.334588875
        charts = {'KRWUSD=X': chart('KRWUSD=X', values=(None, 1)),
                  'KRW=X': chart('KRW=X', 'KRW', values=(raw, 3000))}
        with patch.object(updater, 'urlopen', side_effect=lambda *a, **kw: chart_response(
                *a, **kw, charts=charts)) as open_url:
            rate, evidence = updater.completed_market_cap_fx('KRW', BEFORE_CLOSE)
        self.assertEqual(open_url.call_count, 3)
        self.assertEqual(rate, 1 / raw)
        self.assertEqual(evidence['sourceRate'], raw)
        self.assertEqual((evidence['baseCurrency'], evidence['quoteCurrency']), ('KRW', 'USD'))
        self.assertEqual((evidence['sourceBaseCurrency'], evidence['sourceQuoteCurrency']), ('USD', 'KRW'))
        self.assertEqual(evidence['sourceTicker'], 'KRW=X')

    def test_rejects_unverified_pairs_sessions_and_rates(self):
        for name, amend in {
            'wrong ticker': lambda r: r['meta'].update(symbol='GBPUSD=X'),
            'wrong quote': lambda r: r['meta'].update(currency='JPY'),
            'not FX': lambda r: r['meta'].update(instrumentType='EQUITY'),
            'not daily': lambda r: r['meta'].update(dataGranularity='5m'),
            'invalid timezone': lambda r: r['meta'].update(exchangeTimezoneName='Invalid/Timezone'),
            'missing session': lambda r: r['meta'].pop('currentTradingPeriod'),
            'invalid session': lambda r: r['meta']['currentTradingPeriod']['regular'].update(end=0),
            'unadjusted or spot only': lambda r: r['indicators'].pop('adjclose'),
            'invalid rates': lambda r: r['indicators']['adjclose'][0].update(adjclose=[0, float('inf')]),
        }.items():
            with self.subTest(name=name):
                result = chart()
                amend(result)
                with patch.object(updater, 'urlopen', side_effect=lambda *a, **kw: chart_response(
                        *a, **kw, charts={'EURUSD=X': result})):
                    self.assertIsNone(updater.completed_market_cap_fx('EUR', BEFORE_CLOSE))

    def test_updates_cap_and_provenance_atomically_and_reuses_currency_observation(self):
        checked = '2026-10-21T18:58:00+00:00'
        stale_record = {'marketCapUSD': 25, 'marketCapAsOf': '2026-10-16', 'marketCapReviewedBy': 'old',
                        'marketCapFXMetadata': {'asOf': '2026-10-16'}, 'quarters': [{'date': '2026-09-30'}]}
        local = 18_000_000_000
        current, other = copy.deepcopy(stale_record), copy.deepcopy(stale_record)
        cache = {}
        with patch.object(updater, 'urlopen', side_effect=lambda *a, **kw: chart_response(
                *a, **kw, charts={'EURUSD=X': chart()})) as open_url:
            updater.refresh_market_cap(current, {'currency': 'EUR', 'marketCap': local}, 'EUR.PA', checked, cache)
            updater.refresh_market_cap(other, {'currency': 'EUR', 'marketCap': local}, 'OTHER.PA', checked, cache)
            open_url.assert_called_once()
        self.assertEqual(current['marketCapUSD'], round(local * current['marketCapFX']))
        self.assertEqual(current['marketCapLocal'], local)
        self.assertEqual(current['marketCapCurrency'], 'EUR')
        self.assertEqual(current['marketCapUpdated'], checked)
        self.assertEqual(current['marketCapMethod'], 'provider_market_cap_converted_with_completed_daily_fx')
        self.assertEqual(current['quarters'], stale_record['quarters'])
        self.assertNotIn('marketCapAsOf', current)
        self.assertNotIn('marketCapReviewedBy', current)
        self.assertEqual(current['marketCapFXMetadata'], other['marketCapFXMetadata'])
        self.assertEqual(current['marketCapSourceUrl'], 'https://finance.yahoo.com/quote/EUR.PA/')

    def test_no_usable_currency_or_conversion_leaves_entire_old_cap_untouched(self):
        original = {'marketCapUSD': 500, 'marketCapAsOf': '2026-10-20', 'marketCapLocal': 400,
                    'marketCapFX': 1.25, 'marketCapUpdated': '2026-10-20T22:00:00+00:00',
                    'marketCapFXMetadata': {'asOf': '2026-10-20'}, 'marketCapSourceUrl': 'https://old.example'}
        cache = {}
        with patch.object(updater, 'completed_market_cap_fx', return_value=None) as fetch:
            for info in ({'marketCap': 900, 'financialCurrency': 'USD'},
                         {'marketCap': 901, 'currency': 'GBp'}, {'marketCap': 0, 'currency': 'EUR'},
                         {'marketCap': 902, 'currency': 'EUR'}, {'marketCap': 903, 'currency': 'EUR'}):
                current = copy.deepcopy(original)
                updater.refresh_market_cap(current, info, 'TEST.PA', 'new', cache)
                self.assertEqual(current, original)
            fetch.assert_called_once_with('EUR')

    def test_non_usd_reporting_currency_does_not_require_fx_for_usd_listing(self):
        current = {'marketCapCurrency': 'TWD', 'marketCapFX': 0.11, 'marketCapFXMetadata': {'asOf': '2026-10-20'}}
        with patch.object(updater, 'completed_market_cap_fx') as fetch:
            updater.refresh_market_cap(current, {'currency': 'USD', 'financialCurrency': 'TWD', 'marketCap': 999},
                                       'TSM', 'actual observation', {})
            fetch.assert_not_called()
        self.assertEqual(current['marketCapUSD'], 999)
        self.assertEqual(current['marketCapCurrency'], 'USD')
        self.assertEqual(current['marketCapUpdated'], 'actual observation')
        self.assertFalse(any(key.startswith('marketCapFX') for key in current))

    def test_collector_preserves_cap_even_as_a_new_price_is_published(self):
        symbol = 'EURONEXT:TEST'
        original_caps = {'marketCapUSD': 123, 'marketCapUpdated': 'old cap timestamp',
                         'marketCapFXMetadata': {'asOf': '2026-10-19'}, 'marketCapFX': 1.12}
        company = {'symbol': symbol, 'ticker': 'TEST', 'country': '프랑스', 'name': 'Test'}
        previous = {symbol: {'sourceTicker': 'TEST.PA', 'prices': [['2026-10-19', 100]], **original_caps}}
        with (patch.object(updater, 'rows', [company]), patch.object(updater, 'stocks', previous),
              patch.object(updater, 'completed_fx_observation', return_value=(None, None)),
              patch.object(updater, 'completed_market_cap_fx', return_value=None),
              patch.object(updater, 'fetch_prices', return_value=[['2026-10-20', 110]]),
              patch.object(updater, 'fetch_info', return_value={'marketCap': 567, 'currency': 'EUR'}),
              patch.object(updater.yf, 'Ticker', create=True), patch.object(updater.time, 'sleep'),
              patch.object(updater, 'write_json') as write, patch.dict(updater.os.environ, LIMIT='0', SYMBOLS='')):
            updater.main()
        candidate = write.call_args.args[1]['stocks'][symbol]
        self.assertEqual({k: v for k, v in candidate.items() if k.startswith('marketCap')}, original_caps)
        self.assertEqual(candidate['lastPriceDate'], '2026-10-20')


if __name__ == '__main__':
    unittest.main()
