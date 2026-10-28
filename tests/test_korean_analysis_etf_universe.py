import copy, importlib.util, json, pathlib, unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('sync_etfs', ROOT/'scripts/sync_korean_analysis_etfs.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
class TestChartUniverse(unittest.TestCase):
 def setUp(self):
  self.market=json.loads((ROOT/'data/korea-market.json').read_text());self.charts=json.loads((ROOT/'data/korean_etf_charts.json').read_text())
 def test_full_universe_and_source_immutability(self):
  before=copy.deepcopy(self.charts);out=mod.sync(self.market,self.charts);self.assertEqual(self.charts,before)
  codes={r.get('ticker','').split('.')[0] for r in out['sectorReturns']['rows']};self.assertTrue({f['code'] for f in self.charts['funds']}<=codes)
  for field in self.market.keys()-{'sectorReturns','sources'}:self.assertEqual(out[field],self.market[field])
  self.assertEqual(mod.sync(out,self.charts),out)
 def test_preserve_newer_rows(self):
  market=copy.deepcopy(self.market);row=next(r for r in market['sectorReturns']['rows'] if r.get('ticker')=='091160.KS');row.update(asOf='2026-10-28',day=123.456);market['sectorReturns']['asOf']='2026-10-28'
  out=mod.sync(market,self.charts);new=next(r for r in out['sectorReturns']['rows'] if r.get('ticker')=='091160.KS');self.assertEqual(new['day'],123.456);self.assertEqual(new['calculation'],row['calculation'])
 def test_new_chart_rows_use_actual_calendar_boundaries(self):
  out=mod.sync(self.market,self.charts)
  for row in out['sectorReturns']['rows']:
   if not row.get('id','').startswith('chart-etf-'):continue
   fund=copy.deepcopy(next(f for f in self.charts['funds'] if f['code']==row['ticker'].split('.')[0]));fund['daily']=[d for d in fund['daily'] if d['date'] <= out['sectorReturns']['asOf']];self.assertEqual(row['asOf'],fund['daily'][-1]['date'])
   for key in ('day','week','month'):
    base=row['calculation']['bases'][key]
    if base is None:self.assertIsNone(row[key]);self.assertEqual(row['periodStatus'][key],'insufficient_history')
    else:self.assertAlmostEqual(row[key],(fund['daily'][-1]['close']/next(d['close'] for d in fund['daily'] if d['date']==base)-1)*100)
 def test_new_ipo_not_filled(self):
  charts=copy.deepcopy(self.charts);fund=next(f for f in charts['funds'] if f['code']=='0247S0');fund['daily']=fund['daily'][:10];market=copy.deepcopy(self.market);market['sectorReturns']['rows']=[r for r in market['sectorReturns']['rows'] if r.get('ticker')!='0247S0.KS'];out=mod.sync(market,charts);row=next(r for r in out['sectorReturns']['rows'] if r.get('ticker')=='0247S0.KS');self.assertIsNone(row['month']);self.assertEqual(row['periodStatus']['month'],'insufficient_history')
 def test_archive_only_matching_latest_kr_changes(self):
  archive=json.loads((ROOT/'data/briefings.json').read_text());market=mod.sync(self.market,self.charts);result=mod.sync_briefings(archive,market)
  latest=max(e['date'] for e in archive['entries'] if e['market']=='KR')
  for a,b in zip(archive['entries'],result['entries']):
   if a['market']!='KR' or a['date']!=latest:self.assertEqual(a,b)
   else:
    for k in a.keys()-{'sectors','sources'}:self.assertEqual(a[k],b[k])
 def test_future_chart_points_excluded_from_report(self):
  charts=copy.deepcopy(self.charts);fund=charts['funds'][0];point=copy.deepcopy(fund['daily'][-1]);point.update(date='2099-01-01',close=999999);fund['daily'].append(point)
  market=mod.sync(self.market,charts);row=next(r for r in market['sectorReturns']['rows'] if r.get('ticker')==fund['code']+'.KS');self.assertLessEqual(row['asOf'],market['sectorReturns']['asOf']);self.assertNotIn('2099-01-01',row['calculation']['constituentData'][0]['observations'])
