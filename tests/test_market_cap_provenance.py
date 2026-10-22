import ast
import unittest
from pathlib import Path
from urllib.parse import quote

class MarketCapProvenanceTest(unittest.TestCase):
    def test_new_provider_cap_replaces_old_calculation_metadata(self):
        path = Path(__file__).resolve().parents[1]/'scripts/update_data.py'
        tree = ast.parse(path.read_text())
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'replace_market_cap')
        scope = {'quote': quote}
        exec(compile(ast.Module(body=[fn], type_ignores=[]), str(path), 'exec'), scope)
        old = dict(marketCapUSD=1, marketCapAsOf='2026-10-16', marketCapLocal=100,
                   marketCapFX=10, marketCapMethod='closing_price_times_issued_shares',
                   marketCapSource='issuer calculation', marketCapSourceUrl='https://old.example',
                   financialVerifiedAt='2026-10-17', prices=[['2026-10-20', 100]])
        scope['replace_market_cap'](old, 384424892.1, '108320.KS', '2026-10-20T22:19:15+00:00')
        self.assertEqual(old['marketCapUSD'], 384424892)
        for key in ('marketCapAsOf', 'marketCapLocal', 'marketCapFX', 'marketCapMethod'):
            self.assertNotIn(key, old)
        self.assertEqual(old['financialVerifiedAt'], '2026-10-17')
        self.assertEqual(old['prices'], [['2026-10-20', 100]])
        self.assertEqual(old['marketCapSourceUrl'], 'https://finance.yahoo.com/quote/108320.KS/')
        self.assertIn('not a certified', old['marketCapSource'])
