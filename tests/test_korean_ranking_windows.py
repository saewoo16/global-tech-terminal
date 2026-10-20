import copy
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from korean_rankings_source import validate_period_windows, validate_turnover_amounts

class RankingWindowTests(unittest.TestCase):
    def fixture(self):
        return {period:{investor:{'coverage':{'start':start,'end':'2026-10-20'}} for investor in ('foreign','institution')} for period,start in [('day','2026-10-20'),('week','2026-10-14'),('month','2026-09-17')]}
    def test_rolling_periods_keep_actual_returned_windows(self):
        periods=self.fixture(); prior=copy.deepcopy(periods)
        self.assertEqual(validate_period_windows(periods),'2026-10-20')
        self.assertEqual(periods,prior)
    def test_rejects_stale_week_in_current_day_batch(self):
        periods=self.fixture(); periods['week']['foreign']['coverage']['end']='2026-10-19'
        with self.assertRaisesRegex(ValueError,'Mixed provider period end'):
            validate_period_windows(periods)
    def test_turnover_placeholders_are_not_actual_zero(self):
        for value in (None, '', '0', 0, '-1'):
            with self.assertRaisesRegex(ValueError,'placeholder turnover'):
                validate_turnover_amounts([{'tradeAmount':value}])
        validate_turnover_amounts([{'tradeAmount':'123456789'}])
    def test_rejects_inverted_period(self):
        periods=self.fixture(); periods['month']['institution']['coverage']['start']='2026-10-21'
        with self.assertRaisesRegex(ValueError,'Invalid provider period'):
            validate_period_windows(periods)

if __name__=='__main__':unittest.main()
