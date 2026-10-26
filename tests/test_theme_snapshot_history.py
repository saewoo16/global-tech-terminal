"""A newer membership/cap catalog must not change stored historical observations."""
import copy
from datetime import date as calendar_date, timedelta
import json
import sys
import unittest
from pathlib import Path
R=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(R/'scripts'))
from korean_theme_source import build, normalize
from validate_korean_market import validate

class ThemeSnapshotHistoryTests(unittest.TestCase):
    def test_changed_membership_preserves_real_old_snapshot(self):
        payload=json.loads((R/'data/korea-market.json').read_text())
        self.assert_membership_change_preserves_snapshot(payload['themes'])

    def assert_membership_change_preserves_snapshot(self, themes):
        prior=copy.deepcopy(themes)
        date=next(d for d,v in prior['daily'].items() if v.get('rows'))
        incoming_date=(calendar_date.fromisoformat(date)+timedelta(days=1)).isoformat()
        provider_date=incoming_date.replace('-','')
        self.assertNotEqual(date,incoming_date)
        saved=copy.deepcopy(prior['daily'][date])
        catalog={b['id']:b for b in prior['baskets']}
        responses={}
        for market,code in [('KOSPI','005930'),('KOSDAQ','247540')]:
            for investor in ['FOREIGNER','ORGANIZATION']:
                for period in ['DAY','WEEK','MONTH']:
                    responses[f'{market}_{investor}_{period}']={'url':'https://stock.naver.com/api/test','data':{'sections':{
                        'buyRankList':[{'type':'ST','itemcode':code,'accTradeAmount':'123456000','bizdateFrom':provider_date,'bizdateTo':provider_date,'estimated':False}], 'sellRankList':[]}}}
        incoming=build(responses=responses)
        incoming['basketDefinitionVersion']='test-new-version'
        incoming['membershipAsOf']=incoming_date
        incoming['marketCapAsOf']=incoming_date
        result=normalize(incoming,[date,incoming_date],prior)
        historical=result['daily'][date]
        self.assertEqual(historical['basketDefinitionVersion'],saved['basketDefinitionVersion'])
        self.assertEqual(historical['marketCapAsOf'],saved['marketCapAsOf'])
        for actual,original in zip(historical['rows'],saved['rows']):
            self.assertEqual(actual['coverage'],original['coverage'])
            self.assertEqual(actual['members'],original.get('members',catalog[original['id']]['members']))
            self.assertEqual(actual['marketCapAsOf'],original.get('marketCapAsOf',saved['marketCapAsOf']))
        self.assertEqual(result['daily'][incoming_date]['membershipAsOf'],incoming_date)
        self.assertEqual(result['daily'][incoming_date]['basketDefinitionVersion'],'test-new-version')

    def test_history_fixture_survives_rolling_window_and_daily_order(self):
        payload=json.loads((R/'data/korea-market.json').read_text())
        themes=copy.deepcopy(payload['themes'])
        real_days=[d for d,v in themes['daily'].items() if v.get('rows')]
        self.assertTrue(real_days)
        # Reproduce a rolling window dropping the earliest real observation.
        if len(real_days)>1:
            themes['daily'].pop(min(real_days))
        remaining=list(themes['daily'].items())
        for ordered in (remaining,list(reversed(remaining))):
            with self.subTest(order=[d for d,_ in ordered]):
                themes['daily']=dict(ordered)
                self.assert_membership_change_preserves_snapshot(themes)

    def test_snapshot_rows_override_current_catalog_cap_date(self):
        payload=json.loads((R/'data/korea-market.json').read_text())
        section=next(v for v in payload['themes']['daily'].values() if v.get('rows'))
        catalog={b['id']:b for b in payload['themes']['baskets']}
        for row in section['rows']:
            prior=row.get('members',catalog[row['id']]['members'])
            row['members']=copy.deepcopy(prior)
            row['marketCapAsOf']='2026-10-15'
            for member in row['members']:member['marketCapAsOf']='2026-10-15'
        self.assertEqual(validate(payload),[])

if __name__=='__main__':unittest.main()
