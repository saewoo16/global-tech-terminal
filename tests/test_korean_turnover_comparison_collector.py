"""Offline regression coverage for scoped, complete NXT turnover collection."""
import copy
import sys
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import update_korean_turnover_comparison as collector
from manage_korean_turnover_comparison import empty_series, merge

DAY = '2026-10-30'
STAMP = DAY + 'T12:00:00+00:00'

def status():
    return {'serverTime': DAY + 'T21:00:00+09:00', 'exchanges': [{'exchange': 'nxt', 'statuses': [
        {'marketType': m, 'stockType': 'stock', 'today': {'isTradingDay': True},
         'latest': {'tradeBaseAt': DAY, 'session': {'marketStatusDetailType': 'close', 'marketSessionType': 'afterMarket'}}}
        for m in ('KOSPI', 'KOSDAQ')]}]}

def stocks():
    return [{'itemcode': code, 'type': 'ST', 'sosok': sosok, 'marketStatus': 'CLOSE',
             'tradingSessionType': 'AFTER_MARKET', 'tradeAmount': amount, 'tradeVolume': '100'}
            for code, sosok, amount in [('000001', '0', '123000000'), ('000002', '1', '456000000')]]

def payload():
    row = {'date': DAY, 'turnover': 100, 'sourceValue': '100', 'sourceUnit': '억원',
           'conversionToEokKRW': 1, 'observedAt': STAMP, 'sourceIds': ['regular-source'],
           'scopeVerified': True, 'valueStatus': 'final'}
    markets = {}
    for m in ('KOSPI', 'KOSDAQ'):
        regular = empty_series(m, 'regular')
        regular.update(rows=[copy.deepcopy(row)], sourceIds=['regular-source'], status='verified', asOf=DAY,
                       coverage={'start': DAY, 'end': DAY, 'count': 1})
        markets[m] = {'unit': '억원', 'scope': 'whole-market', 'sourceIds': ['regular-source'],
                      'rows': [copy.deepcopy(row)], 'coverage': {'start': DAY, 'end': DAY, 'count': 1},
                      'comparisonSeries': {'regular': regular, 'integrated': empty_series(m, 'integrated')}}
    return {'sources': [{'id': 'regular-source', 'url': 'https://example.org/regular'}],
            'marketTurnover': {'markets': markets}, 'otherPanel': {'doNotTouch': [1, 2, 3]}}

def fetcher(url):
    if url == collector.STATUS:
        data = status()
    else:
        q = parse_qs(urlparse(url).query)
        data = stocks()
        if q['marketType'][0] != 'ALL':
            wanted = '0' if q['marketType'][0] == 'KOSPI' else '1'
            data = [r for r in data if r['sosok'] == wanted]
        page, size = int(q['startIdx'][0]), int(q['pageSize'][0])
        data = data[page * size:(page + 1) * size]
    return {'url': url, 'observedAt': STAMP, 'sha256': 'test-only', 'data': data}


class TurnoverComparisonCollectorTests(unittest.TestCase):
    def test_complete_pagination_and_market_splits(self):
        evidence = collector.collect(DAY, fetcher)
        self.assertEqual(evidence['universeCount'], 2)
        self.assertEqual(evidence['checks']['page-1']['data'], [])
        self.assertEqual(len(evidence['checks']['KOSPI']['data']), 1)

    def test_rejects_incomplete_pagination(self):
        def incomplete(url):
            r = fetcher(url)
            if 'pageSize=100' in url and 'startIdx=0' in url:
                r['data'] = r['data'][:1]
            return r
        with self.assertRaisesRegex(ValueError, 'pagination disagrees'):
            collector.collect(DAY, incomplete)

    def test_rejects_nonempty_final_page(self):
        def extra(url):
            r = fetcher(url)
            if 'pageSize=100' in url and 'startIdx=1' in url:
                r['data'] = stocks()[:1]
            return r
        with self.assertRaisesRegex(ValueError, 'omitted final page'):
            collector.collect(DAY, extra)

    def test_rejects_wrong_market_split(self):
        def wrong(url):
            r = fetcher(url)
            if 'marketType=KOSDAQ' in url:
                r['data'][0]['tradeAmount'] = '1'
            return r
        with self.assertRaisesRegex(ValueError, 'market split disagrees'):
            collector.collect(DAY, wrong)

    def test_rejects_uncompleted_or_wrong_date(self):
        for transform in (
            lambda s: s.update(serverTime=DAY + 'T19:59:59+09:00'),
            lambda s: s.update(serverTime='2026-10-31T21:00:00+09:00'),
            lambda s: s['exchanges'][0]['statuses'][0]['latest'].update(tradeBaseAt='2026-10-29'),
            lambda s: s['exchanges'][0]['statuses'][0]['latest']['session'].update(marketStatusDetailType='open'),
            lambda s: s['exchanges'][0]['statuses'][0]['today'].update(isTradingDay=False),
        ):
            with self.subTest(transform=transform):
                s = status(); transform(s)
                with self.assertRaises(ValueError):
                    collector.validate_status(s, DAY)

    def test_rejects_duplicates_unclassified_and_open_rows(self):
        for rows in (stocks() + stocks()[:1], [dict(stocks()[0], sosok='2')],
                     [dict(stocks()[0], type='ETF')], [dict(stocks()[0], marketStatus='OPEN')],
                     [dict(stocks()[0], tradeAmount='NaN')]):
            with self.subTest(rows=rows):
                with self.assertRaises(ValueError): collector.index(rows)

    def test_sums_once_at_provider_precision(self):
        p = payload(); e = collector.collect(DAY, fetcher)
        b = collector.build_bundle(p, e)
        self.assertEqual(b['markets']['KOSPI']['integrated']['rows'][0]['turnover'], 101.23)
        self.assertEqual(b['markets']['KOSDAQ']['integrated']['rows'][0]['turnover'], 104.56)
        self.assertFalse(b['markets']['KOSPI']['integrated']['rows'][0]['officialAggregate'])
        updated = merge(p, b, 'integrated', DAY)
        again = collector.build_bundle(updated, e)
        self.assertEqual(again['markets']['KOSPI']['integrated']['rows'][0]['turnover'], 101.23)
        self.assertEqual(updated['otherPanel'], p['otherPanel'])
        for m in ('KOSPI', 'KOSDAQ'):
            self.assertEqual(updated['marketTurnover']['markets'][m]['comparisonSeries']['regular'],
                             p['marketTurnover']['markets'][m]['comparisonSeries']['regular'])
            self.assertEqual(updated['marketTurnover']['markets'][m]['rows'], p['marketTurnover']['markets'][m]['rows'])

    def test_same_amount_later_observation_is_idempotent(self):
        p = payload(); e = collector.collect(DAY, fetcher)
        once = merge(p, collector.build_bundle(p, e), 'integrated', DAY)
        later = copy.deepcopy(e); later['observedAt'] = DAY + 'T13:00:00+00:00'
        twice = merge(once, collector.build_bundle(once, later), 'integrated', DAY)
        self.assertIs(twice, once)

    def test_rechecks_completed_date_after_snapshot(self):
        calls = []
        def rollover(url):
            r = fetcher(url)
            if url == collector.STATUS:
                calls.append(url)
                if len(calls) == 2:
                    r['data']['exchanges'][0]['statuses'][0]['latest']['tradeBaseAt'] = '2026-11-02'
            return r
        with self.assertRaisesRegex(ValueError, 'current completed'):
            collector.collect(DAY, rollover)

    def test_final_value_not_downgraded_to_provisional(self):
        p = payload(); e = collector.collect(DAY, fetcher)
        b = collector.build_bundle(p, e)
        final = merge(p, b, 'integrated', DAY)
        provisional = copy.deepcopy(b)
        for m in ('KOSPI', 'KOSDAQ'):
            provisional['markets'][m]['integrated']['rows'][0].update(
                valueStatus='provisional', turnover=1, sourceValue='1')
        result = merge(final, provisional, 'integrated', DAY)
        self.assertIs(result, final)

    def test_missing_regular_is_not_replaced_with_zero(self):
        p = payload(); p['marketTurnover']['markets']['KOSPI']['comparisonSeries']['regular']['rows'] = []
        with self.assertRaisesRegex(ValueError, 'Same-date verified KRX'):
            collector.build_bundle(p, collector.collect(DAY, fetcher))

    def test_future_merge_rejected_and_wrong_mode_preserves_input(self):
        p = payload(); original = copy.deepcopy(p)
        b = collector.build_bundle(p, collector.collect(DAY, fetcher))
        with self.assertRaisesRegex(ValueError, 'Future'):
            merge(p, b, 'integrated', '2026-10-29')
        self.assertEqual(p, original)

if __name__ == '__main__':
    unittest.main()
