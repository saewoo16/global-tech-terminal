"""Retain dated raw rankings without weakening date/coverage validation."""
import copy,json,pathlib,sys,tempfile,unittest
from unittest.mock import patch
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from validate_korean_market import validate
from update_korean_market import update_rankings
from korean_rankings_source import build as build_rankings
from korean_theme_source import build as build_themes, normalize as normalize_themes
class DatedArchive(unittest.TestCase):
 def setUp(self):self.data=json.loads((ROOT/'data/korea-market.json').read_text())
 def test_more_than_five_snapshots_preserved(self):
  self.assertIn('2026-10-21',self.data['rankings']['daily']);self.assertGreater(len(self.data['rankings']['dates']),5);self.assertEqual(validate(self.data),[])
 def test_unsorted_duplicate_and_mismatched_dates_rejected(self):
  for kind in ['reverse','duplicate','missing']:
   p=copy.deepcopy(self.data);dates=p['rankings']['dates']
   if kind=='reverse':dates.reverse()
   elif kind=='duplicate':dates.append(dates[-1])
   else:dates.pop(0)
   self.assertTrue(any('rankings:' in e for e in validate(p)))

 def test_refresh_retains_all_rankings_and_prior_theme_observations(self):
  before=copy.deepcopy(self.data)
  latest=max(before['rankings']['daily'])
  def provider(section):
   result=copy.deepcopy(section);result['unit']='KRW'
   for rows in [result.get('rows',[]),*result.get('byMarket',{}).values()]:
    for row in rows:row['value']=round(row['value']*1e8)
   return result
  incoming={'asOf':latest,'sources':[],'rankings':{
   'daily':{latest:{key:provider(value) for key,value in before['rankings']['daily'][latest].items()}},
   'periods':{period:{key:provider(before['rankings'][section][key]) for key in ('foreign','institution')}
              for period,section in [('week','aggregate5d'),('month','monthly')]}}}
  evidence=json.loads((ROOT/'data/korea-flow-restoration-evidence-20261028.json').read_text())
  themes=build_themes(responses=evidence['rawInvestorResponses'])
  with patch('update_korean_market.collect_rankings',return_value=incoming):
   for _ in range(2):
    update_rankings(self.data)
    self.assertEqual(self.data['rankings']['dates'],sorted(before['rankings']['daily']))
    self.assertEqual(self.data['rankings']['daily'],before['rankings']['daily'])
    self.data['themes']=normalize_themes(themes,self.data['rankings']['dates'],self.data['themes'])
    for day,value in before['themes']['daily'].items():
     if day!=themes['asOf'] and value.get('rows'):
      self.assertEqual(self.data['themes']['daily'][day],value)
    self.assertEqual(validate(self.data),[])

 def test_source_builder_retains_previous_dates_beyond_five(self):
  # Synthetic provider responses exercise the builder offline; no fake market
  # values are written to the repository's published data.
  day='2026-10-28'
  universe=[{'itemcode':f'{i:05d}0','itemname':f'Fixture {i}','type':'ST',
             'sosok':str(i%2),'tradeAmount':str(3000-i)} for i in range(2001)]
  def fetch(job,refresh=False):
   name,url=job
   if name=='turnover':data=universe[:100]
   elif name=='universe':data=universe
   elif name=='exchange_status':
    data={'exchanges':[{'statuses':[{'marketType':market,'latest':{'tradeBaseAt':day}}
                                   for market in ('KOSPI','KOSDAQ')]}]}
   else:
    market,investor,period=name.split('_')
    rows=[{**row,'accTradeAmount':row['tradeAmount'],'bizdateFrom':'20261028','bizdateTo':'20261028'}
          for row in universe if row['sosok']==('0' if market=='KOSPI' else '1')][:100]
    data={'sections':{'buyRankList':rows,'sellRankList':[]}}
   return {'url':url,'data':data}
  old={f'2026-10-{i:02d}':{'archivedFixture':i} for i in range(20,28)}
  with tempfile.TemporaryDirectory() as directory:
   path=pathlib.Path(directory)/'previous.json'
   path.write_text(json.dumps({'rankings':{'daily':old}}))
   with patch('korean_rankings_source.fetch',side_effect=fetch),patch('korean_rankings_source.P',path.parent):
    result=build_rankings(previous=path)
  self.assertEqual(result['rankings']['dates'],sorted([*old,day]))
  for date,value in old.items():self.assertEqual(result['rankings']['daily'][date],value)
  self.assertEqual(result['rankings']['daily'][day]['foreign']['coverage']['end'],day)
