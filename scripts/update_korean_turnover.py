"""Refresh official published ECOS market turnover; preserves other market fields.
No key/account is created. Public sample endpoint supports at most ten rows/page.
"""
import argparse, copy, json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.request import urlopen
from decimal import Decimal
from korean_turnover import validate
ROOT=Path(__file__).resolve().parents[1]
CODES={'KOSPI':'0088000','KOSDAQ':'0091000'}
def collect(market,start,end):
    rows=[];offset=1
    while True:
        url=f'https://ecos.bok.or.kr/api/StatisticSearch/sample/json/kr/{offset}/{offset+9}/802Y001/D/{start.replace("-","")}/{end.replace("-","")}/{CODES[market]}'
        with urlopen(url,timeout=30) as response:obj=json.load(response)
        observed=datetime.now(timezone.utc).isoformat()
        if obj.get('RESULT',{}).get('CODE')=='INFO-200':break
        result=obj['StatisticSearch'];source_rows=result['row']
        for r in source_rows:
            assert r['UNIT_NAME']=='억원' and r['STAT_CODE']=='802Y001' and r['ITEM_CODE1']==CODES[market], 'Unexpected ECOS unit/series'
            d=datetime.strptime(r['TIME'],'%Y%m%d').date().isoformat();assert start<=d<=end
            value=Decimal(r['DATA_VALUE']);assert value.is_finite() and value>=0
            rows.append({'date':d,'turnover':float(value),'sourceValue':r['DATA_VALUE'],'sourceUnit':'억원','conversionToEokKRW':1,'observedAt':observed,'source':url})
        offset+=10
        if offset>int(result['list_total_count']):break
    assert len({r['date'] for r in rows})==len(rows),'Duplicate ECOS dates'
    return rows

def update(payload,end):
    result=copy.deepcopy(payload); section=result['marketTurnover']
    for market,series in section['markets'].items():
        old={r['date']:r for r in series['rows']};start=(date.fromisoformat(max(old))-timedelta(days=30)).isoformat()
        for row in collect(market,start,end):
            prior=old.get(row['date'])
            if prior and prior.get('sourceValue')==row['sourceValue']:continue
            old[row['date']]=row
        # Known completed-session dates come from existing verified flow history.
        # Interior missing source observations remain explicit gaps, not interpolation.
        for known in result.get('flows',{}).get('markets',{}).get(market,{}).get('rows',[]):
            d=known.get('date')
            if d and min(old)<=d<=max(old) and d not in old:
                old[d]={'date':d,'turnover':None,'missingReason':'확인된 거래일이지만 ECOS 원천 관측 미확인','observedAt':datetime.now(timezone.utc).isoformat()}
        series['rows']=[r for _,r in sorted(old.items())]
        rows=series['rows'];series['asOf']=rows[-1]['date'];series['coverage']={'start':rows[0]['date'],'end':rows[-1]['date'],'count':len(rows)}
        series['note']=f"한국은행 ECOS 주식시장(일) 시장 전체 거래대금. 원단위 억원. 실제 공표 기준일 {rows[-1]['date']}. 조회 목표 {end}; 정규장 한정·시간외 및 NXT 포함 여부는 미확인. 다른 제공자 당일 수치와 혼합하지 않음. 실제 관측시각은 각 행 observedAt에 보존."
    errors=validate(section,result['sources']);assert not errors,errors
    # Do not republish unchanged observations merely for a new checked-at timestamp.
    if all(result['marketTurnover']['markets'][m]['rows']==payload['marketTurnover']['markets'][m]['rows'] for m in CODES):return payload
    section['collectedAt']=datetime.now(timezone.utc).isoformat();return result

def main():
    p=argparse.ArgumentParser();p.add_argument('--as-of',required=True,help='Verified latest completed KRX session YYYY-MM-DD');p.add_argument('--path',default=str(ROOT/'data/korea-market.json'));p.add_argument('--check',action='store_true');a=p.parse_args();date.fromisoformat(a.as_of)
    path=Path(a.path);old=json.loads(path.read_text())
    if a.check:
        errors=validate(old.get('marketTurnover'),old['sources']);assert not errors,errors;print('Market turnover valid');return
    new=update(old,a.as_of)
    if new==old:print('No newly published turnover; unchanged.');return
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(new,ensure_ascii=False,indent=2)+'\n');temp.replace(path);print('New published market turnover merged; other fields preserved.')
if __name__=='__main__':main()
