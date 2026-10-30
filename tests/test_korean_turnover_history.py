"""Independent regression checks for full-history venue turnover reconstruction."""
import copy
from decimal import Decimal
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from update_korean_turnover_history import investor_total, build, year_start, validate_venue_status

CODES = ('1000','2000','3000','3100','4000','5000','6000','7000','7100','8000','9000','9001')

def daily_row(day='20261030'):
    return {'bizdate': day, 'time': '', 'netAmounts': [
        {'investorGubun': code, 'buyPrice': str(100000000 + i * 1000000),
         'sellPrice': str(100000000 + i * 1000000), 'buyQuant': str(100 + i),
         'sellQuant': str(100 + i), 'diffValue': '0'}
        for i, code in enumerate(CODES)]}

class InvestorTotalTests(unittest.TestCase):
    def test_single_side_total_not_buy_plus_sell_or_net(self):
        row = daily_row()
        expected = sum(Decimal(r['buyPrice']) for r in row['netAmounts'])
        actual = investor_total(row)
        self.assertIsInstance(actual, Decimal)
        self.assertEqual(actual, expected)
        self.assertNotEqual(actual, expected * 2)
        self.assertNotEqual(actual, Decimal(0))

    def test_exact_original_precision_and_no_mutation(self):
        row = daily_row()
        row['netAmounts'][0].update(buyPrice='100000001', sellPrice='100000001')
        before = copy.deepcopy(row)
        self.assertEqual(investor_total(row), Decimal('1266000001'))
        self.assertEqual(row, before)

    def test_duplicate_investor_code_rejected(self):
        row = daily_row(); row['netAmounts'][-1]['investorGubun'] = '1000'
        with self.assertRaises(ValueError): investor_total(row)

    def test_missing_category_rejected_not_treated_as_zero(self):
        row = daily_row(); row['netAmounts'].pop()
        with self.assertRaises(ValueError): investor_total(row)

    def test_derived_institution_total_rejected(self):
        row = daily_row(); row['netAmounts'].append(dict(row['netAmounts'][0], investorGubun='9999'))
        with self.assertRaises(ValueError): investor_total(row)

    def test_unknown_category_rejected(self):
        row = daily_row(); row['netAmounts'][-1]['investorGubun'] = '9998'
        with self.assertRaises(ValueError): investor_total(row)

    def test_diff_value_must_equal_buy_minus_sell_per_category(self):
        row = daily_row(); row['netAmounts'][0]['diffValue'] = '1'
        with self.assertRaises(ValueError): investor_total(row)

    def test_small_provider_rounding_side_difference_allowed(self):
        row = daily_row(); row['netAmounts'][0].update(buyPrice='101000000', diffValue='1000000')
        self.assertEqual(investor_total(row), Decimal('1267000000'))

    def test_side_difference_exceeds_provider_precision_rejected(self):
        row = daily_row(); row['netAmounts'][0].update(buyPrice='113000000', diffValue='13000000')
        with self.assertRaises(ValueError): investor_total(row)

    def test_share_totals_must_balance_exactly(self):
        row = daily_row(); row['netAmounts'][0]['buyQuant'] = '101'
        with self.assertRaises(ValueError): investor_total(row)

    def test_invalid_gross_amounts_or_quantities_rejected(self):
        for field in ('buyPrice','sellPrice','buyQuant','sellQuant'):
            for invalid in ('-1', 'NaN', 'Infinity', '1.5', None, True):
                with self.subTest(field=field, value=invalid):
                    row = daily_row(); row['netAmounts'][0][field] = invalid
                    with self.assertRaises(ValueError): investor_total(row)

    def test_zero_category_is_valid_not_missing(self):
        row = daily_row(); row['netAmounts'][0].update(buyPrice='0', sellPrice='0', buyQuant='0', sellQuant='0')
        self.assertEqual(investor_total(row), Decimal('1166000000'))

    def test_reordered_disjoint_categories_do_not_change_total(self):
        row = daily_row(); expected = investor_total(row)
        row['netAmounts'].reverse()
        self.assertEqual(investor_total(row), expected)

def payload_fixture():
    dates = ['2025-10-30', '2026-10-29', '2026-10-30']
    return {'sources': [], 'otherPanel': {'preserve': [1, 2, 3]},
            'flows': {'markets': {m: {'rows': [{'date': d} for d in dates]} for m in ('KOSPI','KOSDAQ')}},
            'marketTurnover': {'markets': {m: {'rows': [{'date': '2026-10-29', 'turnover': 123}],
                'comparisonSeries': {'preserve': True}} for m in ('KOSPI','KOSDAQ')}}}

def evidence_fixture():
    snapshots = []
    for v in ('KRX', 'NXT'):
        for m in ('KOSPI', 'KOSDAQ'):
            snapshots.append({'venue': v, 'market': m, 'url':
                f'https://stock.naver.com/api/domestic/market/trend/daily?tradeType={v}&marketType={m}&bizdate=20261030&startIdx=0&pageSize=30',
                'observedAt': '2026-10-30T13:21:00+00:00', 'sha256': 'a' * 64,
                'data': {'content': [daily_row(d) for d in ('20261030','20261029','20251030')]}})
    return {'targetDate': '2026-10-30', 'observedAt': '2026-10-30T13:22:00+00:00', 'snapshots': snapshots}

class HistoryBuildTests(unittest.TestCase):
    def test_each_market_has_complete_sorted_history_and_single_side_components(self):
        result = build(payload_fixture(), evidence_fixture(), '2026-10-30')
        for m in ('KOSPI','KOSDAQ'):
            s = result['marketTurnover']['markets'][m]['integratedHistory']
            self.assertEqual([r['date'] for r in s['rows']], ['2025-10-30','2026-10-29','2026-10-30'])
            self.assertEqual(s['coverage']['count'], 3)
            self.assertEqual(s['asOf'], '2026-10-30')
            self.assertEqual(s['rows'][-1]['turnover'], 25.32)
            self.assertEqual(s['rows'][-1]['sourceValue'], '2532000000')
            self.assertEqual(s['rows'][-1]['components']['KRX']['grossBuyKRW'], '1266000000')
            self.assertFalse(s['rows'][-1]['officialAggregate'])

    def test_existing_legacy_series_and_other_panels_untouched(self):
        payload = payload_fixture(); before = copy.deepcopy(payload)
        result = build(payload, evidence_fixture(), '2026-10-30')
        self.assertEqual(payload, before)
        self.assertEqual(result['otherPanel'], before['otherPanel'])
        self.assertEqual(result['flows'], before['flows'])
        for m in ('KOSPI','KOSDAQ'):
            for key in ('rows', 'comparisonSeries'):
                self.assertEqual(result['marketTurnover']['markets'][m][key], before['marketTurnover']['markets'][m][key])

    def test_missing_venue_or_completed_date_rejected(self):
        for remove_venue in (True, False):
            evidence = evidence_fixture()
            if remove_venue: evidence['snapshots'].pop()
            else: evidence['snapshots'][0]['data']['content'].pop()
            with self.subTest(whole_venue=remove_venue):
                with self.assertRaises(ValueError): build(payload_fixture(), evidence, '2026-10-30')

    def test_duplicate_page_or_date_rejected(self):
        evidence = evidence_fixture(); evidence['snapshots'].append(copy.deepcopy(evidence['snapshots'][0]))
        with self.assertRaises(ValueError): build(payload_fixture(), evidence, '2026-10-30')

    def test_future_observation_and_unverified_target_rejected(self):
        evidence = evidence_fixture(); evidence['snapshots'][0]['data']['content'][0]['bizdate'] = '20261031'
        with self.assertRaises(ValueError): build(payload_fixture(), evidence, '2026-10-30')
        with self.assertRaises(ValueError): build(payload_fixture(), evidence_fixture(), '2026-10-31')

    def test_url_must_identify_actual_venue_market(self):
        evidence = evidence_fixture(); evidence['snapshots'][0]['url'] = evidence['snapshots'][0]['url'].replace('tradeType=KRX', 'tradeType=NXT')
        with self.assertRaises(ValueError): build(payload_fixture(), evidence, '2026-10-30')

    def test_changed_scope_cannot_be_spliced(self):
        payload = payload_fixture()
        payload['marketTurnover']['markets']['KOSPI']['integratedHistory'] = {'sessionScope':'regular-plus-nxt-all-sessions','rows':[]}
        with self.assertRaises(ValueError): build(payload, evidence_fixture(), '2026-10-30')

    def test_same_values_reobservation_is_idempotent(self):
        result = build(payload_fixture(), evidence_fixture(), '2026-10-30')
        evidence = evidence_fixture(); evidence['observedAt'] = '2026-10-30T13:25:00+00:00'
        for snapshot in evidence['snapshots']: snapshot['observedAt'] = '2026-10-30T13:24:00+00:00'
        again = build(result, evidence, '2026-10-30')
        self.assertIs(again, result)

    def test_revised_nonprice_evidence_is_not_silently_discarded(self):
        result = build(payload_fixture(), evidence_fixture(), '2026-10-30')
        evidence = evidence_fixture()
        for snapshot in evidence['snapshots']:
            for record in snapshot['data']['content'][0]['netAmounts']:
                record['buyQuant'] = str(int(record['buyQuant']) + 1)
                record['sellQuant'] = str(int(record['sellQuant']) + 1)
        updated = build(result, evidence, '2026-10-30')
        old = result['marketTurnover']['markets']['KOSPI']['integratedHistory']['rows'][-1]
        new = updated['marketTurnover']['markets']['KOSPI']['integratedHistory']['rows'][-1]
        self.assertEqual(new['turnover'], old['turnover'])
        self.assertEqual(int(new['components']['KRX']['buyShares']), int(old['components']['KRX']['buyShares']) + 12)

    def test_year_window_clamps_leap_day(self):
        self.assertEqual(year_start('2024-02-29'), '2023-02-28')

def venue_status(venue):
    return {'serverTime': '2026-10-30T21:00:00+09:00', 'exchanges': [{'exchange': venue.lower(), 'statuses': [
        {'marketType': m, 'stockType': 'stock', 'today': {'isTradingDay': True},
         'latest': {'tradeBaseAt': '2026-10-30', 'session': {'marketStatusDetailType': 'close', 'marketSessionType': 'afterMarket'}}}
        for m in ('KOSPI','KOSDAQ')]}]}

class VenueStatusTests(unittest.TestCase):
    def test_each_actual_venue_completed_and_input_preserved(self):
        for venue in ('KRX','NXT'):
            status = venue_status(venue); before = copy.deepcopy(status)
            validate_venue_status(status, '2026-10-30', venue)
            self.assertEqual(status, before)

    def test_other_venue_cannot_certify_requested_venue(self):
        for actual, requested in (('NXT','KRX'), ('KRX','NXT')):
            with self.subTest(actual=actual, requested=requested):
                with self.assertRaises(ValueError): validate_venue_status(venue_status(actual), '2026-10-30', requested)

    def test_open_preclose_old_date_holiday_or_missing_market_rejected(self):
        for venue in ('KRX','NXT'):
            for transform in (
                lambda s: s.update(serverTime='2026-10-30T19:59:59+09:00'),
                lambda s: s['exchanges'][0]['statuses'][0]['latest'].update(tradeBaseAt='2026-10-29'),
                lambda s: s['exchanges'][0]['statuses'][0]['latest']['session'].update(marketStatusDetailType='open'),
                lambda s: s['exchanges'][0]['statuses'][0]['latest']['session'].update(marketSessionType='regularMarket'),
                lambda s: s['exchanges'][0]['statuses'][0]['today'].update(isTradingDay=False),
                lambda s: s['exchanges'][0]['statuses'].pop(),
            ):
                with self.subTest(venue=venue, transform=transform):
                    status = venue_status(venue); transform(status)
                    with self.assertRaises(ValueError): validate_venue_status(status, '2026-10-30', venue)

if __name__ == '__main__':
    unittest.main()
