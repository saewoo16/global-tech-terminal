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

def replace_market_cap(current, cap_usd, ticker, checked_at, *, currency=None, local=None, fx=None):
    """Replace value and its provenance together; observation time is not a price date."""
    for key in list(current):
        if key.startswith('marketCap'):
            current.pop(key)
    current.update(marketCapUSD=round(cap_usd), marketCapUpdated=checked_at,
                   marketCapSource='Yahoo Finance marketCap; provider observation, not a certified closing-date capitalization',
                   marketCapSourceUrl='https://finance.yahoo.com/quote/'+quote(ticker, safe='')+'/')
    if currency is not None:
        current['marketCapCurrency'] = currency
    if fx is not None:
        rate, metadata = fx
        current.update(marketCapLocal=local, marketCapFX=rate, marketCapFXMetadata=dict(metadata),
                       marketCapMethod='provider_market_cap_converted_with_completed_daily_fx')

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
        return completed_daily_points(result), result['meta']
    except Exception as exc:
        print('CHART_FALLBACK_ERROR',ticker,str(exc)[:100],flush=True)
        return [],{}


def completed_daily_observations(result, now):
    """Use actual adjusted daily bars only after their source session has ended.

    Yahoo sometimes omits the latest daily close in range=5y while range=1d
    supplies it. Never substitute regularMarketPrice or an unadjusted close.
    The provider session timestamps, not a guessed weekday calendar, gate an
    in-progress session. Older dated bars precede its current session.
    """
    try:
        meta = result['meta']
        zone = ZoneInfo(meta['exchangeTimezoneName'])
        regular = meta['currentTradingPeriod']['regular']
        start = dt.datetime.fromtimestamp(regular['start'], zone)
        end = dt.datetime.fromtimestamp(regular['end'], dt.timezone.utc)
        if end <= start:
            return []
        adjusted = result['indicators'].get('adjclose', [{}])[0].get('adjclose', [])
        points = {}
        today = now.astimezone(zone).date()
        for stamp, value in zip(result.get('timestamp', []), adjusted):
            moment = dt.datetime.fromtimestamp(stamp, zone)
            day = moment.date()
            if day > start.date() or (day == start.date() and now < end):
                continue
            # A source pointing at a future session has not confirmed today's close.
            if day == today and day < start.date():
                continue
            value = number(value)
            if moment > now or value is None or value <= 0:
                continue
            if day not in points or stamp >= points[day][1]:
                points[day] = (value, stamp)
        return [(day.isoformat(), *points[day]) for day in sorted(points)]
    except (IndexError, KeyError, OSError, TypeError, ValueError, OverflowError):
        return []


def completed_daily_points(result, now=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    return clean_prices([[day, round(value, 5)]
                         for day, value, _ in completed_daily_observations(result, now)])


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
    # Every collection path uses source session-end timestamps. Never merge
    # unfiltered history with a separately gated latest bar.
    prices, _ = chart_fallback(obj.ticker)
    latest = latest_completed_daily(obj.ticker)
    return clean_prices(prices + latest)


def completed_fx_observation(now=None):
    """Reference USD/KRW uses a completed source session, never today's live FX bar."""
    now = now or dt.datetime.now(dt.timezone.utc)
    url = 'https://query2.finance.yahoo.com/v8/finance/chart/KRW=X?range=5d&interval=1d&includePrePost=false'
    try:
        with urlopen(Request(url, headers={'User-Agent': 'Mozilla/5.0'}), timeout=20) as response:
            result = json.load(response)['chart']['result'][0]
        points = completed_daily_points(result, now)
        if points:
            day, value = points[-1]
            return round(value, 2), {'asOf': day, 'observedAt': now.isoformat(), 'sourceUrl': url,
                                    'basis': 'Completed provider FX daily session; not an equity closing-time spot rate',
                                    'timezone': result['meta']['exchangeTimezoneName'],
                                    'sourceCurrentRegularEnd': result['meta']['currentTradingPeriod']['regular']['end']}
    except Exception as exc:
        print('COMPLETED_FX_UNAVAILABLE', str(exc)[:100], flush=True)
    return None, None


def completed_market_cap_fx(currency, now=None):
    """Return USD per unit of listing currency, with the exact source bar and direction."""
    pairs = ((currency, 'USD', currency+'USD=X'),
             ('USD', currency, 'USD'+currency+'=X'),
             ('USD', currency, currency+'=X'))
    for base, quoted, ticker in pairs:
        url = ('https://query2.finance.yahoo.com/v8/finance/chart/'+quote(ticker, safe='')
               +'?range=5d&interval=1d&includePrePost=false')
        try:
            with urlopen(Request(url, headers={'User-Agent': 'Mozilla/5.0'}), timeout=20) as response:
                result = json.load(response)['chart']['result'][0]
            observed = now or dt.datetime.now(dt.timezone.utc)
            meta = result['meta']
            expected_symbols = {base+quoted+'=X'}
            if base == 'USD':
                expected_symbols.add(quoted+'=X')
            if (meta.get('symbol') not in expected_symbols or meta.get('currency') != quoted
                    or meta.get('instrumentType') != 'CURRENCY' or meta.get('dataGranularity') != '1d'):
                continue
            points = completed_daily_observations(result, observed)
            if not points:
                continue
            day, source_rate, stamp = points[-1]
            rate = source_rate if base == currency else 1 / source_rate
            if number(rate) is None or rate <= 0:
                continue
            regular = meta['currentTradingPeriod']['regular']
            return rate, {
                'asOf': day, 'observedAt': observed.isoformat(),
                'baseCurrency': currency, 'quoteCurrency': 'USD',
                'sourceBaseCurrency': base, 'sourceQuoteCurrency': quoted, 'sourceRate': source_rate,
                'source': 'Yahoo Finance chart adjusted daily close', 'sourceTicker': meta['symbol'],
                'sourceUrl': url, 'timezone': meta['exchangeTimezoneName'], 'sourceBarTimestamp': stamp,
                'sourceCurrentRegularStart': regular['start'], 'sourceCurrentRegularEnd': regular['end'],
                'basis': 'Completed provider FX daily session; not an equity closing-time spot rate',
            }
        except Exception:
            # Try the next pair representation, never an ungated history/quote value.
            continue
    print('MARKET_CAP_FX_UNAVAILABLE', currency, flush=True)
    return None


def refresh_market_cap(current, info, ticker, checked_at, fx_cache):
    """Keep all prior cap fields together unless both the new cap and conversion are available."""
    local = number(info.get('marketCap'))
    currency = info.get('currency')
    # Financial reporting currency can differ from the listing currency (e.g. ADRs).
    if (local is None or local <= 0 or not isinstance(currency, str) or len(currency) != 3
            or not currency.isascii() or not currency.isalpha() or not currency.isupper()):
        return
    if currency == 'USD':
        replace_market_cap(current, local, ticker, checked_at, currency=currency)
        return
    if currency not in fx_cache:
        fx_cache[currency] = completed_market_cap_fx(currency)
    fx = fx_cache[currency]
    if fx is None:
        return
    converted = local * fx[0]
    if number(converted) is not None and round(converted) > 0:
        replace_market_cap(current, converted, ticker, checked_at, currency=currency, local=local, fx=fx)


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

def preserve_verified_price_history(previous, incoming):
    """Append only a compatible completed series; corporate-action revisions need review."""
    if not previous:
        return incoming, None
    lookup = dict(incoming)
    for day, value in previous:
        if day in lookup and abs(lookup[day] - value) > max(0.0001, abs(value) * 1e-6):
            return previous, 'Adjusted historical values changed; retained verified series pending source review.'
    last = previous[-1][0]
    return previous + [point for point in incoming if point[0] > last], None

def main():
    unique={r['symbol']:r for r in rows}
    now=dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')
    # Daily completed-session prices and cap observations; official filings use separate verified backfills.
    keys=list(unique)
    selected=set(filter(None,os.environ.get('SYMBOLS','').split(',')))
    if selected:keys=[key for key in keys if key in selected]
    limit=int(os.getenv('LIMIT','0'))
    if limit:keys=keys[:limit]
    fx=old.get('fx',1341)
    fx_metadata = old.get('fxMetadata')
    completed_fx, metadata = completed_fx_observation()
    if completed_fx is not None:
        fx, fx_metadata = completed_fx, metadata
    ok=0
    fx_cache={}
    for i,symbol in enumerate(keys,1):
        r=unique[symbol];ticker=lookup(r)
        current=dict(stocks.get(symbol,{}))
        # A previous run may contain wrong-exchange chart data: never keep that chart.
        if current.get('sourceTicker') and current['sourceTicker']!=ticker:
            for key in list(current):
                if key in ('prices', 'close', 'quarters') or key.startswith('marketCap'):
                    current.pop(key)
            print('RESET WRONG TICKER:',symbol,current.get('sourceTicker'),'->',ticker,flush=True)
        try:
            t=yf.Ticker(ticker)
            p=fetch_prices(t)
            if not p:
                time.sleep(1)
                p=fetch_prices(t)
            if p:
                p, review = preserve_verified_price_history(current.get('prices', []), p)
                if review:
                    current['priceRevisionStatus'] = review
                else:
                    current.pop('priceRevisionStatus', None)
            if p and not review:
                current.update({'prices':p,'close':p[-1][1],'updated':now,'sourceTicker':ticker})
                ok+=1
            # Info endpoint can be rate limited and may be unavailable: leave missing values empty.
            info=fetch_info(t)
            current['priceCheckedAt']=now
            refresh_market_cap(current, info, ticker, dt.datetime.now(dt.timezone.utc).isoformat(), fx_cache)
            current['priceCurrency']=info.get('currency') or current.get('priceCurrency') or ''
            current['reportingCurrency']=info.get('financialCurrency') or current.get('reportingCurrency') or info.get('currency') or ''
            # Publication requires verified official filings. Aggregator quarterly
            # statements are research candidates, never an automatic replacement
            # for issuer fiscal dates, accounting scope, or verification dates.
            stocks[symbol]=annotate(symbol,current)
            print(f'{i}/{len(keys)} {symbol} -> {ticker}: {len(p)} prices, {len(current.get("quarters",[]))} quarters',flush=True)
        except Exception as e:print('ERROR',symbol,str(e)[:100],flush=True)
        time.sleep(.15)
    if not ok and keys:
        raise RuntimeError('No price requests succeeded; retained existing market.json instead of publishing a false refresh')
    payload = {'updated':now,'fx':fx,'stocks':stocks}
    if fx_metadata is not None:payload['fxMetadata'] = fx_metadata
    write_json(ROOT/'data/market.json',payload)
    with_quarters=sum(bool(stocks.get(k,{}).get('quarters')) for k in keys)
    no_quarters=[f'{unique[k]["name"]} ({lookup(unique[k])})' for k in keys if not stocks.get(k,{}).get('quarters')]
    print('DONE',ok,'/',len(keys),'quotes fetched;',with_quarters,'/',len(keys),'with financials',flush=True)
    print('FINANCIALS_MISSING_EXAMPLES:',', '.join(no_quarters[:20]),flush=True)

if __name__=='__main__':main()
