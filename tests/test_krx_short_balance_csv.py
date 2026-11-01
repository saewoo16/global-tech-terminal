import csv
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import import_krx_short_balance_csv as importer


class KRXCSVTests(unittest.TestCase):
    def make_manifest(self, root, dates=('2026-09-28', '2026-10-21', '2026-10-28')):
        snapshots = []
        for d in dates:
            for market in ('KOSPI', 'KOSDAQ'):
                p = root / f'{market}-{d}.csv'
                with p.open('w', encoding='cp949', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(importer.HEADERS)
                    for i in range(15):
                        code = str(i + (0 if market == 'KOSPI' else 15)).zfill(6)
                        if i == 0 and market == 'KOSPI': code = '0009K0'
                        writer.writerow([code, '테스트 종목', '10', '100', '1000', '10000', '10.00'])
                snapshots.append({'market': market, 'date': d, 'observedAt': '2026-11-01T07:53:03Z', 'path': p.name, 'sourceUrl': 'https://data.krx.co.kr/contents/MDC/MDI/mdiLoader/index.cmd?menuId=MDC0203', 'expectedRows': 15})
        return {'snapshots': snapshots}

    def test_decode_precision_and_history(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            payload = importer.build(self.make_manifest(root), root)
            self.assertEqual(payload['asOf'], '2026-10-28')
            self.assertEqual(payload['coverage']['count'], 30)
            self.assertEqual(payload['rows'][0]['code'], '0009K0')
            self.assertEqual(payload['rows'][0]['ratioPct'], '10.00')
            self.assertEqual(payload['rows'][0]['balanceShares'], '10')
            self.assertEqual([p['date'] for p in payload['rows'][1]['history']], ['2026-09-28', '2026-10-21'])
            self.assertEqual(len(payload['sources'][0]['sha256']), 64)

    def test_only_exact_ranking_union_embeds_history(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            payload = importer.build(self.make_manifest(root), root)
            selected = importer.ranking_codes(payload['rows'])
            self.assertEqual(payload['coverage']['historyScope'], 'current-ranking-union')
            self.assertEqual(payload['coverage']['historySecurityCount'], len(selected))
            self.assertEqual({r['code'] for r in payload['rows'] if r['history']}, selected)
            self.assertEqual(len(payload['rows']), 30)
            # Both metric ties are resolved deterministically by security code.
            self.assertEqual(selected, set(sorted(r['code'] for r in payload['rows'])[:15]))
            self.assertEqual(sum(len(r['history']) for r in payload['rows']), 30)

    def test_missing_market_and_wrong_count(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); manifest = self.make_manifest(root)
            manifest['snapshots'].pop()
            with self.assertRaises(ValueError): importer.build(manifest, root)
            manifest = self.make_manifest(root)
            manifest['snapshots'][0]['expectedRows'] = 16
            with self.assertRaises(ValueError): importer.build(manifest, root)

    def test_source_universe_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); manifest = self.make_manifest(root)
            p = root / 'KOSPI-2026-09-28.csv'
            text = p.read_text(encoding='cp949').replace('000001,', '999999,')
            p.write_text(text, encoding='cp949')
            payload = importer.build(manifest, root)
            self.assertFalse(any(r['code'] == '999999' for r in payload['rows']))
            current = next(r for r in payload['rows'] if r['code'] == '000001')
            self.assertEqual([h['date'] for h in current['history']], ['2026-10-21'])

    def test_reject_wrong_units(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); manifest = self.make_manifest(root)
            p = root / 'KOSPI-2026-09-28.csv'
            text = p.read_text(encoding='cp949').replace(',1000,10000,', ',1,10000,')
            p.write_text(text, encoding='cp949')
            with self.assertRaises(ValueError): importer.build(manifest, root)


if __name__ == '__main__': unittest.main()
