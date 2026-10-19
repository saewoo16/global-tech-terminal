"""A newer membership/cap catalog must not change stored historical observations."""
import copy
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
        prior=copy.deepcopy(payload['themes'])
        date=next(d for d,v in prior['daily'].items() if v.get('rows'))
        saved=copy.deepcopy(prior['daily'][date])
        catalog={b['id']:b for b in prior['baskets']}
        responses={}
        for market,code in [('KOSPI','005930'),('KOSDAQ','247540')]:
            for investor in ['FOREIGNER','ORGANIZATION']:
                for period in ['DAY','WEEK','MONTH']:
                    responses[f'{market}_{investor}_{period}']={'url':'https://stock.naver.com/api/test','data':{'sections':{
                        'buyRankList':[{'type':'ST','itemcode':code,'accTradeAmount':'123456000','bizdateFrom':'20261020','bizdateTo':'20261020','estimated':False}], 'sellRankList':[]}}}
        incoming=build(responses=responses)
        incoming['basketDefinitionVersion']='test-new-version'
        incoming['membershipAsOf']='2026-10-20'
        incoming['marketCapAsOf']='2026-10-20'
        result=normalize(incoming,[date,'2026-10-20'],prior)
        historical=result['daily'][date]
        self.assertEqual(historical['basketDefinitionVersion'],saved['basketDefinitionVersion'])
        self.assertEqual(historical['marketCapAsOf'],saved['marketCapAsOf'])
        for actual,original in zip(historical['rows'],saved['rows']):
            self.assertEqual(actual['coverage'],original['coverage'])
            self.assertEqual(actual['members'],original.get('members',catalog[original['id']]['members']))
            self.assertEqual(actual['marketCapAsOf'],original.get('marketCapAsOf',saved['marketCapAsOf']))
        self.assertEqual(result['daily']['2026-10-20']['membershipAsOf'],'2026-10-20')

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
