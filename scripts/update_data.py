"""Best-effort Yahoo Finance research feed. Missing values remain absent, never fabricated."""
import datetime as dt,json,os,sys,time
from urllib.request import Request, urlopen
from urllib.parse import quote
from zoneinfo import ZoneInfo
from pathlib import Path
import yfinance as yf
from data_quality import annotate, clean_prices, merge_quarters, migrate_symbols, number, write_json
ROOT=Path(__file__).resolve().parents[1]
rows=json.loads((ROOT/'data/companies.json').read_text())
old=json.loads((ROOT/'data/market.json').read_text())
stocks=migrate_symbols(old.get('stocks',{}))
# Exchange listing takes priority over headquarters / incorporation country.
# For KRX-only source entries, use a maintained KOSDAQ whitelist.
KOSDAQ_CODES = {'033160', '095340', '183300', '005290', '089030', '101160', '357780', '104830', '356860', '074600', '166090', '036930', '058470', '222800', '102710', '092070', '077360'}

def lookup(r):
    sym=r['symbol']; t=str(r['ticker']); country=r['country']
    ex=sym.split(':',1)[0]
    if ex in ('NYSE','NASDAQ','AMEX'):return t
    if ex=='TSE':return t+'.T'
    if ex=='TWSE':return t+'.TW'
    if ex=='TPEX':return t+'.TWO'
    if ex=='HKEX':return t.zfill(4)+'.HK'
    if ex=='SSE':return t+'.SS'
    if ex=='SZSE':return t+'.SZ'
    if ex=='KRX':return t+('.KQ' if t in KOSDAQ_CODES else '.KS')
    if ex=='XETR':return t+'.DE'
    if ex=='SIX':return t+'.SW'
    if ex=='VIE':return t+'.VI'
    if ex=='MIL':return t+'.MI'
    if ex=='EURONEXT':
        suffix={'네덜란드':'.AS','프랑스':'.PA','벨기에':'.BR'}.get(country)
        if suffix:return t+suffix
    print('UNMAPPED_EXCHANGE',sym,country,flush=True)
    return t

def fnum(x):
    try:
        n=float(x)
        return n if n==n and abs(n)!=float('inf') else None
    except Exception:return None

def chart_fallback(ticker):
    """Public Yahoo chart endpoint, with adjusted closes and exchange-local dates."""
    try:
        url='https://query2.finance.yahoo.com/v8/finance/chart/'+quote(ticker,safe='')+'?range=5y&interval=1d'
        request=Request(url,headers={'User-Agent':'Mozilla/5.0'})
        with urlopen(request,timeout=20) as response:
            result=json.load(response)['chart']['result'][0]
        values=result['indicators'].get('adjclose',[{}])[0].get('adjclose')
        if values is None:
            # Do not silently substitute unadjusted prices for adjusted returns.
            return [], {}
        zone=ZoneInfo(result['meta']['exchangeTimezoneName'])
        points=[[dt.datetime.fromtimestamp(stamp,zone).date().isoformat(),round(value,5)]
                for stamp,value in zip(result['timestamp'],values)
                if fnum(value) is not None]
        return clean_prices(points),result['meta']
    except Exception as exc:
        print('CHART_FALLBACK_ERROR',ticker,str(exc)[:100],flush=True)
        return [],{}


def completed_daily_points(result, now=None):
    """Use actual adjusted daily bars only after their source session has ended.

    Yahoo sometimes omits the latest daily close in range=5y while range=1d
    supplies it. Never substitute regularMarketPrice or an unadjusted close.
    The provider session timestamps, not a guessed weekday calendar, gate an
    in-progress session. Older dated bars precede its current session.
    """
    now = now or dt.datetime.now(dt.timezone.utc)
    try:
        meta = result['meta']
        zone = ZoneInfo(meta['exchangeTimezoneName'])
        regular = meta['currentTradingPeriod']['regular']
        session_day = dt.datetime.fromtimestamp(regular['start'], zone).date()
        end = dt.datetime.fromtimestamp(regular['end'], dt.timezone.utc)
        adjusted = result['indicators'].get('adjclose', [{}])[0].get('adjclose', [])
        points = []
        for stamp, value in zip(result.get('timestamp', []), adjusted):
            day = dt.datetime.fromtimestamp(stamp, zone).date()
            if day > session_day or (day == session_day and now < end):
                continue
            if day > now.astimezone(zone).date() or fnum(value) is None or value <= 0:
                continue
            points.append([day.isoformat(), round(value, 5)])
        return clean_prices(points)
    except (KeyError, TypeError, ValueError, OverflowError):
        return []


def latest_completed_daily(ticker):
    try:
        url = 'https://query2.finance.yahoo.com/v8/finance/chart/' + quote(ticker, safe='') + '?range=1d&interval=1d'
        with urlopen(Request(url, headers={'User-Agent': 'Mozilla/5.0'}), timeout=20) as response:
            result = json.load(response)['chart']['result'][0]
        return completed_daily_points(result)
    except Exception as exc:
        print('LATEST_DAILY_ERROR', ticker, str(exc)[:100], flush=True)
        return []


def fetch_prices(obj):
    prices = []
    try:
        h=obj.history(period='5y',interval='1d',auto_adjust=True,raise_errors=False,timeout=20)
        if h is not None and not h.empty:
            prices = clean_prices([[str(i.date()),round(float(row['Close']),5)] for i,row in h.iterrows() if fnum(row.get('Close')) is not None])
    except Exception:pass
    if not prices:
        prices = chart_fallback(obj.ticker)[0]
    # Repair the range-specific final-bar omission without discarding history.
    latest = latest_completed_daily(obj.ticker)
    return clean_prices(prices + latest)

def first_available(frame,candidates):
    for item in candidates:
        if item in frame.index:return frame.loc[item]
    return None

def fetch_quarters(obj):
    try:
        inc=obj.quarterly_income_stmt
        if inc is None or inc.empty:
            inc=obj.get_income_stmt(freq='quarterly')
        if inc is None or inc.empty:
            print('FINANCIALS_EMPTY: Yahoo provided no quarterly income statement',flush=True)
            return []
        rv=first_available(inc,['Total Revenue','Operating Revenue'])
        op=first_available(inc,['Operating Income As Reported','Operating Income'])
        if rv is None:
            print('FINANCIALS_NO_REVENUE_ROW:',list(inc.index[:15]),flush=True)
            return []
        out=[]
        for col in sorted(inc.columns,reverse=True):
            rev=fnum(rv.get(col));oper=fnum(op.get(col)) if op is not None else None
            if rev is None and oper is None:continue
            out.append({'date':str(col.date()) if hasattr(col,'date') else str(col)[:10], 'revenue':round(rev/1e6,3) if rev is not None else None,'operatingIncome':round(oper/1e6,3) if oper is not None else None})
        return out[:4]
    except Exception as e:
        print('FINANCIAL FETCH ERROR',str(e)[:150],flush=True)
        return []

def fetch_info(obj):
    try:return obj.get_info() or {}
    except Exception:return {}

def main():
    unique={r['symbol']:r for r in rows}
    now=dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')
    # Slow-changing financial data: once every Monday or manually. Daily close and cap: daily.
    weekly=os.environ.get('FETCH_FINANCIALS','0')=='1' or dt.datetime.now(dt.timezone.utc).weekday()==0
    if os.environ.get('PRICE_ONLY')=='1':weekly=False
    keys=list(unique)
    selected=set(filter(None,os.environ.get('SYMBOLS','').split(',')))
    if selected:keys=[key for key in keys if key in selected]
    limit=int(os.getenv('LIMIT','0'))
    if limit:keys=keys[:limit]
    fx=old.get('fx',1341)
    try:
        pair=yf.Ticker('KRW=X').history(period='5d')
        if not pair.empty:fx=round(float(pair['Close'].iloc[-1]),2)
    except Exception:pass
    ok=0
    fx_cache={'USD':1.0}
    for i,symbol in enumerate(keys,1):
        r=unique[symbol];ticker=lookup(r)
        current=dict(stocks.get(symbol,{}))
        # A previous run may contain wrong-exchange chart data: never keep that chart.
        if current.get('sourceTicker') and current['sourceTicker']!=ticker:
            current.pop('prices',None);current.pop('close',None);current.pop('marketCapUSD',None);current.pop('quarters',None)
            print('RESET WRONG TICKER:',symbol,current.get('sourceTicker'),'->',ticker,flush=True)
        try:
            t=yf.Ticker(ticker)
            p=fetch_prices(t)
            if not p:
                time.sleep(1)
                p=fetch_prices(t)
            if p:
                current.update({'prices':p,'close':p[-1][1],'updated':now,'sourceTicker':ticker})
                ok+=1
            # Info endpoint can be rate limited and may be unavailable: leave missing values empty.
            info=fetch_info(t)
            current['priceCheckedAt']=now
            cap=fnum(info.get('marketCap'))
            if cap is not None and cap>0:
                currency=(info.get('currency') or info.get('financialCurrency') or 'USD')
                # yfinance marketCap is denominated in instrument currency; convert if FX obtainable.
                try:
                    if currency!='USD' and currency in fx_cache:
                        cap=cap*fx_cache[currency]
                    elif currency!='USD':
                        original_cap=cap
                        cross=yf.Ticker(currency+'USD=X').history(period='5d')
                        if cross is None or cross.empty:
                            inv=yf.Ticker('USD'+currency+'=X').history(period='5d')
                            cap=cap/float(inv['Close'].iloc[-1]) if not inv.empty else None
                        else:cap=cap*float(cross['Close'].iloc[-1])
                        if cap is not None:fx_cache[currency]=cap/original_cap
                except Exception:cap=None
                if cap is not None:
                    current['marketCapUSD']=round(cap)
                    current['marketCapUpdated']=now
            current['priceCurrency']=info.get('currency') or current.get('priceCurrency') or ''
            current['reportingCurrency']=info.get('financialCurrency') or current.get('reportingCurrency') or info.get('currency') or ''
            # First run (or missing quarters): attempt regardless of weekday.
            # Existing populated financials refresh weekly to limit Yahoo requests.
            incomplete=len(current.get('quarters',[]))<4 or any(q.get('revenue') is None or q.get('operatingIncome') is None for q in current.get('quarters',[]))
            if os.environ.get('PRICE_ONLY')!='1' and (weekly or incomplete):
                q=fetch_quarters(t)
                if q:
                    for quarter in q:
                        quarter.update(source='Yahoo Finance',sourceType='financial_aggregator',sourceUrl='https://finance.yahoo.com/quote/'+ticker+'/financials/',reportedCurrency=current['reportingCurrency'])
                    merged=merge_quarters(current.get('quarters',[]),q)
                    if merged!=current.get('quarters',[]):
                        current['quarters']=merged
                        current['financialUpdated']=now
                    current['finSource']='Public filings / Yahoo Finance (see each quarter)'
                    current['financialCheckedAt']=now
                else:
                    print('NO FINANCIAL DATA',symbol,ticker,flush=True)
            stocks[symbol]=annotate(symbol,current)
            print(f'{i}/{len(keys)} {symbol} -> {ticker}: {len(p)} prices, {len(current.get("quarters",[]))} quarters',flush=True)
        except Exception as e:print('ERROR',symbol,str(e)[:100],flush=True)
        time.sleep(.15)
    if not ok and keys:
        raise RuntimeError('No price requests succeeded; retained existing market.json instead of publishing a false refresh')
    write_json(ROOT/'data/market.json',{'updated':now,'fx':fx,'stocks':stocks})
    with_quarters=sum(bool(stocks.get(k,{}).get('quarters')) for k in keys)
    no_quarters=[f'{unique[k]["name"]} ({lookup(unique[k])})' for k in keys if not stocks.get(k,{}).get('quarters')]
    print('DONE',ok,'/',len(keys),'quotes fetched;',with_quarters,'/',len(keys),'with financials',flush=True)
    print('FINANCIALS_MISSING_EXAMPLES:',', '.join(no_quarters[:20]),flush=True)

if __name__=='__main__':main()
