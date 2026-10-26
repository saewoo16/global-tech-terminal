"""Public NAVER composition/stock-cap snapshots; no estimated constituents/caps."""
import datetime as dt
import json
import re
import urllib.request
from decimal import Decimal

MARKET_URL = 'https://stock.naver.com/api/domestic/market/stock/default?tradeType=KRX&marketType=ALL&orderType=marketSum&startIdx=0&pageSize=4000'

def fetch_json(url):
    with urllib.request.urlopen(url, timeout=40) as response:
        return json.load(response)

def fetch_market_snapshot():
    rows = fetch_json(MARKET_URL)
    if not isinstance(rows, list) or len(rows) < 2000:
        raise ValueError('Market-cap universe incomplete')
    return {row['itemcode']: row for row in rows}, dt.datetime.now(dt.timezone.utc).isoformat()

def build_representatives(code, rows, market, observed_at, official_sources=None):
    """Fail closed on missing domestic caps, unknown components, duplicate/date/count issues."""
    url = f'https://stock.naver.com/api/domestic/detail/{code}/ETFComponent'
    dates = {row.get('referenceDate') for row in rows}
    counts = {int(row['componentCount']) for row in rows if row.get('componentCount')}
    stocks, excluded, missing = [], [], []
    eligible_types = {'ST', 'RT', 'IF', 'MF'} if code == '329200' else {'ST'}
    for row in rows:
        ticker, name = row.get('componentItemCode'), row.get('componentName', '')
        isin = row.get('componentIsinCode') or ''
        item = market.get(ticker)
        base = {'code': ticker, 'name': name, 'isin': isin}
        if item and item.get('type') in eligible_types:
            try:
                raw_cap = Decimal(str(item['marketSum']))
                if raw_cap != raw_cap.to_integral_value():
                    raise ValueError('Fractional KRW cap')
                cap = int(raw_cap)
                shares, price = Decimal(str(item['listedStockCnt'])), Decimal(str(item['nowPrice']))
                if cap <= 0 or abs(shares * price - cap) >= Decimal(1000000):
                    raise ValueError('Market cap / shares / price disagree')
                stocks.append(dict(base, name=item['itemname'], marketCapKRW=cap,
                                   quoteSession=item.get('tradingSessionType'),
                                   marketStatus=item.get('marketStatus')))
            except (KeyError, ValueError, ArithmeticError):
                missing.append(dict(base, reason='시총 또는 주식수·가격 검증 미완료'))
        elif (item and item.get('type') not in eligible_types) or isin.startswith('KR7') and ticker and not re.fullmatch(r'[0-9A-Z]{6}', ticker):
            excluded.append(dict(base, category='other', reason='국내 개별주식 외 자산'))
        elif isin.startswith('KRD') or any(word in name for word in ['현금', '예금', 'CASH']):
            excluded.append(dict(base, category='cash', reason='현금·예금'))
        elif isin and not isin.startswith('KR'):
            excluded.append(dict(base, category='foreign', reason='해외 편입종목: 국내 비교범위 제외'))
        elif isin.startswith('KR4') or isin.startswith('KR5'):
            excluded.append(dict(base, category='derivative', reason='파생상품'))
        else:
            missing.append(dict(base, reason='국내 주식 여부 또는 시총 미확인'))
    stocks.sort(key=lambda row: (-row['marketCapKRW'], row['code']))
    duplicate = len({row['code'] for row in stocks}) != len(stocks)
    complete = bool(rows) and len(dates) == 1 and None not in dates and len(counts) == 1 and next(iter(counts)) == len(rows) and not missing and not duplicate
    foreign_count = sum(row['category'] == 'foreign' for row in excluded)
    return {
        'scope': 'etf', 'label': 'ETF 국내 편입종목 시총 상위' if foreign_count or code == '329200' else 'ETF 내 시총 상위',
        'asOf': observed_at, 'marketCapObservedAt': observed_at,
        'universeAsOf': next(iter(dates)) if len(dates) == 1 else None,
        'members': stocks[:3] if complete else [],
        'universeCount': len(stocks) + len(missing), 'verifiedCount': len(stocks),
        'providerComponentCount': next(iter(counts)) if len(counts) == 1 else None,
        'receivedComponentCount': len(rows), 'foreignExcludedCount': foreign_count,
        'status': 'verified' if complete else 'partial',
        'excludedComponents': excluded, 'missingComponents': missing,
        'sourceUrls': [url, MARKET_URL] + list(official_sources or []),
        'includedInstrumentTypes': sorted(eligible_types),
        'methodology': ('리츠·인프라 ETF는 상장 리츠(RT)·인프라(IF)·부동산펀드(MF)를 포함합니다. ' if code == '329200' else '') + 'ETF 구성목록의 국내 개별주식을 시가총액(KRW 공급사 원자료, 백만원 단위 정밀도) 내림차순으로 정렬했습니다. 편입비중 순위나 업종 전체 순위가 아닙니다. 해외주식·현금·파생상품·ETF는 제외합니다. 시총은 표시된 수집시각의 공급사 스냅샷으로 정규장 확정 시총이 아니며 시간외 시세를 포함할 수 있습니다. 구성목록 기준일과 시총 관측시각을 별도로 표시합니다.'
    }

def collect_representatives(code, market, observed_at, official_sources=None):
    return build_representatives(code, fetch_json(f'https://stock.naver.com/api/domestic/detail/{code}/ETFComponent'), market, observed_at, official_sources)


def build_weight_representatives(code, rows, observed_at, official_sources=None):
    """Top three actual non-cash holdings by portfolio weight, including foreign assets."""
    import math
    dates={r.get('referenceDate') for r in rows}
    counts={str(r.get('componentCount')) for r in rows}
    holdings=[];excluded=[];missing=[];identities=set()
    for row in rows:
        name=row.get('componentName') or ''
        isin=row.get('componentIsinCode') or ''
        key=isin or row.get('componentItemCode') or name
        if key in identities:
            missing.append({'name':name,'reason':'중복 구성종목'})
        identities.add(key)
        if isin.startswith('KRD') or any(word in name.upper() for word in ['현금','예금','CASH']):
            excluded.append({'name':name,'category':'cash'});continue
        if isin.startswith(('KR4','KR5')):
            excluded.append({'name':name,'category':'derivative'});continue
        try:
            weight=float(row['weight'])
            if not math.isfinite(weight) or not 0<=weight<=100 or not name or not key:raise ValueError()
            holdings.append({'code':row.get('componentItemCode'),'name':name,'isin':isin,'weightPct':weight})
        except (KeyError,ValueError,TypeError):
            missing.append({'name':name,'reason':'편입비중 미확인'})
    holdings.sort(key=lambda r:(-r['weightPct'],r['isin'] or r['name']))
    complete=bool(rows) and len(dates)==1 and None not in dates and len(counts)==1 and counts=={str(len(rows))} and not missing
    return {'scope':'etf','basis':'portfolioWeight','label':'ETF 편입비중 상위','asOf':observed_at,'universeAsOf':next(iter(dates)) if len(dates)==1 else None,'members':holdings[:3] if complete else [],'holdings':holdings,'universeCount':len(holdings)+len(missing),'verifiedCount':len(holdings),'providerComponentCount':next(iter(counts)) if len(counts)==1 else None,'receivedComponentCount':len(rows),'status':'verified' if complete else 'partial','excludedComponents':excluded,'missingComponents':missing,'sourceUrls':[f'https://stock.naver.com/api/domestic/detail/{code}/ETFComponent']+list(official_sources or []),'methodology':'NAVER 구성목록의 실제 편입비중(%) 내림차순 상위 3종목입니다. 국내·해외 편입자산을 포함하고 현금·예금·파생상품은 제외합니다. 개별 기업 시가총액 순위가 아닙니다. 구성 기준일과 수집 시각을 분리하며, 비중이 미확인인 경우 시총으로 대체하지 않습니다.'}


def collect_weight_representatives(code, observed_at, official_sources=None):
    return build_weight_representatives(code,fetch_json(f'https://stock.naver.com/api/domestic/detail/{code}/ETFComponent'),observed_at,official_sources)
