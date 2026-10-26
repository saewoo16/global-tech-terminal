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
    self.assertIn('CFD',m.INVESTING['DXY']['quoteLabel']);self.assertNotIn('DTWEXBGS',m.FRED)
 def test_restricted_ice_series_excluded(self):
    self.assertFalse(any(k.startswith('BAML') for k in m.FRED))
 def test_money_supply_monthly_release_metadata(self):
    for key in ['M1SL','M2SL']:
     row=m.parse_fred('observation_date,'+key+'\n2026-08-01,19991.1\n',key,NOW)
     row=m.add_fred_release_metadata(row,'{"dateModified":"2026-09-22T12:01:00-05:00"}',NOW)
     self.assertEqual(row['asOf'],'2026-08-01');self.assertEqual(row['frequency'],'monthly')
     self.assertEqual(row['sourceUpdatedAt'],'2026-09-22T17:01:00Z');self.assertEqual(row['unit'],'십억 달러')
     self.assertEqual(row['seasonalAdjustment'],'seasonally_adjusted')
     failed=m.preserve_failure(row,key,ValueError('source failed'),NOW)
     for field in ['asOf','sourceUpdatedAt','retrievedAt','value']:self.assertEqual(failed[field],row[field])
 def test_money_supply_source_metadata_rejects_missing_future_and_inconsistent(self):
    row=m.parse_fred('observation_date,M1SL\n2026-08-01,19991.1\n','M1SL',NOW)
    for html in ['', '{"dateModified":"2026-11-01T12:01:00-05:00"}', '{"dateModified":"2026-07-01T12:01:00-05:00"}']:
     with self.assertRaises(ValueError):m.add_fred_release_metadata(row,html,NOW)
 def test_snapshot_integrity(self):
    p=json.loads((ROOT/'data/macro_quotes.json').read_text());ids=[r['id'] for r in p['rows']]
    self.assertEqual(set(ids),set(m.INVESTING)|set(m.FRED));self.assertEqual(len(ids),len(set(ids)))
    for row in p['rows']:
     self.assertTrue(row['sourceUrl'].startswith('https://'));self.assertIn(row['status'],('verified','stale','unavailable'))
     if row['value'] is not None:self.assertGreater(row['value'],0);self.assertLessEqual(row['asOf'],row['retrievedAt'][:10])


# Collection tests use synthetic HTTP failures only: no network calls.
from copy import deepcopy
from contextlib import redirect_stdout
from io import StringIO
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlparse
from http.client import IncompleteRead

COLLECTION_NOW = datetime(2026, 10, 26, 12, tzinfo=timezone.utc)

class MacroCollectionSafetyTests(unittest.TestCase):
 def setUp(self):
    # Fixed synthetic observations keep regression tests independent of live refreshes.
    rows=[]
    for key,spec in m.INVESTING.items():
     rows.append(m.parse_investing(html(instrument_id=spec['instrumentId'],path='/'+spec['path']),key,NOW))
    for key in m.FRED:
     day='2026-08-01' if key in m.MONTHLY else '2026-10-22'
     row=m.parse_fred(f'observation_date,{key}\n{day},5.0\n',key,NOW)
     if key in m.MONEY_SUPPLY:
      row=m.add_fred_release_metadata(row,'{"dateModified":"2026-09-22T12:01:00-05:00"}',NOW)
     rows.append(row)
    self.previous={'schemaVersion':1,'updatedAt':m.iso(NOW),'rows':rows}
    self.original=deepcopy(self.previous)

 @staticmethod
 def unavailable(url):
    raise m.SourceUnavailable('HTTP 503\n provider unavailable')

 def success(self,url):
    if '/series/' in url:
     return '{"dateModified":"2026-09-22T12:01:00-05:00"}'
    if 'fredgraph.csv' in url:
     key=parse_qs(urlparse(url).query)['id'][0]
     old=next(r for r in self.previous['rows'] if r['id']==key)
     return f'observation_date,{key}\n{old["asOf"]},{old["value"]}\n'
    key=next(k for k,s in m.INVESTING.items() if url.endswith(s['path']))
    s=m.INVESTING[key]
    old=next(r for r in self.previous['rows'] if r['id']==key)
    return html(instrument_id=s['instrumentId'],value=old['value'],timestamp=old['sourceObservation']['lastUpdateTime'],path='/'+s['path'])

 def test_all_transport_failures_preserve_complete_snapshot_and_dates(self):
    candidate=m.collect(self.previous,self.unavailable,COLLECTION_NOW)
    self.assertEqual(candidate['collectionStatus'],'source_unavailable')
    self.assertEqual(candidate['verifiedCount'],0)
    self.assertEqual(candidate['staleCount'],14)
    for old,row in zip(self.previous['rows'],candidate['rows']):
     # Collector uses registry order, which may differ from historical JSON order.
     old=next(r for r in self.previous['rows'] if r['id']==row['id'])
     self.assertEqual(row['status'],'stale')
     self.assertEqual(row['lastAttemptAt'],m.iso(COLLECTION_NOW))
     self.assertNotIn('\n',row['error'])
     for key,value in old.items():
      if key not in ('status','lastAttemptAt','error'):self.assertEqual(row[key],value,key)
    self.assertEqual(self.previous,self.original)
    m.validate_snapshot(candidate,COLLECTION_NOW)

 def test_partial_transport_failure_keeps_failed_row_and_refreshes_others(self):
    def fetch(url):
     if url.endswith(m.INVESTING['UST10Y']['path']):return self.unavailable(url)
     return self.success(url)
    candidate=m.collect(self.previous,fetch,COLLECTION_NOW)
    self.assertEqual((candidate['collectionStatus'],candidate['verifiedCount'],candidate['staleCount']),('partial',13,1))
    failed=next(r for r in candidate['rows'] if r['id']=='UST10Y')
    self.assertEqual(failed['retrievedAt'],self.previous['rows'][0]['retrievedAt'])
    self.assertTrue(all(r['retrievedAt']==m.iso(COLLECTION_NOW) for r in candidate['rows'] if r['status']=='verified'))

 def test_success_after_stale_removes_old_failure_metadata(self):
    stale=m.collect(self.previous,self.unavailable,COLLECTION_NOW)
    candidate=m.collect(stale,self.success,COLLECTION_NOW)
    self.assertEqual((candidate['collectionStatus'],candidate['verifiedCount'],candidate['staleCount']),('complete',14,0))
    for row in candidate['rows']:
     self.assertEqual(row['status'],'verified')
     self.assertNotIn('error',row)
     self.assertNotIn('lastAttemptAt',row)

 def test_initial_collection_requires_success_for_every_series(self):
    with self.assertRaises(m.SourceUnavailable):m.collect(None,self.unavailable,COLLECTION_NOW)
    candidate=m.collect(None,self.success,COLLECTION_NOW)
    self.assertEqual(candidate['verifiedCount'],14)

 def test_bad_prior_snapshot_rejected_before_network(self):
    mutations=[lambda p:p['rows'].pop(),lambda p:p['rows'].append(deepcopy(p['rows'][0])),lambda p:p['rows'][0].update(id='UNKNOWN'),lambda p:p['rows'][1].update(id=p['rows'][0]['id']),lambda p:p.update(schemaVersion=2)]
    for mutate in mutations:
     bad=deepcopy(self.previous);mutate(bad);fetch=Mock(side_effect=self.unavailable)
     with self.subTest(bad=bad.get('schemaVersion')):
      with self.assertRaises(ValueError):m.collect(bad,fetch,COLLECTION_NOW)
      fetch.assert_not_called()

 def test_invalid_retained_values_metadata_and_dates_fail_closed(self):
    for change in [{'value':True},{'value':'4.988'},{'value':float('nan')},{'value':0},{'sourceUrl':'https://example.com/wrong'},{'unit':'USD'},{'status':'unavailable'},{'asOf':'2026-10-27'},{'retrievedAt':'2026-10-25T07:29:44'},{'observedAt':'2026-10-23T20:59:58Z'}]:
     bad=deepcopy(self.previous);bad['rows'][0].update(change)
     with self.subTest(change=change):
      with self.assertRaises(ValueError):m.validate_snapshot(bad,COLLECTION_NOW)

 def test_invalid_fred_month_and_release_metadata_fail_closed(self):
    for key,change in [('M1SL',{'asOf':'2026-08-02'}),('M2SL',{'sourceUpdatedAt':'2026-11-01T00:00:00Z'}),('DGS10',{'observedAt':'2026-10-22T12:00:00Z'}),('M1SL',{'seasonalAdjustment':'unadjusted'})]:
     bad=deepcopy(self.previous);next(r for r in bad['rows'] if r['id']==key).update(change)
     with self.subTest(key=key,change=change):
      with self.assertRaises(ValueError):m.validate_snapshot(bad,COLLECTION_NOW)

 def test_source_integrity_and_programming_errors_are_never_degraded(self):
    for error in [ValueError('wrong instrument'),KeyError('payload'),RuntimeError('programming error'),OSError('local error')]:
     with self.subTest(error=type(error).__name__):
      with self.assertRaises(ValueError):m.collect(self.previous,Mock(side_effect=error),COLLECTION_NOW)
    with self.assertRaises(ValueError):m.collect(self.previous,lambda url:'<html>unavailable</html>',COLLECTION_NOW)

 def test_source_regression_is_fatal_even_if_other_series_succeed(self):
    def fetch(url):
     if url.endswith(m.INVESTING['UST10Y']['path']):return html(timestamp='1792702799000')
     return self.success(url)
    with self.assertRaisesRegex(ValueError,'regressed'):m.collect(self.previous,fetch,COLLECTION_NOW)

 def test_http_and_transport_errors_are_classified(self):
    for error in [HTTPError('https://example.com',503,'Unavailable',{},None),URLError('timeout'),TimeoutError('timeout'),ConnectionError('reset'),IncompleteRead(b'partial',10)]:
     with self.subTest(error=type(error).__name__),patch.object(m,'urlopen',side_effect=error):
      with self.assertRaises(m.SourceUnavailable):m.fetch_text('https://example.com')

 def test_decode_size_and_programming_errors_are_not_transport(self):
    for body,error in [(b'\xff',UnicodeDecodeError),(b'x'*5_000_001,ValueError)]:
     response=Mock();response.status=200;response.read.return_value=body
     context=Mock();context.__enter__=Mock(return_value=response);context.__exit__=Mock(return_value=False)
     with patch.object(m,'urlopen',return_value=context):
      with self.assertRaises(error):m.fetch_text('https://example.com')
    with patch.object(m,'urlopen',side_effect=RuntimeError('bug')):
     with self.assertRaises(RuntimeError):m.fetch_text('https://example.com')

 def test_main_degraded_exit_is_explicit_and_preserves_observation_dates(self):
    candidate=m.collect(self.previous,self.unavailable,COLLECTION_NOW)
    with TemporaryDirectory() as directory:
     path=Path(directory)/'macro.json';path.write_text(json.dumps(self.previous))
     output=StringIO()
     with patch.object(m,'collect',return_value=candidate),redirect_stdout(output):
      self.assertEqual(m.main(['--output',str(path)]),0)
     self.assertEqual(json.loads(path.read_text()),candidate)
     log=output.getvalue();self.assertIn('source_unavailable',log);self.assertIn('verified: 0/14',log);self.assertIn('retained: 14',log)
     self.assertEqual(log.count('MACRO_SOURCE_UNAVAILABLE '),14)
     self.assertIn('WARNING',log)

 def test_aggregate_metadata_and_integer_types_are_strict(self):
    valid=m.collect(self.previous,self.unavailable,COLLECTION_NOW)
    mutations=[
     lambda p:p.update(collectionStatus='complete'),
     lambda p:p.update(verifiedCount=14),
     lambda p:p.update(staleCount=0),
     lambda p:p.pop('collectionStatus'),
     lambda p:p.pop('verifiedCount'),
     lambda p:p.pop('staleCount'),
     lambda p:p.update(verifiedCount=False),
     lambda p:p.update(staleCount=14.0),
     lambda p:p.update(schemaVersion=True),
     lambda p:next(r for r in p['rows'] if r['id']=='M1SL').update(precision=True),
    ]
    for index,mutate in enumerate(mutations):
     candidate=deepcopy(valid);mutate(candidate)
     with self.subTest(case=index):
      with self.assertRaises(ValueError):m.validate_snapshot(candidate,COLLECTION_NOW)
    m.validate_snapshot(valid,COLLECTION_NOW)
    # Historical snapshots without new aggregate metadata remain supported.
    m.validate_snapshot(self.previous,COLLECTION_NOW)

 def test_main_integrity_error_does_not_replace_file(self):
    with TemporaryDirectory() as directory:
     path=Path(directory)/'macro.json';path.write_text(json.dumps(self.previous));before=path.read_bytes()
     with patch.object(m,'collect',side_effect=ValueError('invalid source')):
      with self.assertRaises(ValueError):m.main(['--output',str(path)])
     self.assertEqual(path.read_bytes(),before)
     self.assertFalse(path.with_suffix('.tmp').exists())

if __name__=='__main__':unittest.main()
