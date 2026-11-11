import unittest, sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import patch_japan_financials as japan

class OfficialOnlyPublication(unittest.TestCase):
    def test_scheduled_japan_step_cannot_fetch_or_write_unverified_quarters(self):
        with patch.object(japan, 'collect_research_candidates') as collect, patch.object(japan, 'write_json') as write, patch.object(japan.yf, 'Ticker') as ticker:
            japan.main()
            collect.assert_not_called()
            write.assert_not_called()
            ticker.assert_not_called()

    def test_himx_official_quarter(self):
        import json
        root=Path(__file__).resolve().parents[1]
        snapshot=json.loads((root/'data/financial_backfill_us_20261111.json').read_text())
        q=snapshot['companies']['NASDAQ:HIMX']['quarters'][0]
        self.assertEqual(q['date'], '2026-09-30')
        self.assertEqual(q['revenue'], 246.752)
        self.assertEqual(q['operatingIncome'], 22.737)
        self.assertEqual(q['publishedAt'], '2026-11-05T06:35:00-05:00')
        self.assertIn('interim disclosures', q['basis'])
        self.assertEqual(len(q['sourceSha256']), 64)

    def test_japan_direct_and_derived_quarters_keep_scope(self):
        import json
        root=Path(__file__).resolve().parents[1]
        j=json.loads((root/'data/financial_backfill_japan_20261111.json').read_text())['companies']
        a=j['TSE:3436']['quarters'][0]; b=j['TSE:4004']['quarters'][0]
        self.assertEqual((a['revenue'],a['operatingIncome']),(332524-215016,-4397-(-6363)))
        self.assertEqual((b['revenue'],b['operatingIncome']),(325100,78000))
        self.assertIn('not directly comparable',b['comparabilityNote'])
        self.assertIn('0.1 billion',b['sourcePrecision'])

    def test_reference_fx_uses_gated_daily_source(self):
        import ast
        root=Path(__file__).resolve().parents[1]
        source=(root/'scripts/update_data.py').read_text()
        tree=ast.parse(source)
        funcs={n.name:ast.get_source_segment(source,n) for n in tree.body if isinstance(n,ast.FunctionDef)}
        self.assertIn('completed_daily_points(result, now)',funcs['completed_fx_observation'])
        self.assertIn('completed_fx_observation()',funcs['main'])
        self.assertNotIn("yf.Ticker('KRW=X').history",funcs['main'])
        self.assertIn("payload['fxMetadata'] = fx_metadata",funcs['main'])

    def test_fx_excludes_unfinished_session(self):
        import datetime as dt, io, json
        import update_data as updater
        begin=dt.datetime(2026,11,11,tzinfo=dt.timezone.utc)
        end=begin+dt.timedelta(days=1)
        result={'meta':{'exchangeTimezoneName':'UTC','currentTradingPeriod':{'regular':{'start':int(begin.timestamp()),'end':int(end.timestamp())}}},'timestamp':[int((begin-dt.timedelta(days=1)).timestamp()),int(begin.timestamp())],'indicators':{'adjclose':[{'adjclose':[1342.37,9999]}]}}
        body=json.dumps({'chart':{'result':[result]}}).encode()
        with patch.object(updater,'urlopen',return_value=io.BytesIO(body)):
            value, metadata=updater.completed_fx_observation(begin+dt.timedelta(hours=22))
        self.assertEqual(value,1342.37)
        self.assertEqual(metadata['asOf'],'2026-11-10')
        self.assertEqual(metadata['observedAt'],'2026-11-11T22:00:00+00:00')
