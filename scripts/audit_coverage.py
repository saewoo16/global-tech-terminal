"""Offline, all-company coverage audit and regression gate (no paid API required)."""
import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from data_quality import ALIASES, clean_prices, number, valid_date, write_json

ROOT = Path(__file__).resolve().parents[1]


def audit(companies, market):
    unique = {r['symbol']: r for r in companies}
    stocks = market.get('stocks', {})
    result, errors = [], []
    today = dt.datetime.now(dt.timezone.utc).date()
    for symbol, company in sorted(unique.items()):
        item = stocks.get(symbol, {})
        prices = clean_prices(item.get('prices'))
        quarters = item.get('quarters', [])
        revenue = sum(number(q.get('revenue')) is not None for q in quarters[:4])
        operating = sum(number(q.get('operatingIncome')) is not None for q in quarters[:4])
        complete = sum(number(q.get('revenue')) is not None and number(q.get('operatingIncome')) is not None for q in quarters[:4])
        latest = prices[-1][0] if prices else ''
        stale = not latest or (today-dt.date.fromisoformat(latest)).days > 7
        if prices != item.get('prices', []):
            errors.append(f'{symbol}: invalid/duplicate/unsorted chart points')
        if len({q.get('date') for q in quarters}) != len(quarters):
            errors.append(f'{symbol}: duplicate financial period dates')
        for q in quarters:
            if not valid_date(q.get('date')):
                errors.append(f'{symbol}: invalid/future quarter {q.get("date")}')
            if q.get('reportedCurrency') and q['reportedCurrency'] != item.get('reportingCurrency'):
                errors.append(f'{symbol}: mismatched financial currency at {q["date"]}')
            for field in ('revenue','operatingIncome'):
                if q.get(field) is not None and number(q[field]) is None:
                    errors.append(f'{symbol}: non-finite {field}')
            if number(q.get('revenue')) is not None and q['revenue'] < 0:
                errors.append(f'{symbol}: negative revenue')
        result.append({'symbol':symbol,'name':company['name'],'country':company['country'],
                       'chart_points':len(prices),'latest_price':latest,'stale_price':stale,
                       'market_cap':number(item.get('marketCapUSD')) is not None,
                       'quarters':len(quarters),'revenue_quarters':revenue,'operating_quarters':operating,
                       'complete_quarters':complete,'financial_status':item.get('financialStatus','unknown'),
                       'latest_quarter':quarters[0].get('date','') if quarters else '',
                       'note':item.get('financialNote','')})
    summary = {'companies':len(unique), 'charts':sum(r['chart_points']>=2 for r in result),
               'missing_charts':sum(r['chart_points']<2 for r in result),
               'missing_market_caps':sum(not r['market_cap'] for r in result),
               'stale_prices':sum(r['stale_price'] for r in result),
               'four_complete_quarters':sum(r['complete_quarters']==4 for r in result),
               'no_financial_quarters':sum(not r['quarters'] for r in result),
               'not_disclosed_quarterly':sum(r['financial_status']=='not_disclosed' for r in result)}
    return {'checkedAt':dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
            'summary':summary,'companies':result,'errors':errors}


def regressions(current, baseline):
    previous={ALIASES.get(r['symbol'],r['symbol']):r for r in baseline['companies']}
    errors=[]
    for row in current['companies']:
        before=previous.get(row['symbol'])
        if not before:continue
        if before['chart_points']>=2 and row['chart_points']<2:
            errors.append(f'{row["symbol"]}: usable chart was lost')
        if before['market_cap'] and not row['market_cap']:
            errors.append(f'{row["symbol"]}: market cap was lost')
        newer_period=row.get('latest_quarter','')>before.get('latest_quarter','')
        if row['complete_quarters']<before['complete_quarters'] and row['financial_status']!='not_disclosed' and not newer_period:
            errors.append(f'{row["symbol"]}: complete financial quarter coverage decreased')
    return errors


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--baseline',type=Path)
    args=parser.parse_args()
    companies=json.loads((ROOT/'data/companies.json').read_text())
    market=json.loads((ROOT/'data/market.json').read_text())
    report=audit(companies,market)
    if args.baseline and args.baseline.exists():
        baseline=json.loads(args.baseline.read_text())
        # Historical renamed company IDs are normalized before comparison.
        for old,new in ALIASES.items():
            if old in baseline.get('stocks',{}):baseline['stocks'][new]=baseline['stocks'][old]
        report['errors']+=regressions(report,audit(companies,baseline))
    write_json(ROOT/'data/coverage.json',report)
    with (ROOT/'data/coverage.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(report['companies'][0]))
        writer.writeheader();writer.writerows(report['companies'])
    print(json.dumps(report['summary'],ensure_ascii=False,indent=2))
    for row in report['companies']:
        if row['chart_points']<2 or row['complete_quarters']<4:
            print('COVERAGE_GAP',row['symbol'],row['name'],row['financial_status'],f'{row["complete_quarters"]}/4',row['note'])
    for error in report['errors']:print('::error::'+error)
    if report['errors']:raise SystemExit(1)


if __name__=='__main__':main()
