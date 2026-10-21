"""October21 actual price data; archived observations remain exact dated."""
import json,math,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class October21Prices(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.d=json.loads((ROOT/'data/korea-market.json').read_text())
  cls.b=next(x for x in json.loads((ROOT/'data/briefings.json').read_text())['entries']if x['market']=='KR'and x['date']=='2026-10-21')
  cls.e=json.loads((ROOT/'data/korea-highs-evidence-20261021.json').read_text())
 def test_actual_price_dates_and_boundaries(self):
  for key in ['heatmaps','sectorReturns','highsScreen','indexMovers']:
   self.assertGreaterEqual(self.d[key]['asOf'],'2026-10-21')
  self.assertTrue(all(r['asOf']=='2026-10-21'for r in self.e['rows']))
  self.assertEqual(self.b['sectors']['asOf'],'2026-10-21')
 def test_raw_price_precision_and_actual_previous_session(self):
  for r in self.e['rows']:
   if r['freshDailyCoverage']:
    self.assertAlmostEqual(r['changePct'],(r['close']/r['previousClose']-1)*100,places=10)
    self.assertEqual(r['volumeCurrent'],int(r['volumeCurrent']))
    self.assertEqual(r['volumePrevious'],int(r['volumePrevious']))
 def test_and_screen_uses_exact_previous_not_average(self):
  expected={r['ticker']for r in self.e['rows']if r['freshDailyCoverage']and abs(r['changePct'])>=5 and r['volumeCurrent']/r['volumePrevious']>=2}
  self.assertEqual(expected,{r['ticker']for r in self.b['movers']['rows']})
  for r in self.b['movers']['rows']:
   self.assertEqual(r['previousSession'],'2026-10-20');self.assertFalse(r['regularSessionVolumeCertified'])
 def test_highs_union_and_disjoint_labels(self):
  expected={r['ticker']for r in self.e['rows']if r['isNewHigh']or r['isNearHigh']}
  self.assertEqual(expected,{r['ticker']for r in self.b['highs']['rows']})
  for r in self.e['rows']:
   if r['fullHistoryCoverage']:
    self.assertEqual(r['isNewHigh'],r['sessionHigh']>r['prior52WeekHigh'])
    self.assertEqual(r['isNearHigh'],r['close']>=.97*r['high52'])
   self.assertEqual(r['classification']=='new_high',r['isNewHigh'])
   if r['classification']=='near_high':self.assertFalse(r['isNewHigh'])
 def test_sector_returns_recompute_without_date_relabel(self):
  if self.d['sectorReturns']['asOf']!='2026-10-21':return
  for r in self.d['sectorReturns']['rows']:
   if r['asOf']!='2026-10-21':
    self.assertEqual(r.get('refreshStatus'),'retained_previous');continue
   c=r['calculation'];self.assertEqual(c['bases'],{'day':'2026-10-20','week':'2026-10-14','month':'2026-09-21'})
   for k,day in c['bases'].items():
    values=[(q['observations']['2026-10-21']['close' if q.get('priceField')=='close' else 'adjustedClose']/q['observations'][day]['close' if q.get('priceField')=='close' else 'adjustedClose']-1)*100 for q in c['constituentData']]
    self.assertEqual(r[k],round(sum(values)/len(values),2))

class SectorSourceValidation(unittest.TestCase):
 def test_naver_uses_actual_close_without_false_adjusted_label(self):
  import sys,copy
  sys.path.insert(0,str(ROOT/'scripts'))
  from validate_korean_market import validate
  d=json.loads((ROOT/'data/korea-market.json').read_text())
  component=next(c for r in d['sectorReturns']['rows']for c in r['calculation']['constituentData']if c.get('priceField')=='close')
  self.assertNotIn('adjustedClose',next(iter(component['observations'].values())))
  component.pop('priceBasis')
  self.assertTrue(any('non-adjusted source basis required' in e for e in validate(d)))
 def test_retained_sector_cannot_be_redated(self):
  import sys,copy
  sys.path.insert(0,str(ROOT/'scripts'))
  from validate_korean_market import validate
  d=json.loads((ROOT/'data/korea-market.json').read_text())
  retained=[r for r in d['sectorReturns']['rows']if r.get('refreshStatus')=='retained_previous']
  for r in retained:self.assertLess(r['asOf'],d['sectorReturns']['asOf'])
  if retained:
   retained[0]['asOf']=d['sectorReturns']['asOf']
   self.assertTrue(any('verified window required' in e for e in validate(d)))



class PartialIndexPrices(unittest.TestCase):
 def test_partial_index_is_exact_verified_subset(self):
  d=json.loads((ROOT/'data/korea-market.json').read_text());e=json.loads((ROOT/'data/korea-index-evidence-20261021.json').read_text())
  self.assertEqual(e['publicationMode'],'explicit_verified_subset')
  self.assertEqual(len(e['priceSeries']['KOSPI200']),201);self.assertEqual(len(e['priceSeries']['KOSDAQ150']),148)
  for group in list(d['indexMovers']['daily'].values())+[d['indexMovers']['aggregate5d'],d['indexMovers']['monthly']]:
   for index,item in group.items():
    partial=index=='KOSDAQ150';self.assertEqual(item['status'],'partial' if partial else 'verified')
    self.assertEqual(item['coverage']['missingCodes'],['056190','195940'] if partial else [])
    if partial:self.assertIn('전체 순위 아님',item['scopeLabel'])
    start,end=item['comparisonStart'],item['comparisonEnd']
    values=[{'code':r['code'],'changePct':(r['closes'][end]['close']/r['closes'][start]['close']-1)*100} for r in e['priceSeries'][index]]
    for key,positive in [('gainers',True),('losers',False)]:
     ranked=sorted([r for r in values if (r['changePct']>0 if positive else r['changePct']<0)],key=lambda r:((-1 if positive else 1)*r['changePct'],r['code']))[:10]
     self.assertEqual([r['code']for r in item[key]],[r['code']for r in ranked])
     for actual,expected in zip(item[key],ranked):self.assertAlmostEqual(actual['changePct'],expected['changePct'],places=10)
 def test_partial_index_cannot_claim_complete(self):
  import sys
  sys.path.insert(0,str(ROOT/'scripts'));from validate_korean_market import validate
  d=json.loads((ROOT/'data/korea-market.json').read_text());item=d['indexMovers']['daily']['2026-10-21']['KOSDAQ150'];item['status']='verified'
  self.assertTrue(any('partial ranking scope must be explicit' in e for e in validate(d)))

if __name__=='__main__':unittest.main()
