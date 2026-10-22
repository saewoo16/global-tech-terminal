#!/usr/bin/env python3
"""Actual NAVER KRX ETF daily candles and intraday observations. No synthetic data.
Public read-only endpoints; Python standard library only. AUM deliberately null:
NAVER marketSum is market capitalization, not net assets. Quote turnover amonut is
not exposed until unit is independently verified. Short histories remain short.
"""
import argparse, concurrent.futures, datetime as dt, json, pathlib, time, urllib.request, xml.etree.ElementTree as ET
CATALOGUE='https://finance.naver.com/api/sise/etfItemList.nhn'
# Selection favors established KODEX/TIGER sector funds, adds SOL for specific supply chains.
UNIVERSE=[
('091160','반도체','industry'),('139260','IT','industry'),('091180','자동차','industry'),
('091170','은행','industry'),('102970','증권','industry'),('140700','보험','industry'),
('117700','건설','industry'),('117680','철강','industry'),('117460','에너지·화학','industry'),
('102960','기계·장비','industry'),('140710','운송','industry'),('143860','헬스케어','industry'),
('266410','필수소비재','industry'),('266390','경기소비재','industry'),('157490','소프트웨어','industry'),
('0148J0','로봇','theme'),('305720','2차전지','theme'),
('455860','2차전지 소부장','theme'),('455850','반도체 소부장','theme'),
('475300','반도체 전공정','theme'),('475310','반도체 후공정','theme'),('449450','방산','theme'),
('0247S0','MLCC·AI기판(글로벌)','theme'),('0207G0','우주','theme'),('466920','조선','theme'),('487240','AI전력 설비','theme'),
('0091P0','원자력','theme'),('457990','태양광·신재생','theme'),('0209D0','ESS·전고체 배터리','theme'),('364970','바이오','theme'),
('228790','화장품','theme'),('228800','여행·레저','theme'),('228810','미디어·콘텐츠','theme'),
('365000','인터넷','theme'),('364990','게임','theme'),('329200','리츠·인프라','theme')]

def fetch(url):
    last=None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(url,timeout=40) as r:return r.read()
        except Exception as e:
            last=e
            if attempt<2:time.sleep(1+attempt)
    raise last

def iso(v):return f'{v[:4]}-{v[4:6]}-{v[6:8]}'
def official(code,name):
    if code=='0209D0':return 'https://www.samsungfund.com/etf/product/view.do?id=2ETFV7'
    if code=='0148J0':return 'https://www.youtube.com/watch?v=TdlpU2qIzJM'
    if code=='457990':return 'https://www.plusetf.co.kr/product/detail?n=006279'
    if name.startswith('KODEX'):return 'https://www.samsungfund.com/etf/product/list.do'
    if code=='0247S0':return 'https://www.kiwoometf.com/service/invest/KO04020102T?kijaGubun=10&kijaNo=695'
    if code=='449450':return 'https://www.plusetf.co.kr/product/detail?n=006192'
    if code=='0207G0':return 'https://www.soletf.co.kr/ko/fund/etf/211116'
    if code=='455850':return 'https://www.soletf.co.kr/ko/fund/etf/210980'
    if name.startswith('SOL'):return 'https://www.soletf.co.kr/en/fund'
    if code=='463250':return 'https://develop.investments.miraeasset.com/tigeretf/ko/product/search/detail/index.do?ksdFund=KR7463250001'
    if code=='462010':return 'https://kind.krx.co.kr/disclosure/etfisudetail.do?method=searchEtfIsuSummary&strIsurCd=46201'
    return 'https://www.tigeretf.com'
def build_fund(spec,quotes,today):
    code,category,group=spec;q=quotes[code]
    daily_url=f'https://fchart.stock.naver.com/sise.nhn?symbol={code}&timeframe=day&count=400&requestType=0'
    intraday_url=f'https://api.stock.naver.com/chart/domestic/item/{code}?periodType=day'
    # Decode before XML parse because Expat does not support EUC-KR directly.
    xml=ET.fromstring(fetch(daily_url).decode('euc-kr'))
    chart=xml.find('.//chartdata');history=[]
    start=(today-dt.timedelta(days=366)).isoformat()
    for item in xml.findall('.//item'):
        v=item.attrib['data'].split('|')
        if len(v)==6 and iso(v[0])>=start:
            try:r={'date':iso(v[0]),**dict(zip(('open','high','low','close','volume'),map(int,v[1:])))}
            except ValueError:continue
            if r['close']>0 and r['open']>0 and r['low']<=min(r['open'],r['close'])<=max(r['open'],r['close'])<=r['high']:history.append(r)
    history.sort(key=lambda r:r['date'])
    raw=json.loads(fetch(intraday_url));points=[]
    for v in raw.get('priceInfos',[]):
        stamp=v.get('localDateTime','');price=v.get('currentPrice')
        if len(stamp)>=12 and price is not None and price>0:
            points.append({'time':f'{iso(stamp)}T{stamp[8:10]}:{stamp[10:12]}:00+09:00','price':price,'cumulativeVolume':v.get('accumulatedTradingVolume')})
    points.sort(key=lambda r:r['time']);intraday_date=iso(raw.get('tradeBaseAt','')) if raw.get('tradeBaseAt') else (points[-1]['time'][:10] if points else None)
    points=[p for p in points if p['time'][:10]==intraday_date]
    previous_volume=0
    for point in points:
        cumulative=point.get('cumulativeVolume')
        if cumulative is not None and cumulative>=previous_volume:
            point['volume']=cumulative-previous_volume
            previous_volume=cumulative
    if not history or len(points)<2:raise ValueError('Missing valid daily or intraday series; retain previous valid fund')
    orig=chart.attrib.get('origintime','') if chart is not None else ''
    result={'code':code,'name':q['itemname'],'issuer':q['itemname'].split()[0],'category':category,'group':group,
      'metadataAsOf':intraday_date,'metadataRetrievedAt':dt.datetime.now(dt.timezone.utc).isoformat(),
      'aumKRW':None,'marketCapKRW':q.get('marketSum',0)*100000000,'volume':q.get('quant'),'turnoverKRW':None,
      'quotePrice':q.get('nowVal'),'quoteChangePct':q.get('changeRate'),'navPerShareKRW':q.get('nav'),
      'listedAt':iso(orig) if len(orig)==8 else None,
      'sourceUrls':[official(code,q['itemname']),CATALOGUE,daily_url,intraday_url],
      'sourceTitles':['운용사·KRX 상품정보','NAVER ETF 시세·규모 목록','NAVER 실제 일별 OHLCV','NAVER 실제 장중 1분 관측'],
      'daily':history,'dailySourceUrl':daily_url,'dailyAdjustment':'공급사 제공 일별 가격 계열. 분배금 재투자 총수익률이 아니며 수정주가 처리 방식은 공급사에 따릅니다.',
      'dailyCoverage':{'start':history[0]['date'] if history else None,'end':history[-1]['date'] if history else None,'count':len(history),'requestedMonths':12,'shortHistory':len(history)<200},
      'intraday':{'date':intraday_date,'interval':'1분 관측 · 무거래 구간 생략 · 시간외 포함','sourceUrl':intraday_url,'asOf':points[-1]['time'] if points else None,'status':'verified' if points else 'unavailable','exchange':raw.get('stockExchangeType'),'marketStatus':raw.get('marketStatus'),'points':points,'note':'실제 1분 관측값; 무거래 구간 생략, 시간외 거래 포함. volume은 직전 관측 이후 누적 거래량의 차이입니다.'},
      'selectionNote':'국내 상장·국내 주식/산업 노출 대표 ETF. 시가총액과 당일 거래량을 함께 제시하며 유동성 보장이나 전체 시장 최대규모 선언이 아닙니다.'}
    if code=='0148J0':result['selectionNote']='레인보우로보틱스·로보티즈·에스피지·삼현과 국내 로봇 밸류체인 기업을 담는 TIGER 코리아휴머노이드로봇산업 ETF. 대표 기업 괄호는 편입비중 순위가 아닌 ETF 내 시가총액 순위입니다.'
    if code=='457990':result['selectionNote']='한화솔루션·OCI홀딩스·HD현대에너지솔루션 중심의 태양광과 ESS 관련 국내 기업에 투자합니다. 순수 태양광 단일업종이 아니며 배터리·전력 기업도 포함됩니다.'
    if code=='0209D0':result['selectionNote']='LG에너지솔루션·삼성SDI 중심의 국내 전고체 배터리 및 ESS 혼합 테마입니다. 순수 ESS 전수지수가 아니며 기존 태양광·신재생 ETF와 일부 구성종목이 겹칩니다. 실제 상장 이후 이력만 표시합니다.'
    if code=='449450':result['selectionNote']='한화에어로스페이스·현대로템·한국항공우주·한화시스템 등을 편입한 국내 방산 ETF. 방산과 우주는 별도로 표시하지만 복수 사업 기업의 편입은 겹칠 수 있습니다.'
    if code=='0207G0':result['selectionNote']='에이치브이엠·스피어·세아베스틸지주·쎄트렉아이·알멕을 편입한 국내 우주 밸류체인 ETF. 한화시스템 등 방산 사업 기업도 포함됩니다. 실제 상장 이후 차트만 표시합니다.'
    if code=='0247S0':result['selectionNote']='삼성전기·대덕전자·심텍·이수페타시스 등을 담는 MLCC·AI기판 테마. 한국·일본 혼합 글로벌 ETF이며 국내 업종 전수지수가 아닙니다. 2026-10-13 상장으로 실제 상장 이후 차트만 제공합니다.'
    print(code,q['itemname'],len(history),len(points),intraday_date,flush=True)
    return result

def refresh_representatives(funds, previous):
    try:
        from korean_etf_representatives import fetch_market_snapshot, collect_representatives
    except ImportError:
        from scripts.korean_etf_representatives import fetch_market_snapshot, collect_representatives
    try:
        market, observed_at = fetch_market_snapshot()
    except Exception:
        market, observed_at = None, None
    def collect(fund):
        old = previous.get(fund['code'], {}).get('representatives')
        try:
            if market is None: raise ValueError('Market-cap snapshot unavailable')
            result = collect_representatives(fund['code'], market, observed_at, [fund['sourceUrls'][0]])
            if result.get('status') != 'verified': raise ValueError('Incomplete constituent market-cap verification')
            fund['representatives'] = result
        except Exception:
            if old:
                fund['representatives'] = dict(old, refreshStatus='stale')
            else:
                fund['representatives'] = {'scope':'etf','label':'ETF 내 시총 상위','members':[], 'status':'unavailable', 'methodology':'구성종목 또는 시가총액 확인이 완료되지 않아 순위를 표시하지 않습니다.'}
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        list(pool.map(collect, funds))

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',default=str(pathlib.Path(__file__).resolve().parents[1]/'data/korean_etf_charts.json'));args=p.parse_args()
    now=dt.datetime.now(dt.timezone.utc);today=now.astimezone(dt.timezone(dt.timedelta(hours=9))).date()
    quotes={x['itemcode']:x for x in json.loads(fetch(CATALOGUE).decode('euc-kr'))['result']['etfItemList']}
    dest=pathlib.Path(args.output)
    previous={}
    if dest.exists():
        previous={f['code']:f for f in json.loads(dest.read_text()).get('funds',[])}
    funds=[];errors=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        jobs={pool.submit(build_fund,s,quotes,today):s for s in UNIVERSE}
        for job in concurrent.futures.as_completed(jobs):
            try:
                fund=job.result()
                old_evidence=previous.get(fund['code'],{}).get('selectionEvidence')
                if old_evidence and not fund.get('selectionEvidence'):fund['selectionEvidence']=old_evidence
                funds.append(fund)
            except Exception as e:
                code=jobs[job][0];errors.append({'code':code,'error':str(e)})
                old=previous.get(code)
                if old and old.get('daily') and old.get('intraday',{}).get('points'):
                    old['refreshStatus']='stale';old['refreshError']=str(e);funds.append(old)
    refresh_representatives(funds, previous)
    order={s[0]:i for i,s in enumerate(UNIVERSE)};funds.sort(key=lambda f:order[f['code']])
    payload={'schemaVersion':1,'updatedAt':now.isoformat(),'asOf':max((f['intraday']['date'] or '' for f in funds),default=None),'timezone':'Asia/Seoul','currency':'KRW','funds':funds,'errors':errors,'methodology':['NAVER 공개 KRX 일별 OHLCV와 실제 장중 1분 관측값입니다. 누락값·주말·휴장일·상장 전 기간을 합성하지 않습니다.','장중 volume은 직전 관측 이후 누적 거래량 차이이며 cumulativeVolume은 누적 거래량입니다. 무거래 구간은 생략됩니다. 시가총액은 순자산(AUM)이 아니며 AUM 미확인 값은 null입니다.','12개월 범위 내 거래일만 포함합니다. 최근 상장 ETF는 확보된 실제 이력만 표시합니다.','선정은 KODEX/TIGER 우선 및 세부 공급망 SOL, 방산 PLUS, MLCC·AI기판 KIWOOM 보완 방식입니다. 당일 거래량은 장기 유동성의 보장이 아닙니다.','NAVER 공개 비공식 API는 변경·제한될 수 있으며 거래소 직접 실시간 피드가 아닙니다.']}
    if not funds:raise RuntimeError('No valid funds; existing output preserved')
    dest.parent.mkdir(parents=True,exist_ok=True)
    temp=dest.with_suffix('.tmp');temp.write_text(json.dumps(payload,ensure_ascii=False,separators=(',',':'))+'\n');temp.replace(dest)
    print('Saved',dest,'funds',len(funds),'errors',errors)
if __name__=='__main__':main()
