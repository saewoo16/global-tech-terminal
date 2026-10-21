import copy
import json
import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from apply_financial_backfills import apply

class October21FinancialBackfillTests(unittest.TestCase):
    def test_vat_partial_disclosure_remains_partial_and_preserves_prior(self):
        snapshot=json.loads((ROOT/'data/financial_backfill_zlatest_20261021.json').read_text())
        prior={'date':'2026-06-30','revenue':291.0,'operatingIncome':None,'operatingIncomeNotDisclosed':True,'sourceType':'filing'}
        initial={'stocks':{'SIX:VACN':{'quarters':[prior]},'NASDAQ:OTHER':{'quarters':[]}}}
        result=apply(copy.deepcopy(initial),[snapshot])
        item=result['stocks']['SIX:VACN'];q=item['quarters'][0]
        self.assertEqual((q['date'],q['revenue']),('2026-09-30',376.4))
        self.assertIsNone(q['operatingIncome'])
        self.assertTrue(q['operatingIncomeNotDisclosed'])
        self.assertEqual(item['financialStatus'],'not_disclosed')
        self.assertEqual(item['quarters'][1]['revenue'],291.0)
        self.assertEqual(item['financialVerifiedAt'],'2026-10-21')
        self.assertEqual(result,apply(copy.deepcopy(result),[snapshot]))

    def test_six_company_source_snapshot_keeps_original_verification_date(self):
        snapshot=json.loads((ROOT/'data/financial_backfill_zlatest_20261018.json').read_text())
        self.assertEqual(snapshot['asOf'],'2026-10-18')
        self.assertEqual(snapshot['recheckedAt'],'2026-10-21')
        self.assertEqual(sum(len(c['quarters']) for c in snapshot['companies'].values()),19)
        for c in snapshot['companies'].values():
            for q in c['quarters']:
                self.assertEqual(q['verifiedAt'],'2026-10-18')
                for metric in ('revenue','operatingIncome'):
                    self.assertEqual(q['sourceFacts'][metric]['value'],q[metric])
