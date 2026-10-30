"""After 20:00 KST, merge provider-precision KRX regular + all-session NXT totals.
No historical backfill is inferred. Complete NXT universe, page and market splits
must agree. This is a reconstructed provider sum, not an official exchange total.
"""
import argparse,copy,hashlib,json,time
from datetime import datetime,timezone,timedelta
from decimal import Decimal
from pathlib import Path
from urllib.request import urlopen
from concurrent.futures import ThreadPoolExecutor
from manage_korean_turnover_comparison import merge,empty_series
ROOT=Path(__file__).resolve().parents[1]
BASE='https://stock.naver.com/api/domestic/market/stock/default?tradeType=NXT&marketType={market}&orderType=marketSum&startIdx={page}&pageSize={size}'
STATUS='https://stock.naver.com/api/stockSecurity/exchanges/market-status?exchanges=NXT'
KST=timezone(timedelta(hours=9))
def fetch(url):
 with urlopen(url,timeout=30) as response:raw=response.read()
 return {'url':url,'observedAt':datetime.now(timezone.utc).isoformat(),'sha256':hashlib.sha256(raw).hexdigest(),'data':json.loads(raw)}
def index(rows):
 if not isinstance(rows,list):raise ValueError('Expected NXT stock list')
 result={}
 for r in rows:
  code=r.get('itemcode')
  if not code or code in result:raise ValueError('Duplicate or missing stock code')
  if r.get('type')!='ST' or r.get('sosok') not in ('0','1'):raise ValueError('Unsupported or unclassified NXT security')
  if r.get('marketStatus')!='CLOSE' or r.get('tradingSessionType')!='AFTER_MARKET':raise ValueError('NXT not after-market closed')
  amount=Decimal(r['tradeAmount'])
  if not amount.is_finite() or amount<0:raise ValueError('Missing/invalid actual trade amount')
  result[code]=r
 return result

def validate_status(status,as_of):
 statuses=[s for exchange in status.get('exchanges',[]) if exchange.get('exchange')=='nxt' for s in exchange.get('statuses',[])]
 for market in ('KOSPI','KOSDAQ'):
  s=next((s for s in statuses if s.get('marketType')==market and s.get('stockType')=='stock'),None)
  if not s or s.get('latest',{}).get('tradeBaseAt')!=as_of or not s.get('today',{}).get('isTradingDay'):raise ValueError('Requested date is not current completed NXT trading date')
  session=s['latest']['session']
  if session.get('marketStatusDetailType')!='close' or session.get('marketSessionType')!='afterMarket':raise ValueError('NXT all-session close not confirmed')
 server=datetime.fromisoformat(status['serverTime'])
 if server.astimezone(KST).strftime('%Y-%m-%d')!=as_of or server.astimezone(KST).hour<20:raise ValueError('NXT full-day total cannot be collected before 20:00 KST')

def collect(as_of,fetcher=fetch):
 status=fetcher(STATUS);validate_status(status['data'],as_of)
 full=fetcher(BASE.format(market='ALL',page=0,size=4000));stocks=index(full['data'])
 if not stocks or len(stocks)>=4000:raise ValueError('Missing or truncated NXT universe')
 # startIdx is a PAGE INDEX, not a stock-row offset.
 pages=(len(stocks)+99)//100
 jobs=[('page-'+str(i),BASE.format(market='ALL',page=i,size=100)) for i in range(pages+1)]
 jobs += [(m,BASE.format(market=m,page=0,size=4000)) for m in ('KOSPI','KOSDAQ')]
 results=dict(ThreadPoolExecutor(4).map(lambda job:(job[0],fetcher(job[1])),jobs))
 paged=[]
 for i in range(pages):paged.extend(results['page-'+str(i)]['data'])
 if results['page-'+str(pages)]['data']:raise ValueError('NXT universe has omitted final page')
 paged=index(paged)
 def fingerprint(d):return {k:(r['sosok'],r['tradeAmount'],r['tradeVolume']) for k,r in d.items()}
 if fingerprint(paged)!=fingerprint(stocks):raise ValueError('NXT complete pagination disagrees')
 for market,sosok in [('KOSPI','0'),('KOSDAQ','1')]:
  separate=index(results[market]['data']);expected={k:r for k,r in stocks.items() if r['sosok']==sosok}
  if fingerprint(separate)!=fingerprint(expected):raise ValueError('NXT market split disagrees')
 # Recheck status after obtaining the full snapshot; never mix next trading day.
 finalstatus=fetcher(STATUS);validate_status(finalstatus['data'],as_of)
 return {'date':as_of,'observedAt':datetime.now(timezone.utc).isoformat(),'statusBefore':status,'statusAfter':finalstatus,'full':full,'checks':results,'universeCount':len(stocks),'method':'Full venue-only NXT stock universe; independent 100-item pagination plus KOSPI/KOSDAQ endpoints; all CLOSE/AFTER_MARKET. No top-N sum. Provider-precision reported amounts.'}

def build_bundle(payload,evidence):
 d=evidence['date'];stamp=evidence['observedAt']
 sid='nxt-complete-turnover-'+d
 source={'id':sid,'title':'Npay NXT 전체 종목 거래대금·시장별 및 페이지 전수 대조 '+d,'url':evidence['full']['url'],'note':evidence['method']+'; marketStatus API confirms date/all-session close. NXT provider amounts are reported with limited precision; not an official aggregate.'}
 bundle={'sources':[source],'markets':{}}
 allrows=evidence['full']['data']
 for market,sosok in [('KOSPI','0'),('KOSDAQ','1')]:
  series=payload['marketTurnover']['markets'][market].get('comparisonSeries',{}).get('regular',{})
  regular=next((r for r in series.get('rows',[]) if r.get('date')==d and r.get('turnover') is not None),None)
  if not regular or not regular.get('scopeVerified'):raise ValueError('Same-date verified KRX regular close is required for '+market)
  rows=[r for r in allrows if r['sosok']==sosok]
  nxt=sum(Decimal(r['tradeAmount']) for r in rows)/Decimal(100000000)
  total=Decimal(str(regular['turnover']))+nxt
  r={'date':d,'turnover':float(total),'sourceValue':str(total),'sourceUnit':'억원','conversionToEokKRW':1,'observedAt':stamp,'sourceIds':list(dict.fromkeys(regular['sourceIds']+[sid])),'scopeVerified':True,'valueStatus':'final','officialAggregate':False,'valueStatusNote':'양 시장 해당 세션 종료 후 공급사 표시 금액 전수 합산. 거래소 공식 확정 총액을 뜻하지 않음.','regularTurnover':regular['turnover'],'nxtTurnover':float(nxt),'nxtStockCount':len(rows),'universeCount':evidence['universeCount'],'aggregationMethod':'verified KRX regular amount + complete NXT venue-only reported tradeAmount sum / 100000000','precisionNote':'NXT KOSPI 종목별 백만원·KOSDAQ 종목별 천원 표시 정밀도의 합산. 원거래 원단위 정확값이 아님. KRX 원자료 정밀도 별도 보존.'}
  s=empty_series(market,'integrated');s.update(label='KRX 정규장 + NXT 전체',sessionScope='regular-plus-nxt-all-sessions',scopeNote='KRX 09:00~15:30 정규장 + NXT 프리·메인·애프터마켓. KRX 시간외는 제외. NXT 전체 종목의 공급사 표시 거래대금을 시장별 전수 합산한 값이며 거래소 공식 총액이 아닙니다. 과거 NXT 시장별 검증 이력이 없는 날은 미확인으로 남깁니다.',status='verified',rows=[r],sourceIds=r['sourceIds'],asOf=d,coverage={'start':d,'end':d,'count':1})
  bundle['markets'][market]={'integrated':s}
 return bundle

def main():
 p=argparse.ArgumentParser();p.add_argument('--as-of',required=True);p.add_argument('--path',default=str(ROOT/'data/korea-market.json'));p.add_argument('--evidence',help='Optional output evidence path; defaults data/korea-turnover-comparison-evidence-DATE.json');a=p.parse_args()
 path=Path(a.path);payload=json.loads(path.read_text());e=collect(a.as_of);bundle=build_bundle(payload,e);result=merge(payload,bundle,'integrated',a.as_of)
 if result is payload:print('No newly verified total; unchanged.');return
 out=Path(a.evidence) if a.evidence else ROOT/'data'/('korea-turnover-comparison-evidence-'+a.as_of.replace('-','')+'.json')
 # Evidence contains public quotations only; leave all other panels untouched.
 out.write_text(json.dumps(e,ensure_ascii=False,separators=(',',':'))+'\n')
 tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(result,ensure_ascii=False,separators=(',',':'))+'\n');tmp.replace(path);print('NXT full-universe comparison merged for '+a.as_of)
if __name__=='__main__':main()
