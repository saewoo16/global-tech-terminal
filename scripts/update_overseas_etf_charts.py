#!/usr/bin/env python3
"""US-listed sector/theme ETF OHLC snapshots. No synthetic bars or private keys.
Daily bars and returns are price-only (Yahoo split-adjusted close, not adjusted
close/dividend total return). Only completed regular-session daily bars are used.
The intraday chart contains actual five-minute regular-session observations.
"""
import argparse, calendar, concurrent.futures, datetime as dt, json, math, pathlib, time, urllib.parse, urllib.request
from zoneinfo import ZoneInfo
NY = ZoneInfo('America/New_York')
ROOT = pathlib.Path(__file__).resolve().parents[1]
THEMES={'LIT','BATT','ICLN','TAN','FAN','FDN','CIBR','CLOU'}

def fetch_chart(ticker, interval, period):
    query=urllib.parse.urlencode({'range':period,'interval':interval,'includePrePost':'false','events':'div,splits'})
    last=None
    for host in ('query1.finance.yahoo.com','query2.finance.yahoo.com'):
        url=f'https://{host}/v8/finance/chart/{urllib.parse.quote(ticker)}?{query}'
        for attempt in range(2):
            try:
                req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'})
                with urllib.request.urlopen(req,timeout=35) as response: data=json.load(response)
                if data.get('chart',{}).get('error'): raise ValueError(str(data['chart']['error']))
                return data['chart']['result'][0],url
            except Exception as exc:
                last=exc
                if not attempt: time.sleep(1)
    raise RuntimeError(str(last))

def number(value, positive=False):
    return isinstance(value,(int,float)) and math.isfinite(value) and (value>0 if positive else value>=0)

def daily_bars(raw, now):
    quote=raw.get('indicators',{}).get('quote',[{}])[0]
    bars=[]
    for i,stamp in enumerate(raw.get('timestamp',[])):
        local=dt.datetime.fromtimestamp(stamp,NY)
        # Don't publish a still-open US trading session as a completed daily bar.
        # Yahoo's currentTradingPeriod is authoritative for the latest session,
        # including exchange early closes; older sessions necessarily completed.
        regular=raw.get('meta',{}).get('currentTradingPeriod',{}).get('regular',{})
        regular_end=regular.get('end')
        if local.date()==now.astimezone(NY).date():
            if regular_end is None or now.timestamp()<regular_end: continue
        if local.date()>now.astimezone(NY).date(): continue
        values={key:(quote.get(key,[])[i] if i<len(quote.get(key,[])) else None) for key in ('open','high','low','close','volume')}
        if not all(number(values[k],True) for k in ('open','high','low','close')): continue
        if not values['low']<=min(values['open'],values['close'])<=max(values['open'],values['close'])<=values['high']: continue
        if not number(values['volume']): values['volume']=None
        bars.append({'date':local.date().isoformat(),**values})
    return sorted({b['date']:b for b in bars}.values(),key=lambda b:b['date'])

def period_returns(bars):
    result={'day':None,'week':None,'month':None};anchors={}
    if not bars:return result,anchors
    end=bars[-1];date=dt.date.fromisoformat(end['date'])
    month=date.month-1 or 12;year=date.year-(date.month==1)
    month_date=date.replace(year=year,month=month,day=min(date.day,calendar.monthrange(year,month)[1]))
    bases={'day':bars[-2] if len(bars)>=2 else None,'week':next((b for b in reversed(bars) if b['date']<=(date-dt.timedelta(days=7)).isoformat()),None),'month':next((b for b in reversed(bars) if b['date']<=month_date.isoformat()),None)}
    for period,base in bases.items():
        if base and number(base['close'],True):result[period]=(end['close']/base['close']-1)*100;anchors[period]=base['date']
    return result,anchors

def intraday_points(raw, now, latest_daily):
    quote=raw.get('indicators',{}).get('quote',[{}])[0];points=[]
    for i,stamp in enumerate(raw.get('timestamp',[])):
        local=dt.datetime.fromtimestamp(stamp,NY)
        if stamp>now.timestamp() or local.date().isoformat()!=latest_daily or not dt.time(9,30)<=local.time()<dt.time(16,0):continue
        price=quote.get('close',[])[i] if i<len(quote.get('close',[])) else None
        volume=quote.get('volume',[])[i] if i<len(quote.get('volume',[])) else None
        if number(price,True): points.append({'time':local.isoformat(),'price':price,'volume':volume if number(volume) else None})
    return sorted({p['time']:p for p in points}.values(),key=lambda p:p['time'])

def build_fund(row, sources, now, previous=None):
    ticker=row['ticker'];raw,daily_url=fetch_chart(ticker,'1d','1y');bars=daily_bars(raw,now)
    if len(bars)<2:raise ValueError('Fewer than two valid completed daily bars')
    meta=raw['meta']
    if meta.get('instrumentType')!='ETF' or meta.get('currency')!='USD':raise ValueError('Unexpected instrument type/currency')
    values,anchors=period_returns(bars);points=[];intraday_error=None;intra_url=None
    try:
        intra,intra_url=fetch_chart(ticker,'5m','5d');points=intraday_points(intra,now,bars[-1]['date'])
    except Exception as exc:intraday_error=str(exc)
    holdings=row.get('holdings',{});hold_sources=[sources[sid]['url'] for sid in holdings.get('sourceIds',[]) if sid in sources and sources[sid].get('url')]
    fund={'code':ticker,'name':row.get('benchmark') or meta.get('longName') or ticker,'issuer':(row.get('benchmark') or meta.get('longName') or ticker).split()[0],
      'category':row['name'],'sourceGroup':row.get('group'),'group':'theme' if ticker in THEMES else 'industry','currency':'USD','exchange':meta.get('fullExchangeName') or meta.get('exchangeName'),'timezone':'America/New_York',
      'metadataAsOf':bars[-1]['date'],'metadataRetrievedAt':now.isoformat(),'aumUSD':None,'marketCapUSD':None,'volume':bars[-1].get('volume'),'quotePrice':bars[-1]['close'],'quoteChangePct':values['day'],
      'listedAt':dt.datetime.fromtimestamp(meta['firstTradeDate'],NY).date().isoformat() if meta.get('firstTradeDate') else None,
      'sourceUrls':[daily_url]+([intra_url] if intra_url else [])+hold_sources,'sourceTitles':['Yahoo Finance 실제 일별 OHLCV']+(['Yahoo Finance 실제 정규장 5분 OHLCV'] if intra_url else [])+['운용사 검증 보유내역 (표시된 기존 기준일)']*len(hold_sources),
      'daily':bars,'dailySourceUrl':daily_url,'dailyAdjustment':'Yahoo Finance split-adjusted OHLC close. 분배금 재투자·배당 조정종가 총수익률이 아닌 가격 수익률입니다.',
      'returns':values,'returnAnchors':anchors,'returnsMethodology':'1일: 직전 거래일 종가, 1주일: 달력 7일 전 해당일 또는 그 이전 가장 가까운 거래일 종가, 1달: 달력 한 달 전 해당일 또는 그 이전 가장 가까운 거래일 종가. 일봉과 같은 close 기준 가격 수익률.',
      'dailyCoverage':{'start':bars[0]['date'],'end':bars[-1]['date'],'count':len(bars),'requestedMonths':12,'shortHistory':len(bars)<200},
      'intraday':{'date':bars[-1]['date'],'interval':'정규장 5분 관측 · 미국 동부시간','sourceUrl':intra_url,'asOf':points[-1]['time'] if points else None,'status':'verified' if len(points)>=2 else 'unavailable','points':points,'note':'실제 정규장 5분 구간 종가·구간 거래량. 장전·시간외 제외. 거래 없는 구간이나 누락 구간은 합성하지 않습니다.','refreshError':intraday_error},
      'selectionNote':'미국 상장 업종·테마 대표 ETF이며 글로벌 투자 상품은 미국 외 기업도 포함합니다. 전체 해외 업종을 전수 포함하지 않으며 ETF 간 구성종목이 겹칠 수 있습니다.'}
    old_intra=(previous or {}).get('intraday',{})
    if len(points)<2 and old_intra.get('date')==bars[-1]['date'] and len(old_intra.get('points',[]))>=2:
        fund['intraday']=dict(old_intra,refreshStatus='stale',refreshError=intraday_error or 'No new valid observations; retained prior verified same-session series')
    if holdings.get('status')=='verified':fund['holdings']=holdings;fund['holdingsSourceUrls']=hold_sources
    return fund

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',default=str(ROOT/'data/overseas_etf_charts.json'));parser.add_argument('--analysis',default=str(ROOT/'data/us_analysis.json'));args=parser.parse_args()
    analysis=json.loads(pathlib.Path(args.analysis).read_text());entries=sorted(analysis['entries'],key=lambda e:e['date'],reverse=True)
    entry=next(e for e in entries if e.get('sectors',{}).get('rows'));rows=[r for r in entry['sectors']['rows'] if r.get('instrumentType')=='etf']
    if not rows:raise ValueError('No verified ETF universe in existing analysis')
    sources={s['id']:s for s in entry.get('sources',[])};now=dt.datetime.now(dt.timezone.utc);dest=pathlib.Path(args.output)
    previous={f['code']:f for f in json.loads(dest.read_text()).get('funds',[])} if dest.exists() else {};funds=[];errors=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        jobs={pool.submit(build_fund,row,sources,now,previous.get(row['ticker'])):row for row in rows}
        for future in concurrent.futures.as_completed(jobs):
            row=jobs[future]
            try:fund=future.result();funds.append(fund);print(fund['code'],len(fund['daily']),len(fund['intraday']['points']),fund['daily'][-1]['date'],flush=True)
            except Exception as exc:
                errors.append({'code':row['ticker'],'error':str(exc)});old=previous.get(row['ticker'])
                if old and old.get('daily'):funds.append(dict(old,refreshStatus='stale',refreshError=str(exc)))
    if not funds or len(errors)==len(rows):raise RuntimeError('All ETF requests failed; existing snapshot preserved')
    # Partial source failure retains valid prior funds, never empties existing charts.
    order={r['ticker']:i for i,r in enumerate(rows)};funds.sort(key=lambda f:order[f['code']])
    payload={'schemaVersion':1,'updatedAt':now.isoformat(),'asOf':max(f['daily'][-1]['date'] for f in funds),'timezone':'America/New_York','currency':'USD','funds':funds,'errors':errors,'universeSourceDate':entry['date'],'methodology':['미국 상장 실제 ETF만 포함하며 화장품·화학 대표 종목 바스켓은 제외합니다.','가격은 Yahoo Finance 공개 비공식 시세입니다. 확정된 정규장 일봉과 실제 5분 관측만 사용하며 휴장일·상장 전·누락 구간을 합성하지 않습니다.','수익률은 일봉 close 기준 가격 수익률이며 분배금 재투자 총수익률이 아닙니다.','보유종목은 기존 분석의 운용사 검증 스냅샷과 실제 보유내역 기준일을 유지합니다. 가격 갱신이 보유내역 재검증을 의미하지 않습니다.']}
    dest.parent.mkdir(parents=True,exist_ok=True);temp=dest.with_suffix('.tmp');temp.write_text(json.dumps(payload,ensure_ascii=False,separators=(',',':'))+'\n');temp.replace(dest)
    print('Saved',dest,len(funds),'funds',len(errors),'errors')
if __name__=='__main__':main()
