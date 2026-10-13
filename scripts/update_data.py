"""Best-effort Yahoo Finance research feed. Missing values remain absent, never fabricated."""
import datetime as dt,json,os,sys,time
from pathlib import Path
import yfinance as yf
ROOT=Path(__file__).resolve().parents[1]
rows=json.loads((ROOT/'data/companies.json').read_text())
old=json.loads((ROOT/'data/market.json').read_text())
stocks=old.get('stocks',{})
# Exchange listing takes priority over headquarters / incorporation country.
# For KRX-only source entries, use a maintained KOSDAQ whitelist.
KOSDAQ_CODES = {'033160', '095340', '183300', '005290', '089030', '101160', '108320', '357780', '104830', '356860', '074600', '166090', '036930', '058470', '222800', '102710', '092070', '077360'}

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
        if inc is None or inc.empty:
            inc=obj.get_income_stmt(freq='quarterly')
        if inc is None or inc.empty:
            print('FINANCIALS_EMPTY: Yahoo provided no quarterly income statement',flush=True)
            return []
        rv=first_available(inc,['Total Revenue','Operating Revenue'])
        op=first_available(inc,['Operating Income','Operating Income As Reported'])
        if rv is None:
            print('FINANCIALS_NO_REVENUE_ROW:',list(inc.index[:15]),flush=True)
            return []
        out=[]
        for col in sorted(inc.columns,reverse=True)[:4]:
            rev=fnum(rv.get(col));oper=fnum(op.get(col)) if op is not None else None
            out.append({'date':str(col.date()) if hasattr(col,'date') else str(col)[:10], 'revenue':round(rev/1e6,3) if rev is not None else None,'operatingIncome':round(oper/1e6,3) if oper is not None else None})
        return out
    except Exception as e:
        print('FINANCIAL FETCH ERROR',str(e)[:150],flush=True)
        return []

def fetch_info(obj):
    try:return obj.get_info() or {}
    except Exception:return {}

# Values below are verified against company IR publications as of 2026-10-13.
# Revenue and operating income are stored in MILLIONS of JPY, following the
# existing dashboard schema (which uses millions of reporting currency).
# Updating IR overrides is necessary when subsequent results are published.
IR_VERIFIED = {
    '6723.T': {
        'source': 'Renesas Electronics official IFRS financial releases',
        'quarters': [
            ('2026-06-30', 418.4, 102.1, 'https://www.renesas.com/en/about/newsroom/renesas-reports-financial-results-second-quarter-ended-june-30-2026'),
            # IFRS six-month total less IFRS Q2, NOT non-GAAP amounts
            ('2026-03-31', 380.3, 90.6, 'https://www.renesas.com/en/about/newsroom/renesas-reports-financial-results-second-quarter-ended-june-30-2026'),
            ('2025-12-31', 351.5, 67.2, 'https://www.renesas.com/en/about/newsroom/renesas-reports-financial-results-year-ended-december-31-2025'),
            ('2025-09-30', 335.4, 72.6, 'https://www.renesas.com/en/about/newsroom/renesas-reports-financial-results-third-quarter-ended-september-30-2025'),
        ]
    },
    '7751.T': {
        'source': 'Canon official quarterly financial highlights',
        'quarters': [
            ('2026-06-30', 1180.9, 159.2, 'https://global.canon/en/ir/finance/highlight-q.html'),
            ('2026-03-31', 1093.7, 71.4, 'https://global.canon/en/ir/finance/highlight-q.html'),
            ('2025-12-31', 1321.8, 153.1, 'https://global.canon/en/ir/finance/highlight-q.html'),
            ('2025-09-30', 1104.3, 88.0, 'https://global.canon/en/ir/finance/highlight-q.html'),
        ]
    },
}

# IR pages for firms requiring additional extraction from PDF disclosures;
# these are NOT filled with guessed amounts.
IR_REVIEW_URLS = {
    '4063.T': 'https://www.shinetsu.co.jp/en/ir/ir-data/ir-results/',
    '4901.T': 'https://ir.fujifilm.com/en/investors/ir-materials/earnings-presentations.html',
}

def supplement_verified_ir(ticker, current):
    if ticker in IR_REVIEW_URLS:
        current['irSourceUrl'] = IR_REVIEW_URLS[ticker]
    verified = IR_VERIFIED.get(ticker)
    if not verified:
        return current
    existing = {q['date']: dict(q) for q in current.get('quarters', [])
                if isinstance(q, dict) and q.get('date')}
    for date, revenue_bn, operating_bn, url in verified['quarters']:
        existing[date] = {
            'date': date,
            'revenue': round(revenue_bn * 1000, 3),
            'operatingIncome': round(operating_bn * 1000, 3),
            'sourceUrl': url,
            'source': 'Official company IR',
        }
    current['quarters'] = sorted(existing.values(), key=lambda q: q['date'], reverse=True)[:4]
    current['reportingCurrency'] = 'JPY'
    current['finSource'] = 'Official company IR + Yahoo Finance (where available)'
    return current

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
        # A previous run may contain wrong-exchange chart data: never keep that chart.
        if current.get('sourceTicker') and current['sourceTicker']!=ticker:
            current.pop('prices',None);current.pop('close',None);current.pop('marketCapUSD',None);current.pop('quarters',None)
            print('RESET WRONG TICKER:',symbol,current.get('sourceTicker'),'->',ticker,flush=True)
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
            # First run (or missing quarters): attempt regardless of weekday.
            # Existing populated financials refresh weekly to limit Yahoo requests.
            if weekly or not current.get('quarters'):
                q=fetch_quarters(t)
                if q:
                    current['quarters']=q
                    current['finSource']='Yahoo Finance / yfinance (verify filings)'
                    current['financialUpdated']=now
                else:
                    print('NO FINANCIAL DATA',symbol,ticker,flush=True)
            current = supplement_verified_ir(ticker, current)
            stocks[symbol]=current
            print(f'{i}/{len(keys)} {symbol} -> {ticker}: {len(p)} prices, {len(current.get("quarters",[]))} quarters',flush=True)
        except Exception as e:print('ERROR',symbol,str(e)[:100],flush=True)
        if i%25==0:
            (ROOT/'data/market.json').write_text(json.dumps({'updated':now,'fx':fx,'stocks':stocks},ensure_ascii=False))
        time.sleep(.15)
    (ROOT/'data/market.json').write_text(json.dumps({'updated':now,'fx':fx,'stocks':stocks},ensure_ascii=False))
    with_quarters=sum(bool(stocks.get(k,{}).get('quarters')) for k in keys)
    no_quarters=[f'{unique[k]["name"]} ({lookup(unique[k])})' for k in keys if not stocks.get(k,{}).get('quarters')]
    print('DONE',ok,'/',len(keys),'quotes fetched;',with_quarters,'/',len(keys),'with financials',flush=True)
    print('FINANCIALS_MISSING_EXAMPLES:',', '.join(no_quarters[:20]),flush=True)

if __name__=='__main__':main()
