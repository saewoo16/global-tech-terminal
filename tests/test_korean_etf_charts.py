import datetime as dt,json,pathlib,unittest,importlib.util,tempfile,sys
from unittest.mock import patch
ROOT=pathlib.Path(__file__).resolve().parents[1]
PATH=ROOT/'data/korean_etf_charts.json'
if not PATH.exists():PATH=pathlib.Path(__file__).with_name('korean_etf_charts.json')
class ETFChartsTest(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.data=json.loads(PATH.read_text());cls.funds=cls.data['funds']
 def test_broad_coverage(self):
  self.assertGreaterEqual(len(self.funds),30)
  self.assertTrue({'0148J0','305720','455850','449450','0207G0','457990','0209D0','0222F0'}<={f['code'] for f in self.funds})
 def test_user_exclusions_do_not_return(self):
  codes={f['code'] for f in self.funds}
  self.assertFalse(codes & {'069500','229200','462010','471990','463250','445290','385510'})
  self.assertTrue({'455860','455850','475300','475310','449450','0207G0'} <= codes)
  self.assertEqual(next(f for f in self.funds if f['code']=='0207G0')['category'],'우주')
 def test_representative_portfolio_weights(self):
  for f in self.funds:
   r=f.get('representatives')
   if not r or r.get('status')=='unavailable':continue
   self.assertIn(r['scope'],{'etf','sector'})
   if r['scope']=='etf':self.assertIn('ETF',r['label'])
   self.assertTrue(r['asOf']);self.assertTrue(r['universeAsOf']);self.assertTrue(r['sourceUrls'])
   self.assertLessEqual(len(r['members']),3)
   caps=[m['weightPct'] for m in r['members']]
   self.assertTrue(all(c>=0 for c in caps));self.assertEqual(caps,sorted(caps,reverse=True))
   self.assertLessEqual(r['verifiedCount'],r['universeCount'])
 def test_real_ohlc(self):
  for f in self.funds:
   rows=f['daily'];self.assertTrue(rows,f['code']);self.assertEqual(len(rows),len({r['date'] for r in rows}));self.assertEqual(rows,sorted(rows,key=lambda x:x['date']))
   for r in rows:self.assertTrue(0<r['low']<=min(r['open'],r['close'])<=max(r['open'],r['close'])<=r['high']);self.assertGreaterEqual(r['volume'],0)
   self.assertEqual(rows[-1]['date'],f['dailyCoverage']['end'])
 def test_actual_intraday(self):
  for f in self.funds:
   i=f['intraday'];ps=i['points'];self.assertGreater(len(ps),1);self.assertEqual(i['exchange'],'KRX');self.assertEqual(len(ps),len({p['time'] for p in ps}))
   for p in ps:self.assertGreater(p['price'],0);self.assertTrue(p['time'].startswith(i['date']));self.assertTrue(p['time'].endswith('+09:00'));self.assertGreaterEqual(p.get('volume',0),0)
   self.assertEqual(sum(p.get('volume',0) for p in ps),ps[-1]['cumulativeVolume'])
 def test_no_aum_confusion(self):
  for f in self.funds:self.assertIsNone(f['aumKRW']);self.assertGreater(f['marketCapKRW'],0);self.assertEqual(len(f['sourceUrls']),4)
 def test_short_history_is_honest(self):
  space=next(f for f in self.funds if f['code']=='0207G0');self.assertTrue(space['dailyCoverage']['shortHistory']);self.assertEqual(space['daily'][0]['date'],'2026-06-16')
 def test_datacenter_is_added_without_replacing_selected_themes(self):
  from scripts import update_korean_etf_charts as mod
  codes=[f['code'] for f in self.funds];configured=[s[0] for s in mod.UNIVERSE]
  self.assertEqual(len(codes),len(set(codes)));self.assertEqual(set(codes),set(configured))
  self.assertGreaterEqual(len(codes),37)
  self.assertEqual([s for s in mod.UNIVERSE if s[0]=='0222F0'],[('0222F0','데이터센터','theme')])
  self.assertEqual(mod.official('0222F0','마이티 AI데이터센터밸류체인'),'https://db-asset.com/mob/kr/fund/41900')
  f=next(f for f in self.funds if f['code']=='0222F0')
  self.assertEqual(f['name'],'마이티 AI데이터센터밸류체인');self.assertEqual(f['listedAt'],'2026-08-04')
  self.assertTrue(all(row['date']>=f['listedAt'] for row in f['daily']))
  self.assertEqual(f['sourceUrls'][0],mod.official(f['code'],f['name']))
  self.assertNotIn('https://www.tigeretf.com',f['representatives']['sourceUrls'])
 def test_datacenter_dated_issuer_evidence_and_liquidity_are_separate(self):
  f=next(f for f in self.funds if f['code']=='0222F0');e=f['selectionEvidence']
  self.assertIsNone(f['aumKRW'])
  self.assertEqual(e['asOf'],'2026-10-22');self.assertEqual(e['officialHoldings']['asOf'],e['asOf'])
  self.assertEqual(e['officialHoldings']['equityCount'],22);self.assertEqual(e['officialHoldings']['cashCount'],1)
  official=e['officialHoldings']['rows'];self.assertEqual(len(official),23)
  self.assertEqual({r['code'] for r in official},{r['code'] for r in e['holdings']})
  sdi=next(r for r in official if r['code']=='006400');self.assertEqual(sdi['unitsPerCreationUnit'],146);self.assertEqual(sdi['valuationKRW'],80884000)
  self.assertEqual(e['officialAum']['asOf'],'2026-10-21');self.assertEqual(e['officialAum']['valueKRW'],12619250893)
  liquidity=e['liquidity'];self.assertEqual(liquidity['asOf'],'2026-10-22');self.assertEqual(liquidity['marketCapKRW'],12100000000)
  self.assertEqual(liquidity['volumeShares'],980);self.assertEqual(liquidity['intradayObservationCount'],11)
  self.assertEqual(e['priceReverification']['dailyCount'],53)
  for word in ('저거래량','AUM','2026-10-21','2026-10-22','상장 전','무거래'):
   self.assertIn(word,e['disclosure'])
  self.assertNotIn('저거래량',f['selectionNote'],'Detailed dated caveats belong in the folded source disclosure')
 def test_datacenter_collector_keeps_actual_short_history(self):
  from scripts import update_korean_etf_charts as mod
  xml=b'<protocol><chartdata origintime="20260804"><item data="20261021|10880|11010|10875|11010|342"/><item data="20261022|10810|10865|10495|10555|980"/></chartdata></protocol>'
  intraday={'tradeBaseAt':'20261022','stockExchangeType':'KRX','marketStatus':'CLOSE','priceInfos':[{'localDateTime':'202610220933','currentPrice':10810,'accumulatedTradingVolume':3},{'localDateTime':'202610221530','currentPrice':10555,'accumulatedTradingVolume':980}]}
  q={'itemname':'마이티 AI데이터센터밸류체인','marketSum':121,'quant':980,'nowVal':10555,'changeRate':-4.13,'nav':10553}
  with patch.object(mod,'fetch',side_effect=[xml,json.dumps(intraday).encode()]):f=mod.build_fund(('0222F0','데이터센터','theme'),{'0222F0':q},dt.date(2026,10,22))
  self.assertEqual(len(f['daily']),2);self.assertEqual(len(f['intraday']['points']),2)
  self.assertTrue(f['dailyCoverage']['shortHistory']);self.assertIsNone(f['aumKRW']);self.assertEqual(f['marketCapKRW'],12100000000)
  self.assertEqual(sum(p['volume'] for p in f['intraday']['points']),980)
  self.assertEqual(f['sourceUrls'][0],'https://db-asset.com/mob/kr/fund/41900')
  self.assertIn('국내 AI 데이터센터',f['selectionNote'])
 def test_representative_refresh_failure_keeps_original_dates(self):
  from scripts import update_korean_etf_charts as mod
  from scripts import korean_etf_representatives as rep
  old={'scope':'etf','basis':'portfolioWeight','label':'ETF 편입비중 상위','asOf':'2026-10-20T07:00:00Z','universeAsOf':'2026-10-20','members':[{'name':'A','marketCapKRW':100}]}
  funds=[{'code':'TEST','sourceUrls':['https://example.com'] }]
  with patch.object(rep,'collect_weight_representatives',side_effect=ValueError('offline')):
   mod.refresh_representatives(funds,{'TEST':{'representatives':old}})
  got=funds[0]['representatives'];self.assertEqual(got['asOf'],old['asOf']);self.assertEqual(got['members'],old['members']);self.assertEqual(got['refreshStatus'],'stale')
 def test_selection_evidence_retains_original_dates(self):
  from scripts import update_korean_etf_charts as mod
  fund=dict(self.funds[0]);fund.pop('selectionEvidence',None)
  evidence={'asOf':'2026-10-21','observedAt':'2026-10-21T08:00:00Z','holdings':[]}
  with tempfile.TemporaryDirectory() as tmp:
   dest=pathlib.Path(tmp)/'snapshot.json';dest.write_text(json.dumps({'funds':[dict(fund,selectionEvidence=evidence)]}))
   with patch.object(mod,'UNIVERSE',[(fund['code'],'x','industry')]),patch.object(mod,'fetch',return_value=b'{"result":{"etfItemList":[]}}'),patch.object(mod,'build_fund',return_value=dict(fund)),patch.object(mod,'refresh_representatives'),patch.object(sys,'argv',['collector','--output',str(dest)]):mod.main()
   self.assertEqual(json.loads(dest.read_text())['funds'][0]['selectionEvidence'],evidence)
 def test_partial_refresh_preserves_previous_fund(self):
  script=ROOT/'scripts/update_korean_etf_charts.py'
  if not script.exists():script=pathlib.Path(__file__).with_name('update_korean_etf_charts.py')
  spec=importlib.util.spec_from_file_location('etf_collector_test',script);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
  old=self.funds[0];fresh=self.funds[1]
  with tempfile.TemporaryDirectory() as tmp:
   dest=pathlib.Path(tmp)/'snapshot.json';dest.write_text(json.dumps({'funds':[old]}))
   def build(spec,*args):
    if spec[0]==old['code']:raise ValueError('Simulated provider failure')
    return fresh
   with patch.object(mod,'UNIVERSE',[(old['code'],'x','industry'),(fresh['code'],'y','industry')]),patch.object(mod,'fetch',return_value=b'{"result":{"etfItemList":[]}}'),patch.object(mod,'build_fund',side_effect=build),patch.object(mod,'refresh_representatives'),patch.object(sys,'argv',['collector','--output',str(dest)]):mod.main()
   got=json.loads(dest.read_text());self.assertEqual(len(got['funds']),2);retained=next(f for f in got['funds'] if f['code']==old['code']);self.assertEqual(retained['daily'],old['daily']);self.assertEqual(retained['refreshStatus'],'stale');self.assertEqual(len(got['errors']),1)
if __name__=='__main__':unittest.main()
