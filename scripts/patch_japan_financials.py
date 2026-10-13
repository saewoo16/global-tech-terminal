"""Free Japanese earnings backfill for Global Tech Terminal.
Reads data/companies.json and data/market.json. Preserves existing prices/caps.
Only inserts independently reported quarters or a mathematically validated FY Q4.
No API key required. Yahoo availability varies by issuer.
"""
import json, math, time, datetime as dt
from pathlib import Path
import yfinance as yf

ROOT = Path(__file__).resolve().parents[1]
COMPANIES = ROOT/'data'/'companies.json'
MARKET = ROOT/'data'/'market.json'
REVENUE = ('Total Revenue','Operating Revenue')
OPERATING = ('Operating Income','Operating Income As Reported')

def number(x):
    try:
        v=float(x)
        return v if math.isfinite(v) else None
    except (ValueError,TypeError): return None

def row(frame, names):
    for name in names:
        if name in frame.index:
            x=frame.loc[name]
            return x.iloc[0] if getattr(x,'ndim',1)>1 else x
    return None

def statement(ticker, freq):
    try:
        df=ticker.get_income_stmt(freq=freq)
        if df is not None and not df.empty:return df
    except Exception as exc:
        print('STATEMENT_ERROR',freq,str(exc)[:140],flush=True)
    try:
        return ticker.quarterly_income_stmt if freq=='quarterly' else ticker.income_stmt
    except Exception:return None

def parse(frame):
    result={}
    if frame is None or frame.empty:return result
    rev=row(frame,REVENUE); op=row(frame,OPERATING)
    if rev is None:return result
    for col in frame.columns:
        date=str(col.date()) if hasattr(col,'date') else str(col)[:10]
        r=number(rev.get(col)); o=number(op.get(col)) if op is not None else None
        if r is None or r<0:continue
        result[date]={'date':date,'revenue':round(r/1e6,3),
                      'operatingIncome':round(o/1e6,3) if o is not None else None}
    return result

def derive_q4(quarters, annual):
    for fy, annual_row in annual.items():
        if fy in quarters:continue
        end=dt.date.fromisoformat(fy)
        bins=[[],[],[]]
        for day, q in quarters.items():
            lag=(end-dt.date.fromisoformat(day)).days
            for i,(lo,hi) in enumerate(((55,125),(145,215),(235,310))):
                if lo<=lag<=hi:bins[i].append(q)
        if any(len(b)!=1 for b in bins):continue
        prev=[b[0] for b in bins]
        r=round(annual_row['revenue']-sum(x['revenue'] for x in prev),3)
        if r<0:continue
        op=None
        if annual_row['operatingIncome'] is not None and all(x['operatingIncome'] is not None for x in prev):
            op=round(annual_row['operatingIncome']-sum(x['operatingIncome'] for x in prev),3)
        quarters[fy]={'date':fy,'revenue':r,'operatingIncome':op}
    return quarters

def main():
    companies=json.loads(COMPANIES.read_text(encoding='utf-8'))
    market=json.loads(MARKET.read_text(encoding='utf-8'))
    stocks=market.setdefault('stocks',{})
    japan={r['symbol']:r for r in companies if r.get('country')=='일본' and r.get('symbol','').startswith('TSE:')}
    full=0; improved=0
    for i,(symbol,company) in enumerate(japan.items(),1):
        ticker=str(company['ticker'])+'.T'
        item=stocks.setdefault(symbol,{})
        previous={str(q.get('date')):q for q in item.get('quarters',[]) if isinstance(q,dict) and q.get('date')}
        try:
            t=yf.Ticker(ticker)
            q=parse(statement(t,'quarterly'))
            a=parse(statement(t,'yearly'))
            q=derive_q4(q,a)
            for date,new in q.items():
                old=previous.get(date)
                if old is None or (old.get('operatingIncome') is None and new['operatingIncome'] is not None):
                    previous[date]=new
            merged=sorted(previous.values(),key=lambda x:x['date'],reverse=True)[:4]
            if len(merged)>len(item.get('quarters',[])):improved+=1
            if merged:
                item['quarters']=merged
                item['reportingCurrency']=item.get('reportingCurrency') or 'JPY'
                item['financialUpdated']=dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')
                item['finSource']='Yahoo Finance (quarterly + verified FY Q4 backfill); verify official IR'
            if len(merged)==4 and all(q.get('operatingIncome') is not None for q in merged):full+=1
            print(f'{i}/{len(japan)} {company["name"]} ({ticker}) {len(merged)}/4 quarters, {sum(q.get("operatingIncome") is not None for q in merged)} operating income',flush=True)
        except Exception as exc:
            print('FAILED',ticker,str(exc)[:180],flush=True)
        time.sleep(.25)
    market['stocks']=stocks
    MARKET.write_text(json.dumps(market,ensure_ascii=False),encoding='utf-8')
    print(f'JAPAN_DONE total={len(japan)} full_4q_with_operating_income={full} improved_count={improved}',flush=True)
    print('NOTE: If Yahoo has no quarterly statements, this script cannot reconstruct them from official IR. No fabricated values.',flush=True)

if __name__=='__main__':main()
