"""Best-effort Yahoo Finance research feed. Missing values remain absent, never fabricated."""
import datetime as dt,json,os,sys,time
from pathlib import Path
import yfinance as yf
ROOT=Path(__file__).resolve().parents[1]
rows=json.loads((ROOT/'data/companies.json').read_text())
old=json.loads((ROOT/'data/market.json').read_text())
stocks=old.get('stocks',{})
COUNTRY_SUFFIX={'한국':'.KS','일본':'.T','대만':'.TW','독일':'.DE','네덜란드':'.AS','프랑스':'.PA','스위스':'.SW','오스트리아':'.VI','이탈리아':'.MI','중국':'.SS','홍콩':'.HK'}
EXCEPTIONS={'TSE:285A':'285A.T','KRX:000660':'000660.KS','KRX:005930':'005930.KS','NYSE:ASX':'ASX','NASDAQ:MU':'MU'}

def lookup(r):
    sym=r['symbol']; t=r['ticker']; country=r['country']
    if sym in EXCEPTIONS:return EXCEPTIONS[sym]
    if country=='한국':return t+('.KQ' if sym.startswith('KOSDAQ:') else '.KS')
    if country=='중국':return t+('.SS' if t.startswith(('6','5')) else '.SZ')
    if country=='홍콩':return t.zfill(4)+'.HK'
    if country=='대만':return t+'.TW'
    if country in COUNTRY_SUFFIX:return t+COUNTRY_SUFFIX[country]
    return t

def fnum(x):
    try:
        n=float(x)
        return n if n==n and abs(n)!=float('inf') else None
    except Exception:return None

def fetch_prices(obj):
    try:
        h=obj.history(period='5y',interval='1d',auto_adjust=True,raise_errors=False)
        if h is None or h.empty:return []
        return [[str(i.date()),round(float(row['Close']),5)] for i,row in h.iterrows() if fnum(row.get('Close')) is not None]
    except Exception:return []

def first_available(frame,candidates):
    for item in candidates:
        if item in frame.index:return frame.loc[item]
    return None

def fetch_quarters(obj):
    try:
        inc=obj.quarterly_income_stmt
        if inc is None or inc.empty:return []
        rv=first_available(inc,['Total Revenue','Operating Revenue'])
        op=first_available(inc,['Operating Income','Operating Income As Reported'])
        if rv is None:return []
        out=[]
        for col in sorted(inc.columns,reverse=True)[:4]:
            rev=fnum(rv.get(col));oper=fnum(op.get(col)) if op is not None else None
            out.append({'date':str(col.date()) if hasattr(col,'date') else str(col)[:10], 'revenue':round(rev/1e6,3) if rev is not None else None,'operatingIncome':round(oper/1e6,3) if oper is not None else None})
        return out
    except Exception:return []

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
    limit=int(os.getenv('LIMIT','0'))
    if limit:keys=keys[:limit]
    fx=old.get('fx',1341)
    try:
        pair=yf.Ticker('KRW=X').history(period='5d')
        if not pair.empty:fx=round(float(pair['Close'].iloc[-1]),2)
    except Exception:pass
    ok=0
    for i,symbol in enumerate(keys,1):
        r=unique[symbol];ticker=lookup(r)
        current=dict(stocks.get(symbol,{}))
        try:
            t=yf.Ticker(ticker)
            p=fetch_prices(t)
            if p:
                current.update({'prices':p,'close':p[-1][1],'updated':now,'sourceTicker':ticker})
                ok+=1
            # Info endpoint can be rate limited and may be unavailable: leave missing values empty.
            info=fetch_info(t)
            cap=fnum(info.get('marketCap'))
            if cap is not None and cap>0:
                currency=(info.get('currency') or info.get('financialCurrency') or 'USD')
                # yfinance marketCap is denominated in instrument currency; convert if FX obtainable.
                try:
                    if currency!='USD':
                        cross=yf.Ticker(currency+'USD=X').history(period='5d')
                        if cross is None or cross.empty:
                            inv=yf.Ticker('USD'+currency+'=X').history(period='5d')
                            cap=cap/float(inv['Close'].iloc[-1]) if not inv.empty else None
                        else:cap=cap*float(cross['Close'].iloc[-1])
                except Exception:cap=None
                if cap is not None:current['marketCapUSD']=round(cap)
            current['priceCurrency']=info.get('currency') or current.get('priceCurrency') or ''
            current['reportingCurrency']=info.get('financialCurrency') or current.get('reportingCurrency') or info.get('currency') or ''
            if weekly:
                q=fetch_quarters(t)
                if q:current['quarters']=q;current['finSource']='Yahoo Finance / yfinance (verify filings)'
            stocks[symbol]=current
            print(f'{i}/{len(keys)} {symbol} -> {ticker}: {len(p)} prices, {len(current.get("quarters",[]))} quarters',flush=True)
        except Exception as e:print('ERROR',symbol,str(e)[:100],flush=True)
        if i%25==0:
            (ROOT/'data/market.json').write_text(json.dumps({'updated':now,'fx':fx,'stocks':stocks},ensure_ascii=False))
        time.sleep(.15)
    (ROOT/'data/market.json').write_text(json.dumps({'updated':now,'fx':fx,'stocks':stocks},ensure_ascii=False))
    print('DONE',ok,'/',len(keys),'quotes fetched')

if __name__=='__main__':main()
