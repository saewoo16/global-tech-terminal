import copy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from update_korean_market import direct_official_credit_splits,collect_liquidity,CHUN,LATEST,RECENT

RELEASE={'date':'2026-10-20','officialMarginLoans':30513862,'url':'https://freesis.kofia.or.kr/stat/main.do','unit':'million KRW'}
BALANCE={'kospiList':[{'stdDate':'2026-10-20','sinyong':'23694349'}], 'kosdaqList':[{'stdDate':'2026-10-20','sinyong':'6819513'}]}

class DirectOfficialCredit(unittest.TestCase):
    def test_actual_values_and_no_deposit_change(self):
        old=copy.deepcopy(BALANCE);rows=direct_official_credit_splits(BALANCE,RELEASE)
        self.assertEqual(BALANCE,old);self.assertNotIn('deposits',rows)
        self.assertEqual(rows['creditKOSPI'][0]['value'],236943.49)
        self.assertEqual(rows['creditKOSDAQ'][0]['rawMillionKRW'],6819513)
        self.assertEqual(rows['creditKOSPI'][0]['splitMinusOfficialMillionKRW'],0)
    def test_missing_or_wrong_date_never_inferred(self):
        for data in ({'kospiList':BALANCE['kospiList']}, {'kospiList':BALANCE['kospiList'],'kosdaqList':[{'stdDate':'2026-10-19','sinyong':'6819513'}]}):
            self.assertFalse(any(direct_official_credit_splits(data,RELEASE).values()))
    def test_duplicate_noninteger_zero_rejected(self):
        for value in ('0','-1','23694349.5',True):
            data=copy.deepcopy(BALANCE);data['kospiList'][0]['sinyong']=value
            with self.assertRaises(ValueError):direct_official_credit_splits(data,RELEASE)
        data=copy.deepcopy(BALANCE);data['kospiList']*=2
        with self.assertRaises(ValueError):direct_official_credit_splits(data,RELEASE)
    def test_mismatch_and_tolerance(self):
        self.assertFalse(any(direct_official_credit_splits(BALANCE,dict(RELEASE,officialMarginLoans=30513865)).values()))
        self.assertTrue(all(direct_official_credit_splits(BALANCE,dict(RELEASE,officialMarginLoans=30513863)).values()))
    def test_mirror_lag_does_not_hide_direct_verified_row(self):
        responses={CHUN:json.dumps(BALANCE),LATEST:'{"as_of":"2026-10-19"}',RECENT:'date,source,investor_deposit,margin_loan\n2026-10-19,kofia_api,92.096622,31.108258\n'}
        with patch('update_korean_market.fetch',side_effect=lambda url:responses[url]):rows=collect_liquidity(RELEASE)
        self.assertEqual(rows['creditKOSPI'][-1]['date'],'2026-10-20')
        self.assertEqual(rows['deposits'][-1]['date'],'2026-10-19')
    def test_mirror_failure_only_allows_direct_verified_pair(self):
        def fetch(url):
            if url==CHUN:return json.dumps(BALANCE)
            raise ValueError('mirror unavailable')
        with patch('update_korean_market.fetch',side_effect=fetch):
            self.assertEqual(collect_liquidity(RELEASE)['deposits'],[])
            with self.assertRaises(ValueError):collect_liquidity()
            with self.assertRaises(ValueError):collect_liquidity(dict(RELEASE,officialMarginLoans=1))
    def test_unverified_source_and_units_rejected(self):
        for release in (dict(RELEASE,url='https://example.com'),dict(RELEASE,unit='억원')):
            with self.assertRaises(ValueError):direct_official_credit_splits(BALANCE,release)
