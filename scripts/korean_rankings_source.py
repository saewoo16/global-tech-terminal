#!/usr/bin/env python3
"""Public, unauthenticated Naver KRX rankings. Direct period aggregates, no sum of truncated lists.
Called by update_korean_market.py. Reads only public, unauthenticated endpoints.
A refresh fetches current provider periods, whose returned dates must be inspected.
"""
import argparse,datetime,json,pathlib,re,urllib.request,concurrent.futures
P=pathlib.Path(__file__).parent
BASE='https://stock.naver.com/api/domestic/market/'
RAW_RESPONSES={}
def fetch(job,refresh=False):
 name,url=job
 data=json.load(urllib.request.urlopen(url,timeout=40))
 obj={'url':url,'retrievedAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),'data':data}
 RAW_RESPONSES[name]=obj
 return obj

def preferred(x):
 # Name suffix alone would wrongly remove 성우, 이오플로우, 에코글로우.
 return bool(re.search(r'우(?:B|C)?(?:\(전환\))?$',x['itemname'])) and not x['itemcode'].endswith('0')
def eligible(x):return x.get('type','ST')=='ST' and not preferred(x)
def iso(s):return f'{s[:4]}-{s[4:6]}-{s[6:]}'
def build(refresh=False,previous=None):
 jobs=[]
 for market in ['KOSPI','KOSDAQ']:
  for investor in ['FOREIGNER','ORGANIZATION']:
   for period in ['DAY','WEEK','MONTH']:
    jobs.append((f'{market}_{investor}_{period}',BASE+f'trend/trendForeignOrg?investorType={investor}&tradeType=KRX&marketType={market}&startIdx=0&pageSize=100&periodType={period}'))
 jobs += [('turnover',BASE+'stock/default?tradeType=KRX&marketType=ALL&orderType=priceTop&startIdx=0&pageSize=100'),('universe',BASE+'stock/default?tradeType=KRX&marketType=ALL&orderType=marketSum&startIdx=0&pageSize=4000'),('exchange_status','https://stock.naver.com/api/stockSecurity/exchanges/market-status?exchanges=KRX')]
 with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:raw=dict(zip([j[0] for j in jobs],pool.map(lambda j:fetch(j,refresh),jobs)))
 sources=[];periods={};asof=None
 for period,label in [('DAY','day'),('WEEK','week'),('MONTH','month')]:
  section={}
  for inv,key in [('FOREIGNER','foreign'),('ORGANIZATION','institution')]:
   bymarket={};allrows=[];sids=[];starts=set();ends=set();counts={}
   for market in ['KOSPI','KOSDAQ']:
    obj=raw[f'{market}_{inv}_{period}'];source=f'naver-{market.lower()}-{key}-{label}-'+obj['data']['sections']['buyRankList'][0]['bizdateTo'];sids.append(source)
    vs=obj['data']['sections']['buyRankList'];assert len(vs)>=15
    starts.update(iso(x['bizdateFrom']) for x in vs);ends.update(iso(x['bizdateTo']) for x in vs)
    rows=[{'code':x['itemcode'],'name':x['itemname'],'market':market,'value':int(x['accTradeAmount']),'sourceId':source,'source':obj['url']} for x in vs if eligible(x)]
    assert len(rows)>=15 and all(x['value']>0 for x in rows[:15])
    rows.sort(key=lambda x:x['value'],reverse=True);bymarket[market]=rows[:15];allrows+=rows
    counts[market]={'sourceNetBuyRows':len(vs),'eligibleNetBuyRows':len(rows),'returnedTop':15}
    sources.append({'id':source,'title':f'NAVER 증권 {market} {inv} {period} 순매수 순위','url':obj['url'],'note':'공급사의 기간 합산 순매수대금. 거래유형 파라미터 KRX. 일별 상위 목록을 더한 값이 아닙니다.'})
   assert len(starts)==len(ends)==1
   start=next(iter(starts));end=next(iter(ends));asof=end
   section[key]={'status':'verified','unit':'KRW','rows':sorted(allrows,key=lambda x:x['value'],reverse=True)[:15],'byMarket':bymarket,'sourceIds':sids,'coverage':{'start':start,'end':end,'sourceCounts':counts,'markets':['KOSPI','KOSDAQ'],'periodType':period},'note':'NAVER 원자료의 외국인/기관 순매수 금액. 각 시장 상위 100개 순매수 목록에서 공급사 유형 ST만 대상으로 우선주 명칭·코드 필터를 적용한 상위 15종목. ST 스팩은 포함하며 RT 리츠·FS 외국주식·DR 예탁증권 및 펀드·ETF·ETN은 제외합니다. 보통주 중심 조회이며 법적 주식종류 전수 검증은 아닙니다. 전체 종목 금액 합계로 사용할 수 없습니다. '+('공급사의 MONTH 실제 조회창은 '+start+'~'+end+'입니다.' if period=='MONTH' else '공급사 집계 시점에 따라 장마감 기사와 값이 다를 수 있습니다.')}
  periods[label]=section
 # Latest turnover is returned by the priceTop sort and independently checked against full stock list.
 obj=raw['turnover'];univ=raw['universe']['data'];vs=obj['data'];allcommon=[x for x in univ if eligible(x) and x.get('sosok') in ('0','1')];eligible_top=[x for x in vs if eligible(x) and x.get('sosok') in ('0','1')]
 assert len(eligible_top)>=20 and len(univ)>2000
 expected=sorted(allcommon,key=lambda x:int(x['tradeAmount'] or 0),reverse=True)[:20]
 assert [x['itemcode']for x in expected]==[x['itemcode']for x in eligible_top[:20]],'Turnover ranking mismatch'
 exchange=raw['exchange_status']['data'];dates={s['latest']['tradeBaseAt'] for e in exchange['exchanges']for s in e['statuses']if s.get('marketType')in ['KOSPI','KOSDAQ']};assert dates=={asof},(dates,asof)
 sources += [{'id':'naver-turnover','title':'NAVER 증권 KRX 거래대금 순위','url':obj['url'],'note':'tradeAmount 원화. 종가×거래량으로 추정하지 않습니다. 전체 주식 목록과 상위20 순위를 대조했습니다.'},{'id':'naver-universe','title':'NAVER KRX 주식 전체 목록','url':raw['universe']['url']},{'id':'naver-exchange-status','title':'NAVER KRX 최근 거래 기준일','url':raw['exchange_status']['url']}]
 tv={'status':'verified','unit':'KRW','rows':[{'code':x['itemcode'],'name':x['itemname'],'market':'KOSPI'if x['sosok']=='0'else'KOSDAQ','value':int(x['tradeAmount']),'sourceId':'naver-turnover','source':obj['url']}for x in eligible_top[:20]],'byMarket':{m:[{'code':x['itemcode'],'name':x['itemname'],'market':m,'value':int(x['tradeAmount']),'sourceId':'naver-turnover','source':obj['url']}for x in sorted(allcommon,key=lambda x:int(x['tradeAmount']or 0),reverse=True)if x['sosok']==s][:20] for m,s in [('KOSPI','0'),('KOSDAQ','1')]},'sourceIds':['naver-turnover','naver-universe','naver-exchange-status'],'coverage':{'start':asof,'end':asof,'sourceUniverseCount':len(univ),'eligibleStockCount':len(allcommon),'marketUniverseCount':sum(x.get('sosok') in ('0','1') for x in univ),'excludedOtherMarketCount':sum(x.get('sosok') not in ('0','1') for x in univ),'universeDefinition':'KOSPI/KOSDAQ only; Naver type ST, preferred-name/code filter; ST SPAC included, RT/FS/DR/IF/PF/MF excluded','preferredFilter':'Name 우/우B/우C/우(전환) suffix AND short code not ending 0; audited current-name exceptions 성우/이오플로우/에코글로우 retained','excludedTypes':['RT','FS','DR','IF','PF','MF'],'includedSPACs':True,'returnedTop':20},'note':'KRX 파라미터로 조회한 최신 거래대금. 전체 '+str(len(univ))+'개 원목록 중 ST 유형 및 우선주 명칭·코드 필터를 통과한 '+str(len(allcommon))+'개 보통주 중심 대상. ST 스팩 포함, RT 리츠·FS·DR 및 펀드형 제외. 애프터마켓 마감 이후 조회한 공급사 스냅샷이며 최종 확정 통계로 단정하지 않습니다.'}
 periods['day']['tradedValue']=tv
 daily={}
 if previous and pathlib.Path(previous).exists():
  old=json.loads(pathlib.Path(previous).read_text());daily.update(old.get('rankings',{}).get('daily',{}));sources.extend(old.get('sources',[]))
 daily[asof]=periods['day']
 historical=P/'historical_rankings.json'
 if historical.exists():
  press=json.loads(historical.read_text())
  for date in sorted(set(z['date']for z in press)):
   daily[date]={}
   for key in ['foreign','institution']:
    selected=[z for z in press if z['date']==date and z['investor']==key];assert len(selected)==2
    sids=[];rows=[];bymarket={}
    for z in selected:
     sid=f'yonhap-{date}-{z["market"].lower()}-{key}';sids.append(sid)
     zr=[{**r,'sourceId':sid}for r in z['rows']];rows+=zr;bymarket[z['market']]=zr[:15]
     sources.append({'id':sid,'title':z['sourceName']+' '+date+' '+z['market']+' '+key,'url':z['url'],'note':'15:30 집계, 원자료 단위 '+z['sourceUnit']+'. 원화로 변환. NAVER 최신값과 집계시점이 다릅니다.'})
    daily[date][key]={'status':'verified','unit':'KRW','rows':sorted(rows,key=lambda x:x['value'],reverse=True)[:15],'byMarket':bymarket,'sourceIds':sids,'coverage':{'start':date,'end':date,'markets':['KOSPI','KOSDAQ'],'snapshotAt':date+'T15:30:00+09:00'},'note':'연합뉴스가 KRX·연합인포맥스를 인용한 15:30 순매수 상위20에서 우선주 명칭·코드 필터를 적용한 상위15. 코스피 원자료 억원, 코스닥 만원을 원화로 변환. NAVER의 최신 및 기간 집계와 값·시점이 다를 수 있습니다.'}
   daily[date]['tradedValue']={'status':'unavailable','unit':'KRW','rows':[],'byMarket':{},'sourceIds':[],'coverage':{'start':date,'end':date},'note':'이 날짜의 실제 거래대금 상위20 전체 순위를 검증하지 못했습니다. 종가×거래량으로 대체하지 않았습니다.'}
 dates=sorted(daily)[-5:]
 return {'schemaVersion':1,'asOf':asof,'generatedAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),'unit':'KRW','sources':list({s['id']:s for s in reversed(sources)}.values()),'rankings':{'unit':'KRW','dates':dates,'daily':{d:daily[d]for d in dates},'aggregate5d':periods['week'],'periods':periods},'limitations':['기간 합계는 공급사의 직접 WEEK/MONTH 집계이며 일별 상위10 합이 아닙니다.','과거 일별 순위는 15:30 기사 스냅샷, 최신과 기간 순위는 NAVER KRX 파라미터 조회입니다.','과거 4거래일 거래대금 상위20은 미확보입니다.','순매수 목록은 상위100 제한으로 시장 전체 또는 테마 합산의 모수가 아닙니다.']}
