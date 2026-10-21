#!/usr/bin/env python3
"""Build immutable daily heatmap snapshots from retained regular-close evidence."""
import argparse, hashlib, json, math
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

def unavailable(entry, reason):
    date=entry['date']
    return {'date':date,'session':date,'previousSession':entry.get('sessionVerification',{}).get('previousSession'),'status':'unavailable','constituentDate':None,'observedAt':None,'regularSessionOnly':True,'coverage':{'expected':None,'verified':0,'missing':[],'missingCount':None,'missingReason':reason},'weighting':{'basis':'equal-security','asOf':None,'note':'증권별 동일 면적 · 시총 가중 아님'},'sources':[],'rows':[]}

def build_entry(root,date,raw_roots=None):
    source_path=root/'data'/f"us-close-evidence-{date.replace('-','')}.json"
    e=json.loads(source_path.read_text()); s=e['screens']; c=s['coverage']; prev=e['sessionVerification']['previousSession']
    assert e['session']==date and e['sessionVerification']['exchangeDate']==date
    assert c['asOf']==date and c['previousSession']==prev
    assert c['dailyValid']==c['selected']==c['securities']==len(s['dailyRows'])
    assert c['missingCount']==0 and not c['missing']
    assert len({r['ticker'] for r in s['dailyRows']})==len(s['dailyRows'])
    assert len({r['cik'] for r in s['dailyRows']})==c['companies']
    assert datetime.fromisoformat(c['retrievedAt'].replace('Z','+00:00')) >= datetime.fromisoformat(e['sessionVerification']['closedAt'])
    rows=[]
    for r in s['dailyRows']:
        assert all(isinstance(r[k],(int,float)) and not isinstance(r[k],bool) and math.isfinite(r[k]) and r[k]>0 for k in ['close','previousClose'])
        assert math.isfinite(r['changePct'])
        assert r['asOf']==date and r['previousSession']==prev
        assert math.isclose(r['changePct'],100*(r['close']/r['previousClose']-1),abs_tol=1e-10)
        row={k:r[k] for k in ['ticker','name','cik','sector','sectorEnglish','industry','close','previousClose','changePct','asOf','previousSession','sourceUrl','chartSource','priceBasis']}
        row.update(marketCapUSD=None,weight=1,currency='USD')
        if raw_roots and date in raw_roots:
            rawfile=raw_roots[date]/(r['ticker'].replace('.','-')+'.json')
            if not rawfile.exists(): rawfile=raw_roots[date]/(r['ticker']+'.json')
            raw=rawfile.read_bytes(); chart=json.loads(raw)['chart']['result'][0]
            bars={datetime.fromtimestamp(t,ZoneInfo('America/New_York')).date().isoformat():v for t,v in zip(chart['timestamp'],chart['indicators']['quote'][0]['close'])}
            assert bars[date]==r['close'],(date,r['ticker'],'close')
            assert bars[prev]==r['previousClose'],(date,r['ticker'],'previousClose')
            row['rawSha256']=hashlib.sha256(raw).hexdigest()
        rows.append(row)
    return {'date':date,'session':date,'previousSession':prev,'status':'verified','constituentDate':c['universeAsOf'],'observedAt':c['retrievedAt'],'closedAt':e['sessionVerification']['closedAt'],'regularSessionOnly':True,'coverage':{'expected':c['selected'],'verified':len(rows),'missing':[],'missingCount':0,'companies':c['companies'],'securities':c['securities']},'weighting':{'basis':'equal-security','asOf':None,'note':'증권별 동일 면적 · 섹터 면적은 증권 수 비례 · 시총 가중 아님','reason':'해당 거래일의 전체 증권별 시총 가중치가 검증되지 않아 동일 면적을 사용합니다. 미확인 시총 추정·복수 주식종류 중복 합산을 하지 않습니다.'},'scope':f"S&P500 {c['companies']}개 기업·{c['securities']}개 주식종류. 미국 시총 상위500개 목록과 다릅니다.",'priceBasis':'정규장 일봉 quote.close, 배당조정 adjclose·프리마켓·애프터마켓 제외. 기업행위 조정은 공급사 기준.','sources':[{'title':'Yahoo Finance historical daily closes','url':'https://finance.yahoo.com/'},{'title':'S&P500 membership','url':'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'},{'title':'FINVIZ 실시간 참고 (선택 거래일 고정 종가 지도가 아님)','url':'https://finviz.com/map.ashx?t=sec'}],'evidenceFile':f'data/{source_path.name}','evidenceSha256':hashlib.sha256(source_path.read_bytes()).hexdigest(),'limitations':['가격은 단일 공급사 일봉에 의존하며 모든 기업행위를 독립 감사하지 않았습니다.','구성종목 관측일과 가격 거래일을 별도로 표시합니다.','면적은 증권별 동일하며 시가총액이나 공식 S&P500 지수 가중치를 나타내지 않습니다.'],'rows':rows}

def build(root, raw_roots=None, existing=None):
    from validate_us_heatmaps import validate_entry
    analysis=json.loads((root/'data/us_analysis.json').read_text())
    requested={e['date']:e for e in analysis['entries']}
    prior={e['date']:e for e in (existing or {}).get('entries',[])}
    entries=[]
    for date in sorted(set(requested)|set(prior)):
        # Preserve a verified archived date exactly; source drift fails rather than rewrites history.
        if date in prior and prior[date]['status']=='verified':
            validate_entry(prior[date],root)
            entries.append(prior[date]);continue
        try:
            entry=build_entry(root,date,raw_roots)
            validate_entry(entry,root)
        except (OSError,ValueError,KeyError,TypeError,AssertionError) as error:
            entry=unavailable(requested.get(date,{'date':date}), '해당 거래일의 독립 검증 dailyRows 미확보 또는 검증 실패. 다른 날짜 지도를 복사하지 않습니다.')
            entry['validationFailureType']=type(error).__name__
        entries.append(entry)
    verified=[e['date'] for e in entries if e['status']=='verified']
    return {'schemaVersion':1,'market':'US','universe':'S&P 500','defaultDate':max(verified) if verified else None,'colorDefinition':'100 * (regular close / previous regular close - 1)','entries':entries}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source-root',type=Path,default=Path(__file__).resolve().parents[1]);p.add_argument('--output',type=Path);p.add_argument('--raw-root',action='append',default=[],metavar='YYYY-MM-DD=PATH');a=p.parse_args()
    raw={date:Path(path) for date,path in (item.split('=',1) for item in a.raw_root)}
    out=a.output or a.source_root/'data/us_heatmaps.json'
    existing=json.loads(out.read_text()) if out.exists() else None
    result=build(a.source_root,raw,existing);out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'output':str(out),'dates':[{k:e[k] for k in ['date','status','coverage']} for e in result['entries']]},ensure_ascii=False))
