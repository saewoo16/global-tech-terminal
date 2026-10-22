import copy
import json
import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from validate_us_analysis import validate_earnings_prices

class SessionAfterHoursSupplementTests(unittest.TestCase):
    def setUp(self):
        data=json.loads((ROOT/'data/us_analysis.json').read_text())
        entry=next(e for e in data['entries'] if e['date']=='2026-10-21')
        self.rows=entry['earnings']['rows']
        self.row=copy.deepcopy(next(r for r in self.rows if r['ticker']=='META'))
    def test_all_twenty_verified_without_changing_original_snapshot(self):
        self.assertEqual(len(self.rows),20)
        for r in self.rows:
            self.assertEqual(r['priceReaction']['subsequentAfterHours']['status'],'verified')
            validate_earnings_prices(r)
    def test_morning_or_unknown_release_time_is_not_a_quote_blocker(self):
        for session in ('before_open','unknown'):
            r=copy.deepcopy(self.row)
            r['releaseTiming']={'session':session,'publishedAt':None,'sourceIds':['fixture']}
            validate_earnings_prices(r)
    def test_wrong_day_premarket_and_overnight_rejected(self):
        for observed in ('2026-10-20T19:59:00-04:00','2026-10-21T09:00:00-04:00','2026-10-21T20:01:00-04:00','2026-10-22T08:00:00-04:00'):
            r=copy.deepcopy(self.row);r['priceReaction']['subsequentAfterHours']['observedAt']=observed
            with self.assertRaises(AssertionError):validate_earnings_prices(r)
    def test_provider_previous_close_percentage_is_not_afterhours_return(self):
        self.row['priceReaction']['subsequentAfterHours']['changePct']=2.64
        with self.assertRaises(AssertionError):validate_earnings_prices(self.row)
    def test_source_and_real_collection_time_required(self):
        for field,value in [('sourceIds',[]),('collectedAt','2026-10-21T22:00:00Z'),('presentationPhase','initial')]:
            r=copy.deepcopy(self.row);r['priceReaction']['subsequentAfterHours'][field]=value
            with self.assertRaises(AssertionError):validate_earnings_prices(r)
