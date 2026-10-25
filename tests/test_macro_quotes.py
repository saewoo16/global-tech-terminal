import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('macro_quotes',ROOT/'scripts/update_macro_quotes.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
NOW=datetime(2026,10,25,7,30,tzinfo=timezone.utc)

def html(instrument_id='23705',value=4.988,timestamp='1792789199000',path='/rates-bonds/u.s.-10-year-bond-yield'):
    instrument={'base':{'id':instrument_id,'path':path,'isOpen':False,'isCfd':False},'price':{'last':value,'lastUpdateTime':timestamp},'name':{'fullName':'United States 10-Year'},'exchange':{'exchange':'NYSE'}}
    return '<script id="__NEXT_DATA__" type="application/json">'+json.dumps({'props':{'pageProps':{'state':{'bondStore':{'instrument':instrument}}}}})+'</script>'

class MacroQuotesTests(unittest.TestCase):
 def test_source_timestamp_not_collection_date(self):
    row=m.parse_investing(html(),'UST10Y',NOW)
    self.assertEqual(row['asOf'],'2026-10-23');self.assertEqual(row['observedAt'],'2026-10-23T20:59:59Z');self.assertEqual(row['retrievedAt'],'2026-10-25T07:30:00Z')
 def test_wrong_instrument_and_future_timestamp_rejected(self):
    for source in [html(instrument_id='650'),html(timestamp='9999999999999'),html(path='/wrong')]:
     with self.assertRaises(ValueError):m.parse_investing(source,'UST10Y',NOW)
 def test_invalid_and_missing_values_rejected(self):
    for value in [0,-1,float('nan'),True]:
     with self.assertRaises(ValueError):m.parse_investing(html(value=value),'UST10Y',NOW)
    with self.assertRaises(ValueError):m.parse_investing('<html>unavailable</html>','UST10Y',NOW)
 def test_fred_skips_missing_and_does_not_invent_time(self):
    row=m.parse_fred('observation_date,DGS10\n2026-10-22,4.96\n2026-10-23,\n','DGS10',NOW)
    self.assertEqual(row['value'],4.96);self.assertEqual(row['asOf'],'2026-10-22');self.assertIsNone(row['observedAt'])
 def test_source_failure_preserves_value_and_original_dates(self):
    old=m.parse_investing(html(),'UST10Y',NOW)
    row=m.preserve_failure(old,'UST10Y',ValueError('bad source'),NOW)
    for key in ['value','asOf','observedAt','retrievedAt']:self.assertEqual(old[key],row[key])
    self.assertEqual(row['status'],'stale');self.assertEqual(old['status'],'verified')
 def test_futures_and_spot_and_dollar_indices_not_conflated(self):
    self.assertNotEqual(m.INVESTING['WTI_FUTURES']['quoteLabel'],m.FRED['DCOILWTICO'][0])
    self.assertEqual(m.INVESTING['DXY']['path'],'indices/usdollar')
    self.assertIn('CFD',m.INVESTING['DXY']['quoteLabel']);self.assertIn('광의',m.FRED['DTWEXBGS'][0])
 def test_restricted_ice_series_excluded(self):
    self.assertFalse(any(k.startswith('BAML') for k in m.FRED))
 def test_snapshot_integrity(self):
    p=json.loads((ROOT/'data/macro_quotes.json').read_text());ids=[r['id'] for r in p['rows']]
    self.assertEqual(set(ids),set(m.INVESTING)|set(m.FRED));self.assertEqual(len(ids),len(set(ids)))
    for row in p['rows']:
     self.assertTrue(row['sourceUrl'].startswith('https://'));self.assertIn(row['status'],('verified','stale','unavailable'))
     if row['value'] is not None:self.assertGreater(row['value'],0);self.assertLessEqual(row['asOf'],row['retrievedAt'][:10])

if __name__=='__main__':unittest.main()
