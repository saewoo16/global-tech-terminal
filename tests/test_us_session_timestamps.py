"""Calendar and timestamp regressions without rewriting archival evidence."""
import copy
import datetime as dt
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from validate_us_analysis import (validate, validate_session_timestamps,
                                  validate_earnings_prices, us_session_close, ET)
from us_exchange_calendar import latest_completed_session


class SessionTimestampTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload = json.loads((ROOT / 'data/us_analysis.json').read_text())

    def setUp(self):
        self.entry = copy.deepcopy(max(self.payload['entries'], key=lambda e: e['date']))

    def check(self, entry=None, now='2026-12-31T23:00:00Z'):
        validate_session_timestamps(entry or self.entry, now=now)

    def synthetic_session(self, date, previous, offset, close=16):
        entry = copy.deepcopy(self.entry)
        entry['date'] = date
        entry['collectedAt'] = f'{date}T{close:02}:10:00{offset}'
        entry['sessionVerification'].update(exchangeDate=date, previousSession=previous,
            openedAt=f'{date}T09:30:00{offset}', closedAt=f'{date}T{close:02}:00:00{offset}',
            retrievedAt=f'{date}T{close:02}:10:00{offset}')
        return entry

    def test_full_archive_passes_unchanged(self):
        before = copy.deepcopy(self.payload)
        self.assertEqual(validate(self.payload), len(self.payload['entries']))
        self.assertEqual(self.payload, before)

    def test_2099_close_rejected_by_public_validator(self):
        payload = copy.deepcopy(self.payload)
        max(payload['entries'], key=lambda e: e['date'])['sessionVerification']['closedAt'] = '2099-11-06T16:00:00-05:00'
        with self.assertRaisesRegex(AssertionError, 'regular-session close'):
            validate(payload)

    def test_exchange_date_mismatch(self):
        self.entry['sessionVerification']['exchangeDate'] = '2026-11-05'
        with self.assertRaisesRegex(AssertionError, 'exchangeDate'):
            self.check()

    def test_wrong_previous_session(self):
        self.entry['sessionVerification']['previousSession'] = '2026-11-04'
        with self.assertRaisesRegex(AssertionError, 'previous trading'):
            self.check()

    def test_before_close_retrieval(self):
        self.entry['sessionVerification']['retrievedAt'] = '2026-11-06T15:59:59-05:00'
        with self.assertRaisesRegex(AssertionError, 'retrieval'):
            self.check()

    def test_future_retrieval(self):
        self.entry['sessionVerification']['retrievedAt'] = '2099-11-06T22:00:00Z'
        with self.assertRaisesRegex(AssertionError, 'retrieval'):
            self.check()

    def test_entry_collection_before_close(self):
        self.entry['collectedAt'] = '2026-11-06T15:59:59-05:00'
        with self.assertRaisesRegex(AssertionError, 'Entry collection'):
            self.check()

    def test_entry_collection_in_future(self):
        self.entry['collectedAt'] = '2099-11-06T16:01:00-05:00'
        with self.assertRaisesRegex(AssertionError, 'Entry collection'):
            self.check()

    def test_future_session(self):
        with self.assertRaisesRegex(AssertionError, 'future session'):
            self.check(now='2026-11-06T20:59:59Z')

    def test_naive_timestamp(self):
        self.entry['sessionVerification']['closedAt'] = '2026-11-06T16:00:00'
        with self.assertRaisesRegex(AssertionError, 'offset'):
            self.check()

    def test_wrong_dst_offset(self):
        self.entry['sessionVerification']['closedAt'] = '2026-11-06T16:00:00-04:00'
        with self.assertRaisesRegex(AssertionError, 'regular-session close'):
            self.check()

    def test_edt_and_est_sessions(self):
        self.check(self.synthetic_session('2026-10-30', '2026-10-29', '-04:00'))
        self.check(self.synthetic_session('2026-11-02', '2026-10-30', '-05:00'))

    def test_equivalent_utc_and_korean_offsets(self):
        self.entry['sessionVerification'].update(openedAt='2026-11-06T14:30:00Z', closedAt='2026-11-07T06:00:00+09:00')
        self.check()

    def test_official_holiday(self):
        with self.assertRaisesRegex(AssertionError, 'non-trading'):
            self.check(self.synthetic_session('2026-11-26', '2026-11-25', '-05:00'))

    def test_weekend(self):
        with self.assertRaisesRegex(AssertionError, 'non-trading'):
            self.check(self.synthetic_session('2026-11-07', '2026-11-06', '-05:00'))

    def test_early_close_and_holiday_previous_session(self):
        self.check(self.synthetic_session('2026-11-27', '2026-11-25', '-05:00', 13))
        self.check(self.synthetic_session('2026-12-24', '2026-12-23', '-05:00', 13))

    def test_normal_close_on_early_close_day_rejected(self):
        with self.assertRaisesRegex(AssertionError, 'regular-session close'):
            self.check(self.synthetic_session('2026-11-27', '2026-11-25', '-05:00'))

    def test_latest_completed_session_boundaries(self):
        cases = (
            ('2026-11-06T20:59:59+00:00', '2026-11-05'),
            ('2026-11-06T21:00:00+00:00', '2026-11-06'),
            ('2026-10-30T19:59:59+00:00', '2026-10-29'),
            ('2026-10-30T20:00:00+00:00', '2026-10-30'),
            ('2026-11-27T17:59:59+00:00', '2026-11-25'),
            ('2026-11-27T18:00:00+00:00', '2026-11-27'),
            ('2026-11-28T22:00:00+00:00', '2026-11-27'),
            ('2026-11-26T22:00:00+00:00', '2026-11-25'),
        )
        for now, expected in cases:
            with self.subTest(now=now):
                self.assertEqual(latest_completed_session(dt.datetime.fromisoformat(now)).isoformat(), expected)

    def test_unreviewed_year_fails_closed(self):
        with self.assertRaisesRegex(AssertionError, 'not reviewed'):
            us_session_close(dt.date(2027, 1, 4))

    def test_legacy_entry_not_recertified(self):
        legacy = next(e for e in self.payload['entries'] if e['date'] == '2026-10-16')
        self.assertNotIn('sessionVerification', legacy)
        self.check(legacy)
        self.assertNotIn('sessionVerification', legacy)

    def test_new_entry_cannot_omit_session_verification(self):
        del self.entry['sessionVerification']
        with self.assertRaisesRegex(AssertionError, 'verification required'):
            self.check()

    def test_official_host_without_calendar_is_not_calendar_evidence(self):
        ids = self.entry['sessionVerification']['sourceIds']
        for source in self.entry['sources']:
            if source['id'] in ids:
                source['url'] = 'https://www.nasdaq.com/market-activity/stocks/aapl'
        with self.assertRaisesRegex(AssertionError, 'calendar source'):
            self.check()

    def test_session_observation_bounds(self):
        for observed in ('2026-11-06T15:59:59-05:00', '2099-11-06T16:01:00-05:00'):
            with self.subTest(observed=observed):
                self.entry['sessionVerification']['observedAt'] = observed
                with self.assertRaisesRegex(AssertionError, 'observation'):
                    self.check()
        self.entry['sessionVerification']['observedAt'] = '2026-11-06T16:01:00-05:00'
        self.check()

    def test_earnings_after_hours_and_early_close(self):
        row = {'releaseDate': '2026-11-27', 'releaseTiming': {'session': 'after_close', 'publishedAt': '2026-11-27T13:01:00-05:00', 'sourceIds': ['release']},
               'priceReaction': {'currency': 'USD', 'regular': {'date': '2026-11-27', 'previousDate': '2026-11-25', 'closedAt': '2026-11-27T13:00:00-05:00', 'close': 100, 'previousClose': 100, 'changePct': 0, 'sourceIds': ['price']},
                                 'afterHours': {'status': 'verified', 'observedAt': '2026-11-27T13:02:00-05:00', 'price': 101, 'changePct': 1, 'sourceIds': ['quote']}}}
        validate_earnings_prices(row)
        for observed in ('2026-11-27T12:59:59-05:00', '2026-11-27T13:01:00-05:00', '2026-11-28T13:02:00-05:00'):
            with self.subTest(observed=observed):
                row['priceReaction']['afterHours']['observedAt'] = observed
                with self.assertRaises(AssertionError):
                    validate_earnings_prices(row)


if __name__ == '__main__':
    unittest.main()
