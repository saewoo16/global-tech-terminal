import copy
import json
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from data_quality import annotate, clean_prices, merge_quarters, migrate_symbols, number
from apply_financial_backfills import apply
from audit_coverage import audit, regressions


class DataQualityTests(unittest.TestCase):
    def test_finite_numbers(self):
        for value in (None, True, 'bad', float('nan'), float('inf')):self.assertIsNone(number(value))
        self.assertEqual(number(0),0)
        self.assertEqual(number(-2),-2)

    def test_prices_valid_sorted_unique(self):
        self.assertEqual(clean_prices([['2026-01-02',2],['2026-01-01',1],['2026-01-02',3],['2026-01-03',0],['2099-01-01',1],['bad',4]]),[['2026-01-01',1.0],['2026-01-02',3.0]])

    def test_missing_feed_never_erases_existing(self):
        previous=[{'date':'2026-06-30','revenue':1,'operatingIncome':-2}]
        self.assertEqual(merge_quarters(previous,[{'date':'2026-06-30','revenue':None,'operatingIncome':None}]),previous)

    def test_null_operating_preserves_verified(self):
        previous=[{'date':'2026-06-30','revenue':1,'operatingIncome':2,'sourceType':'filing','sourceUrl':'https://example.com/filing'}]
        self.assertEqual(merge_quarters(previous,[{'date':'2026-06-30','revenue':1,'operatingIncome':None}]),previous)

    def test_latest_real_period_retained(self):
        previous=[{'date':d,'revenue':1,'operatingIncome':2} for d in ['2026-03-31','2025-12-31','2025-09-30','2025-06-30']]
        merged=merge_quarters(previous,[{'date':'2026-06-30','revenue':2,'operatingIncome':None}])
        self.assertEqual(merged[0]['date'],'2026-06-30');self.assertEqual(len(merged),4)

    def test_disclosure_exception_stays_missing(self):
        q={'date':'2026-06-30','revenue':3,'operatingIncome':None,'operatingIncomeNotDisclosed':True,'sourceType':'filing'}
        self.assertIsNone(merge_quarters([{'date':'2026-06-30','revenue':3,'operatingIncome':10}],[q])[0]['operatingIncome'])
        self.assertEqual(annotate('EURONEXT:AI',{'quarters':[q]})['financialStatus'],'not_disclosed')

    def test_symbol_migration(self):
        stocks=migrate_symbols({'NYSE:FI':{'old':1},'NYSE:PSTG':{'old':2}})
        self.assertEqual(set(stocks),{'NASDAQ:FISV','NYSE:P'})

    def test_snapshot_idempotent_and_future_safe(self):
        market={'stocks':{'TEST:X':{'quarters':[{'date':'2026-09-30','revenue':3,'operatingIncome':4}]}}}
        snapshot={'asOf':'2026-10-13','companies':{'TEST:X':{'reportingCurrency':'USD','replaceQuarters':True,'quarters':[{'date':'2026-06-30','revenue':1,'operatingIncome':2,'sourceUrl':'https://example.com/filing'}]}}}
        a=apply(copy.deepcopy(market),[snapshot]);b=apply(copy.deepcopy(a),[snapshot])
        self.assertEqual(a,b);self.assertEqual(a['stocks']['TEST:X']['quarters'][0]['date'],'2026-09-30')
        self.assertEqual(a['stocks']['TEST:X']['financialVerifiedAt'],'2026-10-13')

    def test_normalized_calendar_date_cannot_duplicate_fiscal_quarter(self):
        market={'stocks':{'TEST:X':{'quarters':[{'date':'2026-06-30','revenue':999,'operatingIncome':999}]}}}
        snapshot={'asOf':'2026-10-17','companies':{'TEST:X':{'replaceQuarters':True,'reportingCurrency':'USD','quarters':[{'date':'2026-06-26','revenue':1,'operatingIncome':2,'sourceUrl':'https://example.com/filing'}]}}}
        result=apply(market,[snapshot])['stocks']['TEST:X']['quarters']
        self.assertEqual(len(result),1);self.assertEqual(result[0]['date'],'2026-06-26')

    def test_no_fake_verification_date(self):
        snapshot={'asOf':'2026-10-13','companies':{'TEST:X':{'reportingCurrency':'USD','quarters':[{'date':'2026-06-30','revenue':1,'operatingIncome':2,'sourceUrl':'https://example.com/filing'}]}}}
        item=apply({'stocks':{}},[snapshot])['stocks']['TEST:X']
        self.assertEqual(item['quarters'][0]['verifiedAt'],'2026-10-13')
        self.assertNotIn('financialUpdated',item)

    def test_regression_detection(self):
        baseline={'companies':[{'symbol':'NYSE:FI','chart_points':20,'market_cap':True,'complete_quarters':4}]}
        current={'companies':[{'symbol':'NASDAQ:FISV','chart_points':0,'market_cap':False,'complete_quarters':2,'financial_status':'partial'}]}
        self.assertEqual(len(regressions(current,baseline)),3)

    def test_corrected_exchange_mappings(self):
        import types
        from unittest.mock import patch
        with patch.dict(sys.modules,{'yfinance':types.ModuleType('yfinance')}):
            import update_data
        self.assertEqual(update_data.lookup({'symbol':'KRX:108320','ticker':'108320','country':'한국'}),'108320.KS')
        self.assertEqual(update_data.lookup({'symbol':'NASDAQ:FISV','ticker':'FISV','country':'미국'}),'FISV')
        self.assertEqual(update_data.lookup({'symbol':'NYSE:P','ticker':'P','country':'미국'}),'P')
        self.assertEqual(update_data.lookup({'symbol':'KRX:095340','ticker':'095340','country':'한국'}),'095340.KQ')

    def test_reported_operating_income_precedes_provider_normalization(self):
        import datetime as dt
        import types
        from unittest.mock import patch
        with patch.dict(sys.modules, {'yfinance': types.ModuleType('yfinance')}):
            import update_data
            import patch_japan_financials
        day = dt.date(2026, 6, 30)
        rows = {'Total Revenue': {day: 1000000},
                'Operating Income': {day: 200000},
                'Operating Income As Reported': {day: 125000}}
        frame = types.SimpleNamespace(index=rows, loc=rows, columns=[day], empty=False)
        ticker = types.SimpleNamespace(quarterly_income_stmt=frame)
        self.assertEqual(update_data.fetch_quarters(ticker)[0]['operatingIncome'], 0.125)
        self.assertEqual(patch_japan_financials.parse(frame)['2026-06-30']['operatingIncome'], 0.125)
        del rows['Operating Income As Reported']
        self.assertEqual(update_data.fetch_quarters(ticker)[0]['operatingIncome'], 0.2)
        self.assertEqual(patch_japan_financials.parse(frame)['2026-06-30']['operatingIncome'], 0.2)

    def test_october_filing_snapshot_is_source_backed_and_idempotent(self):
        root = Path(__file__).resolve().parents[1]
        snapshot = json.loads((root/'data/financial_backfill_zlatest_20261018.json').read_text())
        expected = {'NASDAQ:ASML': ('2026-09-27', 11662.0, 5172.8),
                    'NASDAQ:MU': ('2026-09-03', 54229.0, 43751.0),
                    'NYSE:JBL': ('2026-08-31', 10616.0, 602.0),
                    'NASDAQ:AEIS': ('2026-06-30', 574.1, 95.1),
                    'NYSE:TSM': ('2026-09-30', 1494243.0, 876445.0),
                    'TWSE:2408': ('2026-09-30', 133649.0, 106894.0)}
        self.assertEqual(set(snapshot['companies']), set(expected))
        market = {'stocks': {}}
        for symbol, record in snapshot['companies'].items():
            q = record['quarters'][0]
            self.assertEqual((q['date'], q['revenue'], q['operatingIncome']), expected[symbol])
            for q in record['quarters']:
                self.assertTrue(q['sourceUrl'].startswith('https://'))
                self.assertEqual(q['reportedCurrency'], record['reportingCurrency'])
                self.assertEqual(q['verifiedAt'], '2026-10-18')
                self.assertLess(q['periodStart'], q['date'])
        once = apply(copy.deepcopy(market), [snapshot])
        self.assertEqual(once, apply(copy.deepcopy(once), [snapshot]))
        for symbol in ['NASDAQ:ASML', 'NASDAQ:MU', 'NYSE:JBL', 'NASDAQ:AEIS']:
            self.assertEqual(len(once['stocks'][symbol]['quarters']), 4)
        jabil = once['stocks']['NYSE:JBL']['quarters']
        self.assertEqual(sum(q['revenue'] for q in jabil), 35954)
        self.assertEqual(sum(q['operatingIncome'] for q in jabil), 1704)

    def test_repository_company_coverage(self):
        root=Path(__file__).resolve().parents[1]
        companies=json.loads((root/'data/companies.json').read_text())
        market=json.loads((root/'data/market.json').read_text())
        report=audit(companies,market)
        self.assertEqual(report['summary']['companies'],246)
        self.assertEqual(report['errors'],[])


if __name__=='__main__':unittest.main()
