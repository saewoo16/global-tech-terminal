"""An earnings date is its New York announcement date, never its refresh date."""
import copy
import json
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from validate_us_analysis import validate, market_time

class EarningsSessionTests(unittest.TestCase):
    def setUp(self):
        self.data=json.loads((ROOT/'data/us_analysis.json').read_text())
        self.entry=next(e for e in self.data['entries'] if e['date']=='2026-10-20')
    def test_new_york_date_spans_two_korean_dates(self):
        for timestamp in ('2026-10-20T20:30:00+09:00','2026-10-21T05:30:00+09:00'):
            self.assertEqual(market_time(timestamp).date().isoformat(),'2026-10-20')
        self.assertEqual(market_time('2026-12-17T06:30:00+09:00').date().isoformat(),'2026-12-16')
    def test_previous_session_earnings_cannot_be_copied_forward(self):
        row=copy.deepcopy(self.entry['earnings']['rows'][0])
        old=next(e for e in self.data['entries'] if e['date']=='2026-10-19')
        old['sources'].extend(s for s in self.entry['sources'] if s['id'] not in {x['id'] for x in old['sources']})
        old['earnings']['rows'].append(row)
        with self.assertRaisesRegex(AssertionError,'actual ET announcement'):
            validate(self.data)
    def test_korean_calendar_release_date_is_rejected(self):
        self.entry['earnings']['rows'][0]['releaseTiming']['publishedAt']='2026-10-20T05:30:00+09:00'
        with self.assertRaisesRegex(AssertionError,'America/New_York'):
            validate(self.data)
    def test_late_call_refresh_does_not_change_original_announcement(self):
        row=self.entry['earnings']['rows'][0]
        row['callUpdatedAt']='2026-10-22T02:00:00Z'
        self.assertEqual(row['releaseDate'],'2026-10-20')
        validate(self.data)
    def test_snapshot_never_uses_post_cutoff_release(self):
        self.entry['earnings']['reportCutoffAt']='2026-10-20T13:00:00Z'
        with self.assertRaisesRegex(AssertionError,'report cutoff'):
            validate(self.data)
    def test_spacex_is_original_session_only_and_smci_is_preliminary(self):
        rows={r['ticker']:r for r in self.entry['earnings']['rows']}
        self.assertEqual(rows['SPCX']['releaseDate'],'2026-10-20')
        self.assertEqual(rows['SPCX']['universeScope'],'additional_interest')
        self.assertEqual(rows['SMCI']['releaseType'],'preliminary')
        self.assertFalse(rows['SMCI']['displayCallHighlights'])
        for e in self.data['entries']:
            if e['date']!='2026-10-20': self.assertNotIn('SPCX',{r['ticker'] for r in e.get('earnings',{}).get('rows',[])})
    def test_additional_interest_requires_explicit_scope(self):
        row=copy.deepcopy(self.entry['earnings']['rows'][0]);row['ticker']='SYNTHETIC'
        self.entry['earnings']['rows'].append(row)
        with self.assertRaises(AssertionError):validate(self.data)
        row['universeScope']='additional_interest'
        validate(self.data)
if __name__=='__main__':unittest.main()
