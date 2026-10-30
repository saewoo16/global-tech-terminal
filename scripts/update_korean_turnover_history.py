"""Same-provider KRX + NXT investor gross-buy history, never net flows or top stocks.
All 12 mutually exclusive investor categories and both venues must be complete.
This is a provider-derived market turnover series, not an exchange official final.
Run after completed KRX/NXT sessions; preserve all other panels and raw ECOS history.
"""
import argparse,copy,hashlib,json,calendar
from datetime import date,datetime,timezone
from decimal import Decimal,InvalidOperation
from pathlib import Path
from urllib.request import urlopen
from concurrent.futures import ThreadPoolExecutor
from update_korean_turnover_comparison import validate_status,STATUS
ROOT=Path(__file__).resolve().parents[1]
CODES={'1000','2000','3000','3100','4000','5000','6000','7000','7100','8000','9000','9001'}
SCOPE='provider-investor-gross-buy-krx-plus-nxt'
SOURCE='naver-krx-nxt-investor-gross-turnover'
BASE='https://stock.naver.com/api/domestic/market/trend/daily?tradeType={venue}&marketType={market}&bizdate={day}&startIdx={page}&pageSize=30'

def integer(value):
 if isinstance(value,bool) or value is None:raise ValueError('Invalid numeric investor field')
 try:v=Decimal(str(value))
 except InvalidOperation:raise ValueError('Invalid numeric investor field')
 if not v.is_finite() or v!=v.to_integral_value():raise ValueError('Investor fields must be finite integers')
 return v

def investor_total(row):
 records=row.get('netAmounts',[])
 codes=[r.get('investorGubun') for r in records]
 if len(codes)!=12 or set(codes)!=CODES:raise ValueError('Exactly 12 exclusive investor categories required')
 buy=sell=bq=sq=Decimal(0)
 for r in records:
  b,s,bv,sv=[integer(r.get(k)) for k in ('buyPrice','sellPrice','buyQuant','sellQuant')]
  if min(b,s,bv,sv)<0:raise ValueError('Negative gross money or shares')
  if integer(r.get('diffValue'))!=b-s:raise ValueError('Investor net amount does not reconcile')
  buy+=b;sell+=s;bq+=bv;sq+=sv
 if abs(buy-sell)>12000000:raise ValueError('Buy/sell money totals disagree beyond 12-category rounding bound')
 if bq!=sq:raise ValueError('Buy/sell share totals disagree')
 if buy<=0:raise ValueError('Missing/zero whole-market turnover')
 return buy

def year_start(day):
 d=date.fromisoformat(day)
 return d.replace(year=d.year-1,day=min(d.day,calendar.monthrange(d.year-1,d.month)[1])).isoformat()

def fetch(url):
 with urlopen(url,timeout=30) as response:raw=response.read()
 return {'url':url,'observedAt':datetime.now(timezone.utc).isoformat(),'sha256':hashlib.sha256(raw).hexdigest(),'data':json.loads(raw)}

def validate_venue_status(status,day,venue):
 if venue not in ('KRX','NXT'):raise ValueError('Unknown venue')
 selected=[x for x in status.get('exchanges',[]) if x.get('exchange')==venue.lower()]
 if len(selected)!=1:raise ValueError('Requested venue status missing/duplicate')
 adapted=copy.deepcopy(status);adapted['exchanges']=[copy.deepcopy(selected[0])]
 adapted['exchanges'][0]['exchange']='nxt'
 validate_status(adapted,day)

def collect(day):
 # The same final-session safeguard used by the existing NXT collector.
 status={v:fetch(STATUS.replace('exchanges=NXT','exchanges='+v)) for v in ('KRX','NXT')}
 for v,item in status.items():validate_venue_status(item['data'],day,v)
 jobs=[(v,m,p) for v in ('KRX','NXT') for m in ('KOSPI','KOSDAQ') for p in range(9)]
 def get(job):
  v,m,p=job;result=fetch(BASE.format(venue=v,market=m,day=day.replace('-',''),page=p));result.update(venue=v,market=m,page=p);return result
 snapshots=list(ThreadPoolExecutor(4).map(get,jobs))
 final={v:fetch(STATUS.replace('exchanges=NXT','exchanges='+v)) for v in ('KRX','NXT')}
 for v,item in final.items():validate_venue_status(item['data'],day,v)
 return {'targetDate':day,'observedAt':datetime.now(timezone.utc).isoformat(),'statusBefore':status,'statusAfter':final,'snapshots':snapshots}

def build(payload,evidence,target_date):
 date.fromisoformat(target_date);start=year_start(target_date)
 lookup={(v,m):{} for v in ('KRX','NXT') for m in ('KOSPI','KOSDAQ')}
 for snapshot in evidence['snapshots']:
  v,m=snapshot['venue'],snapshot['market']
  if (v,m) not in lookup:raise ValueError('Unknown venue/market')
  if f'tradeType={v}&marketType={m}&' not in snapshot['url']:raise ValueError('Evidence URL scope mismatch')
  for row in snapshot['data']['content']:
   day=datetime.strptime(row['bizdate'],'%Y%m%d').date().isoformat()
   if day>target_date:raise ValueError('Future/uncompleted observation')
   if day in lookup[v,m]:raise ValueError('Duplicate daily observation/page')
   amount=investor_total(row)
   lookup[v,m][day]={'amount':amount,'row':row,'snapshot':snapshot}
 result=copy.deepcopy(payload)
 source={'id':SOURCE,'title':'Npay KRX·NXT 투자자별 일별 매수대금 전분류 합산','url':'https://stock.naver.com/domestic/trend','note':'거래소별 일별 API 12개 상호배타 투자자 분류의 매수금액만 합산. 매도금액·주식수 대조. 원단위 원, 공급자 백만원 정밀도. 공식 거래소 확정 총액이 아니며 ECOS 및 개별종목 현재가 집계와 범위·수정시점 차이가 있음.'}
 prior=next((s for s in result['sources'] if s['id']==SOURCE),None)
 if prior and prior!=source:raise ValueError('Existing source contract changed')
 if not prior:result['sources'].append(source)
 for market in ('KOSPI','KOSDAQ'):
  target=result['marketTurnover']['markets'][market]
  expected={r['date'] for r in payload['flows']['markets'][market]['rows'] if start<=r['date']<=target_date}
  if target_date not in expected:raise ValueError('Target not in preserved verified completed-session dates')
  for venue in ('KRX','NXT'):
   missing=expected-lookup[venue,market].keys()
   if missing:raise ValueError(f'{venue} {market} missing completed dates: {sorted(missing)}')
  available=set(lookup['KRX',market])&set(lookup['NXT',market])
  rows=[]
  old=target.get('integratedHistory',{})
  if old and old.get('sessionScope')!=SCOPE:raise ValueError('Changed history scope requires separate series')
  previous={r['date']:r for r in old.get('rows',[])}
  for day in sorted(available):
   if day<start:continue
   krx,nxt=lookup['KRX',market][day],lookup['NXT',market][day]
   total=krx['amount']+nxt['amount']
   parts={v:{'grossBuyKRW':str(item['amount']),'grossSellKRW':str(sum(integer(x['sellPrice']) for x in item['row']['netAmounts'])),'buyShares':str(sum(integer(x['buyQuant']) for x in item['row']['netAmounts'])),'sellShares':str(sum(integer(x['sellQuant']) for x in item['row']['netAmounts'])),'categoryCount':12,'source':item['snapshot']['url'],'observedAt':item['snapshot']['observedAt']} for v,item in [('KRX',krx),('NXT',nxt)]}
   row={'date':day,'turnover':float(total/Decimal(10**8)),'sourceValue':str(total),'sourceUnit':'원','conversionToEokKRW':1e-8,'observedAt':max(x['observedAt'] for x in parts.values()),'sourceIds':[SOURCE],'scopeVerified':True,'valueStatus':'provider-end-of-day','officialAggregate':False,'components':parts,'precisionNote':'12개 투자자 분류별 백만원 표시 정밀도. 매수대금 한쪽만 합산하며 매수+매도 이중합산 아님.'}
   prior=previous.get(day)
   if prior and prior['sourceValue']==row['sourceValue'] and all(all(prior.get('components',{}).get(v,{}).get(k)==parts[v][k] for k in ('grossBuyKRW','grossSellKRW','buyShares','sellShares','categoryCount')) for v in parts):row=prior
   rows.append(row)
  # Preserve older verified history when the moving window advances.
  combined={r['date']:r for r in old.get('rows',[])};combined.update({r['date']:r for r in rows});rows=[r for _,r in sorted(combined.items())]
  target['integratedHistory']={'market':market,'unit':'억원','scope':'whole-market','venues':['KRX','NXT'],'sessionScope':SCOPE,'label':'KRX + NXT 거래대금','scopeNote':'Npay 투자자별 일별 매수대금 합산 · KRX와 NXT 각각 12개 투자자 분류를 한 번씩 합산. 정규장 단독 수치나 거래소 공식 확정 총액이 아닙니다.','status':'verified','asOf':rows[-1]['date'],'sourceIds':[SOURCE],'rows':rows,'coverage':{'start':rows[0]['date'],'end':rows[-1]['date'],'count':len(rows)},'precisionNote':'원자료는 원 단위 필드·분류별 백만원 표시 정밀도. 매수/매도 금액 차이는 분류별 반올림 범위 내이며 양쪽 주식수 합계는 일치.','note':'기존 ECOS(KRX 시간외 포함·NXT 제외)와 최근 날짜의 수치가 다르므로 이어 붙이지 않습니다. NXT 개별종목 현재가 전수 합과도 차이가 있어 공식 최종 총액과 동일하다고 주장하지 않습니다. 모든 날짜에 같은 공급자·같은 집계 정의를 적용합니다.'}
 if result==payload:return payload
 result['marketTurnover']['historyUpdatedAt']=evidence['observedAt']
 return result

def main():
 p=argparse.ArgumentParser();p.add_argument('--as-of',required=True);p.add_argument('--path',default=str(ROOT/'data/korea-market.json'));p.add_argument('--evidence-input');p.add_argument('--evidence-output');a=p.parse_args()
 path=Path(a.path);old=json.loads(path.read_text())
 evidence=json.loads(Path(a.evidence_input).read_text()) if a.evidence_input else collect(a.as_of)
 new=build(old,evidence,a.as_of)
 if new is old:print('No newly verified history; unchanged.');return
 from korean_turnover import validate
 errors=validate(new['marketTurnover'],new['sources'])
 if errors:raise ValueError('; '.join(errors))
 output=Path(a.evidence_output) if a.evidence_output else ROOT/'data'/('korea-turnover-history-evidence-'+a.as_of.replace('-','')+'.json')
 output.write_text(json.dumps(evidence,ensure_ascii=False,separators=(',',':'))+'\n')
 temp=path.with_suffix('.tmp');temp.write_text(json.dumps(new,ensure_ascii=False,separators=(',',':'))+'\n');temp.replace(path)
 print('Verified same-provider KRX+NXT history merged; other panels preserved.')
if __name__=='__main__':main()
