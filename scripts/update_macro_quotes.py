#!/usr/bin/env python3
"""Collect dated public Investing.com quotes and matching FRED observations.

No private endpoints/authentication. Futures/CFD quotes remain distinct from
FRED spot/index observations. A failed request preserves the old observation,
not its freshness; retrievedAt never substitutes for observedAt/asOf.
"""
from __future__ import annotations
import argparse
from http.client import IncompleteRead
from urllib.error import HTTPError, URLError
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import csv
from datetime import date, datetime, timedelta, timezone
import io
import json
import math
from pathlib import Path
import re
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
INVESTING = {
 'UST10Y': dict(path='rates-bonds/u.s.-10-year-bond-yield', instrumentId='23705', quoteLabel='미국 10년 국채 시장 수익률', unit='%', precision=3, note='Investing.com 시장 수익률. FRED 고정만기 수익률과 산출 기준·관측시각이 다릅니다.'),
 'WTI_FUTURES': dict(path='commodities/crude-oil', instrumentId='8849', quoteLabel='WTI 선물 연계 CFD', unit='USD/배럴', precision=2, note='Investing.com 선물 연계 CFD 호가. 거래소 확정 결제가격이나 아래 FRED WTI 현물가격이 아닙니다.'),
 'BRENT_FUTURES': dict(path='commodities/brent-oil', instrumentId='8833', quoteLabel='Brent 선물 연계 CFD', unit='USD/배럴', precision=2, note='Investing.com 선물 연계 CFD 호가. 거래소 확정 결제가격이나 아래 FRED Brent 현물가격이 아닙니다.'),
 'DXY': dict(path='indices/usdollar', instrumentId='942611', quoteLabel='달러인덱스 DXY · CFD', unit='지수', precision=2, note='Investing.com US Dollar Index CFD. 연준 광의 달러지수 및 달러인덱스 선물(DX)과 구분합니다.'),
 'USDJPY': dict(path='currencies/usd-jpy', instrumentId='3', quoteLabel='달러/엔 (USD/JPY)', unit='엔/달러', precision=2, note='1달러당 엔화. 역수인 JPY/USD와 다릅니다. FRED 환율과 관측시각이 다릅니다.'),
 'USDKRW': dict(path='currencies/usd-krw', instrumentId='650', quoteLabel='달러/원 (USD/KRW)', unit='원/달러', precision=2, note='1달러당 원화. Investing.com 호가이며 서울 외환시장 공식 종가나 FRED 환율과 관측시각이 다를 수 있습니다.'),
}
FRED = {
 'DGS10': ('미국 10년 고정만기 국채 수익률', '%', 2),
 'HQMCB10YRP': ('10년 우량 회사채 액면수익률', '%', 2),
 'DCOILWTICO': ('WTI 원유 현물', 'USD/배럴', 2),
 'DCOILBRENTEU': ('Brent 원유 현물', 'USD/배럴', 2),
 'M1SL': ('미국 M1 통화량', '십억 달러', 1),
 'M2SL': ('미국 M2 통화량', '십억 달러', 1),
 'DEXJPUS': ('달러/엔 · FRED', '엔/달러', 2),
 'DEXKOUS': ('달러/원 · FRED', '원/달러', 2),
}

MONTHLY = {'HQMCB10YRP', 'M1SL', 'M2SL'}
MONEY_SUPPLY = {'M1SL', 'M2SL'}

def iso(now):
    return now.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')

def numeric(value):
    if isinstance(value, bool): raise ValueError('Boolean is not a quote')
    number = float(value)
    if not math.isfinite(number) or number <= 0: raise ValueError('Invalid quote value')
    return number

class SourceUnavailable(Exception):
    """A request failed before a source payload could be validated."""


def fetch_text(url):
    req = Request(url, headers={'User-Agent':'Mozilla/5.0', 'Accept':'text/html,text/csv;q=0.9,*/*;q=0.8'})
    try:
        with urlopen(req, timeout=30) as response:
            if response.status != 200:
                raise SourceUnavailable(f'HTTP {response.status}')
            body = response.read(5_000_001)
    except (HTTPError, URLError, TimeoutError, ConnectionError, IncompleteRead) as error:
        raise SourceUnavailable(f'{type(error).__name__}: {error}') from error
    if len(body) > 5_000_000:
        raise ValueError('Source payload exceeds size limit')
    # Decoding/schema errors are not availability failures.
    return body.decode('utf-8')


def validate_snapshot(payload, now):
    """Reject invalid retained data before fetching, and candidates before writing."""
    if not isinstance(payload, dict) or type(payload.get('schemaVersion')) is not int or payload.get('schemaVersion') != 1:
        raise ValueError('Invalid macro snapshot schema')
    rows = payload.get('rows')
    if not isinstance(rows, list) or len(rows) != len(INVESTING) + len(FRED):
        raise ValueError('Incomplete macro snapshot')
    ids = [row.get('id') if isinstance(row, dict) else None for row in rows]
    if len(set(ids)) != len(ids) or set(ids) != set(INVESTING) | set(FRED):
        raise ValueError('Unexpected or duplicate macro IDs')

    def timestamp(value):
        if not isinstance(value, str):
            raise ValueError('Missing macro timestamp')
        result = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if result.tzinfo is None or result.year < 2000 or result > now + timedelta(minutes=5):
            raise ValueError('Invalid/future macro timestamp')
        return result

    timestamp(payload.get('updatedAt'))
    if any(field in payload for field in ('collectionStatus', 'verifiedCount', 'staleCount')):
        good = sum(row.get('status') == 'verified' for row in rows)
        expected_status = 'complete' if good == len(rows) else 'partial' if good else 'source_unavailable'
        if (payload.get('collectionStatus') != expected_status or type(payload.get('verifiedCount')) is not int
                or payload['verifiedCount'] != good or type(payload.get('staleCount')) is not int
                or payload['staleCount'] != len(rows)-good):
            raise ValueError('Inconsistent macro collection status')
    for row in rows:
        key = row['id']
        if row.get('status') not in ('verified', 'stale'):
            raise ValueError(f'{key}: no verified observation available to retain')
        if type(row.get('value')) not in (int, float):
            raise ValueError(f'{key}: quote must be a JSON number')
        numeric(row['value'])
        observed_date = date.fromisoformat(row['asOf'])
        retrieved = timestamp(row.get('retrievedAt'))
        if observed_date.year < 2000 or observed_date > retrieved.date():
            raise ValueError(f'{key}: invalid observation date')
        if key in INVESTING:
            spec = INVESTING[key]
            expected = ('Investing.com', 'https://www.investing.com/'+spec['path'], spec['unit'], spec['precision'])
            observed = timestamp(row.get('observedAt'))
            source = row.get('sourceObservation', {})
            if (observed.date() != observed_date or observed > retrieved + timedelta(minutes=5)
                    or str(source.get('instrumentId')) != spec['instrumentId']
                    or type(source.get('last')) not in (int, float) or source.get('last') != row['value']
                    or not isinstance(source.get('isOpen'), bool)
                    or abs(datetime.fromtimestamp(float(source['lastUpdateTime'])/1000, timezone.utc).timestamp()-observed.timestamp()) >= 1):
                raise ValueError(f'{key}: inconsistent source observation')
        else:
            _, unit, precision = FRED[key]
            expected = ('FRED', 'https://fred.stlouisfed.org/series/'+key, unit, precision)
            if row.get('observedAt') is not None or row.get('frequency') != ('monthly' if key in MONTHLY else 'daily'):
                raise ValueError(f'{key}: invalid FRED observation metadata')
            if key in MONTHLY and observed_date.day != 1:
                raise ValueError(f'{key}: invalid observation month')
            if key in MONEY_SUPPLY:
                released = timestamp(row.get('sourceUpdatedAt'))
                if released.date() < observed_date or released > retrieved + timedelta(minutes=5) or row.get('seasonalAdjustment') != 'seasonally_adjusted':
                    raise ValueError(f'{key}: invalid FRED release metadata')
        actual = tuple(row.get(field) for field in ('sourceName','sourceUrl','unit','precision'))
        if actual != expected or type(row.get('precision')) is not int:
            raise ValueError(f'{key}: source identity or unit changed')
        if row['status'] == 'stale':
            if timestamp(row.get('lastAttemptAt')) < retrieved or not row.get('error'):
                raise ValueError(f'{key}: missing stale collection metadata')
    return payload

def parse_investing(html, key, now):
    spec = INVESTING[key]
    match = re.search(r'<script[^>]+id=[\"\']__NEXT_DATA__[\"\'][^>]*>(.*?)</script>', html, re.S)
    if not match: raise ValueError('Investing quote payload unavailable')
    state = json.loads(match.group(1))['props']['pageProps']['state']
    candidates = [v['instrument'] for v in state.values() if isinstance(v,dict) and isinstance(v.get('instrument'),dict) and str(v['instrument'].get('base',{}).get('id')) == spec['instrumentId']]
    if len(candidates) != 1: raise ValueError('Unexpected or ambiguous instrument')
    instrument = candidates[0]
    if instrument['base'].get('path','').strip('/') != spec['path']: raise ValueError('Instrument path changed')
    price = instrument['price']
    value = numeric(price['last'])
    observed = datetime.fromtimestamp(float(price['lastUpdateTime'])/1000, timezone.utc)
    if observed > now + timedelta(minutes=5) or observed.year < 2000: raise ValueError('Invalid/future source timestamp')
    if not isinstance(instrument['base'].get('isOpen'),bool): raise ValueError('Missing source market status')
    source = {'instrumentId':spec['instrumentId'], 'instrumentName':instrument.get('name',{}).get('fullName'), 'symbol':instrument.get('name',{}).get('symbol'), 'isCfd':instrument['base'].get('isCfd'), 'last':value, 'lastUpdateTime':price['lastUpdateTime'], 'isOpen':instrument['base']['isOpen'], 'isDelayed':price.get('isDelayed'), 'exchange':instrument.get('exchange',{}).get('exchange')}
    return {'id':key,'quoteLabel':spec['quoteLabel'],'unit':spec['unit'],'precision':spec['precision'],'value':value,'asOf':observed.date().isoformat(),'observedAt':iso(observed),'observationTimezone':'UTC','sourceTimeText':observed.strftime('%Y-%m-%d %H:%M:%S UTC'),'retrievedAt':iso(now),'sourceName':'Investing.com','sourceUrl':'https://www.investing.com/'+spec['path'],'status':'verified','marketStatus':'open' if source['isOpen'] else 'closed','isDelayed':price.get('isDelayed'), 'note':spec['note'],'sourceObservation':source}

def parse_fred(text, key, now):
    observations = []
    for row in csv.DictReader(io.StringIO(text)):
        stamp = row.get('observation_date') or row.get('DATE')
        if not stamp or row.get(key) in ('', '.', None): continue
        d = date.fromisoformat(stamp)
        if d > now.date(): raise ValueError('Future FRED observation')
        observations.append((d,numeric(row[key])))
    if not observations: raise ValueError('No dated FRED observations')
    d,value = max(observations)
    label,unit,precision = FRED[key]
    return {'id':key,'quoteLabel':label,'unit':unit,'precision':precision,'value':value,'asOf':d.isoformat(),'observedAt':None,'observationTimezone':None,'sourceTimeText':(d.strftime('%Y-%m')+' 월간 관측' if key in MONTHLY else d.isoformat()+' 관측 · 일중 시각 미제공'),'frequency':('monthly' if key in MONTHLY else 'daily'),'retrievedAt':iso(now),'sourceName':'FRED','sourceUrl':'https://fred.stlouisfed.org/series/'+key,'status':'verified','marketStatus':None,'note':'차트와 같은 FRED 시계열의 최근 공표 관측값. 조회일과 관측일은 다릅니다.'}

def add_fred_release_metadata(row, html, now):
    """Keep FRED's source update time distinct from observation month/retrieval."""
    match = re.search(r'"dateModified"\s*:\s*"([^"]+)"', html)
    if not match: raise ValueError('FRED source update time unavailable')
    source_time = datetime.fromisoformat(match.group(1).replace('Z','+00:00'))
    if source_time.tzinfo is None or source_time > now + timedelta(minutes=5):
        raise ValueError('Invalid FRED source update time')
    if source_time.date() < date.fromisoformat(row['asOf']):
        raise ValueError('FRED update precedes observation')
    row['sourceUpdatedAt'] = iso(source_time)
    row['seasonalAdjustment'] = 'seasonally_adjusted'
    row['note'] = '월별 계절조정 통화량. 관측월·FRED 갱신시각·조회시각은 서로 다르며 자료는 수정될 수 있습니다.'
    return row

def preserve_failure(previous, key, error, now):
    if previous and previous.get('value') is not None:
        result = deepcopy(previous)
        result['status'] = 'stale'
    else:
        if key in INVESTING:
            spec=INVESTING[key]; label,unit,precision=spec['quoteLabel'],spec['unit'],spec['precision'];sourceName='Investing.com';sourceUrl='https://www.investing.com/'+spec['path']
        else:
            label,unit,precision=FRED[key];sourceName='FRED';sourceUrl='https://fred.stlouisfed.org/series/'+key
        result={'id':key,'quoteLabel':label,'unit':unit,'precision':precision,'value':None,'asOf':None,'observedAt':None,'retrievedAt':None,'sourceName':sourceName,'sourceUrl':sourceUrl,'status':'unavailable'}
    result['lastAttemptAt']=iso(now)
    result['error']='원천 자료 재확인 실패: '+' '.join(str(error).split())[:180]
    return result

def collect(previous=None, fetcher=fetch_text, now=None):
    now=now or datetime.now(timezone.utc)
    if previous is not None:
        validate_snapshot(previous, now)
    old={r['id']:r for r in (previous or {}).get('rows',[])}
    def one(key):
        try:
            if key in INVESTING:
                row=parse_investing(fetcher('https://www.investing.com/'+INVESTING[key]['path']),key,now)
            else:
                start=(now.date()-timedelta(days=400)).isoformat()
                url=f'https://fred.stlouisfed.org/graph/fredgraph.csv?id={key}&cosd={start}&coed={now.date().isoformat()}'
                row=parse_fred(fetcher(url),key,now)
                if key in MONEY_SUPPLY:
                    row=add_fred_release_metadata(row,fetcher('https://fred.stlouisfed.org/series/'+key),now)
            prior=old.get(key)
            if prior and prior.get('asOf') and row['asOf'] < prior['asOf']: raise ValueError('Source observation regressed')
            if prior and prior.get('observedAt') and row.get('observedAt') and row['observedAt'] < prior['observedAt']: raise ValueError('Source timestamp regressed')
            return row
        except SourceUnavailable as error:
            if key not in old:
                raise SourceUnavailable(f'{key}: no prior verified observation; {error}') from error
            return preserve_failure(old[key],key,error,now)
        except Exception as error:
            # Add the series identity, but never downgrade invalid data to stale success.
            raise ValueError(f'{key}: source validation failed ({type(error).__name__}): {error}') from error
    with ThreadPoolExecutor(max_workers=4) as pool:
        rows=list(pool.map(one,[*INVESTING,*FRED]))
    good = sum(row['status'] == 'verified' for row in rows)
    payload = {'schemaVersion':1,'updatedAt':iso(now),'collectionStatus':('complete' if good == len(rows) else 'partial' if good else 'source_unavailable'),'verifiedCount':good,'staleCount':len(rows)-good,'note':'서버 수집 스냅샷이며 실시간 스트리밍이 아닙니다. 각 값의 관측시각과 원천을 확인하세요. 선물·CFD와 현물, DXY와 연준 광의 달러지수는 서로 다른 지표입니다.','rows':rows}
    return validate_snapshot(payload, now)

def main(argv=None):
    parser=argparse.ArgumentParser();parser.add_argument('--output',default=str(ROOT/'data/macro_quotes.json'));args=parser.parse_args(argv)
    path=Path(args.output)
    previous=json.loads(path.read_text()) if path.exists() else None
    payload=collect(previous)
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n');temp.replace(path)
    good=sum(r['status']=='verified' for r in payload['rows'])
    print(f'Macro collection status: {payload["collectionStatus"]}; verified: {good}/{len(payload["rows"])}; retained: {payload["staleCount"]}')
    for row in payload['rows']:
        if row['status'] == 'stale':
            print(f'MACRO_SOURCE_UNAVAILABLE {row["id"]}: {row["error"]}; retained asOf={row["asOf"]}')
    if good < len(payload['rows']):
        print('WARNING: macro refresh incomplete; validated prior source dates retained. Independent panels still require publication validation.')
    return 0

if __name__=='__main__': raise SystemExit(main())
