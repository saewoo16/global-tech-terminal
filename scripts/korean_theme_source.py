import json,datetime,argparse,urllib.request,concurrent.futures
from pathlib import Path
R=Path(__file__).resolve().parents[1]/'data'

def build(refresh=False, previous=None, responses=None):
 if responses is None:
  jobs=[(m,i,p) for m in ['KOSPI','KOSDAQ'] for i in ['FOREIGNER','ORGANIZATION'] for p in ['DAY','WEEK','MONTH']]
  def fetch(job):
   m,i,p=job
   url=f'https://stock.naver.com/api/domestic/market/trend/trendForeignOrg?investorType={i}&tradeType=KRX&marketType={m}&startIdx=0&pageSize=100&periodType={p}'
   with urllib.request.urlopen(url,timeout=40) as response:data=json.load(response)
   return f'{m}_{i}_{p}',{'url':url,'retrievedAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),'data':data}
  with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:responses=dict(pool.map(fetch,jobs))
 baskets=json.loads((R/'korea-theme-definitions.json').read_text())
 flow={}; names={}; source={}
 for inv in ['FOREIGNER','ORGANIZATION']:
  for per in ['DAY','WEEK','MONTH']:
   rows=[]
   for market in ['KOSPI','KOSDAQ']:
    d=responses[f'{market}_{inv}_{per}']
    for side in ['buyRankList','sellRankList']:
     for row in d['data']['sections'][side]:
      if row['type']!='ST': continue
      row=dict(row,market=market,sourceUrl=d['url'],sourceId=f'naver-{market.lower()}-'+{'FOREIGNER':'foreign','ORGANIZATION':'institution'}[inv]+'-'+{'DAY':'day','WEEK':'week','MONTH':'month'}[per]+'-'+row['bizdateTo'])
      rows.append(row);names[row['itemcode']]=row['itemname']
   assert len(set(r['itemcode'] for r in rows))==len(rows)
   flow[(inv,per)]={r['itemcode']:r for r in rows}
 names.update({'011170':'롯데케미칼','011780':'금호석유화학','454910':'두산로보틱스'})
 periods={'1d':{'apiPeriod':'DAY','label':'일간','from':'2026-10-16','to':'2026-10-16','sessions':1},'1w':{'apiPeriod':'WEEK','label':'주간','from':'2026-10-12','to':'2026-10-16','sessions':5},'1m':{'apiPeriod':'MONTH','label':'월간','from':'2026-09-15','to':'2026-10-16','sessions':20}}
 # Provider-returned periods are authoritative; future trading-session counts are not guessed.
 for key,per in periods.items():
  dates={(r['bizdateFrom'],r['bizdateTo']) for inv in ['FOREIGNER','ORGANIZATION'] for r in flow[(inv,per['apiPeriod'])].values()}
  assert len(dates)==1, ('Mixed provider period windows',key,dates)
  start,end=next(iter(dates));per['from']=f'{start[:4]}-{start[4:6]}-{start[6:]}';per['to']=f'{end[:4]}-{end[4:6]}-{end[6:]}'
  if end!='20261016':per['sessions']=1 if key=='1d' else None
 assert len({p['to'] for p in periods.values()})==1,'Mixed provider as-of dates'
 sourcefile=R/'korea-theme-membership.json'
 classifications=json.loads(sourcefile.read_text()) if sourcefile.exists() else {}
 classification_metadata=dict(classifications) if isinstance(classifications,dict) else {}
 if isinstance(classifications,list): classifications={x['code']:x for x in classifications}
 if 'members' in classifications: classifications=classifications['members']
 expected_codes={c for cs in baskets.values() for c in cs}
 assert set(classifications)==expected_codes, ('Missing membership evidence',expected_codes-set(classifications))
 assert all(x.get('classification_status')=='verified' for x in classifications.values())
 classification_sources=[]
 for code,item in classifications.items():
  for n,evidence in enumerate(item.get('sources',[]),1):
   evidence['id']=f'basket-business-{code}-{n}';classification_sources.append(dict(evidence))
  item['sourceIds']=[x['id'] for x in item.get('sources',[])]
 result={'schemaVersion':1,'asOf':periods['1d']['to'],'collectedAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),'title':'대표 종목 바스켓 수급','classificationType':'curated_representative_baskets','basketDefinitionVersion':'2026-10-17-v1','coverage':'KOSPI + KOSDAQ common stocks, KRX trading only','currency':'KRW','displayUnit':'억원','amountSource':'NAVER Securities public KRX investor ranking API accTradeAmount','amountStatus':'source_reported_exact_KRW','primaryExchangeDirectlyVerified':False,'periods':periods,'notes':[
 '각 테마의 공개 기업 사업내용을 참고해 고정한 2~3개 보통주 대표 바스켓입니다. 전체 업종·테마의 합계 또는 공식 KRX 업종 지수가 아닙니다.',
 '각 종목의 해당 기간 실제 순매수대금(accTradeAmount)을 합산했습니다. 일별 순위표의 상위 종목만 더하거나 순매수 수량에 종가를 곱하지 않았습니다.',
 'NAVER 원천 응답은 시장별 매수·매도 각 상위 100개로 제한됩니다. 구성종목 하나라도 금액을 확인하지 못하면 바스켓 합계와 순위를 표시하지 않습니다. 미확인 값은 0이 아닙니다.',
 '순위는 선택 기간·투자자에서 모든 구성종목 금액이 확보된 대표 바스켓 사이의 내림차순입니다. 기간·투자자별 비교 가능 바스켓 수가 다릅니다.',
 '한화에어로스페이스(012450)는 우주와 방산에 중복됩니다. 기업은 여러 사업을 영위하며 바스켓별 수급에는 해당 기업 주식 전체 거래가 포함됩니다. 바스켓들을 합산하면 안 됩니다.',
 '외국인과 기관은 NAVER의 FOREIGNER 및 ORGANIZATION 분류입니다. tradeType=KRX를 사용하며 NXT 거래는 포함하지 않습니다.',
 '공식 거래소 직접 대조는 접근 제한으로 완료하지 못했습니다. 금액은 NAVER가 제공한 원 단위 응답값입니다.',
 '과거 일별 종목 순매수 금액은 이 API에서 직접 조회되지 않습니다. 일별 기록은 실제 수집·보존된 스냅샷만 표시합니다.',
 '금융 바스켓은 은행 중심 금융지주 3종목 표본입니다. 정유의 SK이노베이션은 SK에너지 자회사 사업 노출을 포함하며, 화장품의 에이피알은 화장품·뷰티기기 사업을 근거로 편입했습니다.'
 ],'membershipVerification':'pending_source_checks' if not classifications else 'source_backed','baskets':[]}
 for i,(name,codes) in enumerate(baskets.items()):
  members=[{'code':c,'name':names.get(c,c),'classificationEvidence':classifications.get(c)} for c in codes]
  b={'id':['semiconductors','electronics','batteries','refining','chemicals','biotech','finance','entertainment','space','robotics','defense','shipbuilding','cosmetics'][i],'name':name,'memberCount':len(codes),'members':members,'flows':{}}
  for key,per in periods.items():
   b['flows'][key]={}
   for invkey,inv in [('foreign','FOREIGNER'),('institution','ORGANIZATION')]:
    rows=flow[(inv,per['apiPeriod'])]
    missing=[c for c in codes if c not in rows]
    memberflows=[]
    for c in codes:
     r=rows.get(c)
     if r:
      assert r['bizdateFrom']==per['from'].replace('-','') and r['bizdateTo']==per['to'].replace('-','')
      memberflows.append({'code':c,'name':names.get(c,c),'netBuyKRW':int(r['accTradeAmount']),'sourceUrl':r['sourceUrl'],'sourceId':r['sourceId'],'market':r['market']})
     else: memberflows.append({'code':c,'name':names.get(c,c),'netBuyKRW':None,'sourceUrl':None,'sourceId':None,'market':None})
    total=None if missing else sum(x['netBuyKRW'] for x in memberflows)
    b['flows'][key][invkey]={'status':'complete' if not missing else 'missing_constituent_amounts','netBuyKRW':total,'netBuyEok':None if total is None else total/100000000,'rank':None,'availableCount':len(codes)-len(missing),'expectedCount':len(codes),'missingMembers':[{'code':c,'name':names.get(c,c)} for c in missing],'memberFlows':memberflows,'sourceIds':list(dict.fromkeys(x['sourceId'] for x in memberflows if x['sourceId']))}
  result['baskets'].append(b)
 result['rankingCoverage']={}
 for period in periods:
  result['rankingCoverage'][period]={}
  for inv in ['foreign','institution']:
   valid=[b for b in result['baskets'] if b['flows'][period][inv]['status']=='complete']
   valid.sort(key=lambda b:b['flows'][period][inv]['netBuyKRW'],reverse=True)
   for rank,b in enumerate(valid,1):b['flows'][period][inv]['rank']=rank
   result['rankingCoverage'][period][inv]={'completeBaskets':len(valid),'totalBaskets':len(baskets)}

 result['sources']=list({r['sourceId']:{'id':r['sourceId'],'title':f"NAVER 증권 {r['market']} {inv} {per} 순매수·순매도 금액",'url':r['sourceUrl'],'note':'KRX 파라미터의 공급사 기간 합산 원 단위 금액; 최종 거래소 확정 여부는 별도 검증하지 않음.'} for (inv,per),rows in flow.items() for r in rows.values()}.values())
 result['sources'].extend(classification_sources)
 result['membershipSourceNotes']=classification_metadata.get('methodology_notes_ko',[])
 result['membershipCounts']={'memberships':sum(len(x) for x in baskets.values()),'uniqueTickers':len(expected_codes)}
 result['dailySnapshots']={}
 if previous:
  old=json.loads(Path(previous).read_text()) if isinstance(previous,(str,Path)) and Path(previous).exists() else previous if isinstance(previous,dict) else {}
  result['dailySnapshots'].update(old.get('dailySnapshots',{}))
 result['dailySnapshots'][result['asOf']]={'asOf':result['asOf'],'collectedAt':result['collectedAt'],'classificationType':result['classificationType'],'rows':[{'id':b['id'],'name':b['name'],'memberCount':b['memberCount'],'members':b['members'],'foreign':b['flows']['1d']['foreign'],'institution':b['flows']['1d']['institution']} for b in result['baskets']]}
 result['dailySnapshots']={k:result['dailySnapshots'][k] for k in sorted(result['dailySnapshots'])[-5:]}
 return result


def normalize(result, dates, previous=None):
 def absent(day):
  return {'status':'unavailable','rows':[],'sourceIds':[],'coverage':{'start':day,'end':day},'note':'이 날짜의 대표 바스켓 전체 구성종목 수급은 미확보입니다. 최신 1일·주간·월간으로 전환해 주세요.'}
 def period(key):
  info=result['periods'][key];rows=[];ids=set()
  for basket in result['baskets']:
   row={'name':basket['name'],'memberCount':basket['memberCount'],'members':basket['members'],'coverage':{}}
   for investor in ['foreign','institution']:
    cell=basket['flows'][key][investor];row[investor]=cell['netBuyEok'];row['coverage'][investor]=cell;ids.update(cell['sourceIds'])
   row['note']='외국인 '+str(row['coverage']['foreign']['availableCount'])+'/'+str(basket['memberCount'])+' · 기관 '+str(row['coverage']['institution']['availableCount'])+'/'+str(basket['memberCount'])
   rows.append(row)
  return {'status':'partial','rows':rows,'sourceIds':sorted(ids),'coverage':{'start':info['from'],'end':info['to'],'count':len(rows),'note':'외국인 '+str(result['rankingCoverage'][key]['foreign']['completeBaskets'])+'/13 · 기관 '+str(result['rankingCoverage'][key]['institution']['completeBaskets'])+'/13개 바스켓 합계 확인'},'note':'고정한 2~3개 대표 종목 바스켓입니다. 전체 업종·테마 합계가 아닙니다. 구성종목 하나라도 금액이 없으면 해당 투자자의 합계는 미확인으로 둡니다.','membershipVerification':result['membershipVerification']}
 daily=dict((previous or {}).get('daily',{}));daily[result['asOf']]=period('1d')
 return {'unit':'억원','dates':dates,'daily':{day:daily.get(day,absent(day))for day in dates},'aggregate5d':period('1w'),'monthly':period('1m'),'methodology':'테마별 고정 2~3개 대표 종목의 실제 순매수 합계입니다. 전체 업종 순위가 아닙니다. 구성종목 한 개라도 금액이 미확인이면 합계를 비워 둡니다.','classification':result['classificationType'],'membershipVerification':result['membershipVerification'],'baskets':[{'id':b['id'],'name':b['name'],'members':b['members']}for b in result['baskets']]}
