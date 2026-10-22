import copy
import json
import sys
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from apply_financial_backfills import apply

class LamOctoberBackfillTest(unittest.TestCase):
    def test_official_september_quarter_preserves_quote_and_other_company(self):
        snapshot=json.loads((ROOT/'data/financial_backfill_zlatest_20261022.json').read_text())
        q=snapshot['companies']['NASDAQ:LRCX']['quarters'][0]
        self.assertEqual(q['date'], '2026-09-27')
        self.assertEqual(q['revenue'], 8219.418)
        self.assertEqual(q['operatingIncome'], 3283.727)
        old={'stocks':{'NASDAQ:LRCX':{'prices':[['2026-10-20',263.45001]],'lastPriceDate':'2026-10-20','marketCapUSD':329687760896,'quarters':[]}}}
        before=copy.deepcopy(old['stocks']['NASDAQ:LRCX'])
        result=apply(old,[snapshot])['stocks']['NASDAQ:LRCX']
        for k in ('prices','lastPriceDate','marketCapUSD'):
            self.assertEqual(result[k],before[k])
        self.assertEqual(result['financialVerifiedAt'],'2026-10-22')
        self.assertEqual(result['quarters'][0]['publishedAt'],'2026-10-21')
