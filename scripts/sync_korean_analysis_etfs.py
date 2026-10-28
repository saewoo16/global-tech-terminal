#!/usr/bin/env python3
"""Reuse the published domestic ETF chart snapshot; never fetch or mutate that source."""
import argparse, calendar, copy, datetime as dt, hashlib, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
def sync(payload, charts):
    out=copy.deepcopy(payload); section=out['sectorReturns']; rows=section['rows']; sources={s['id']:s for s in out['sources']}
    existing={r.get('ticker','').split('.')[0]:r for r in rows if r.get('instrumentType')=='etf'}
    names={r['name'] for r in rows}
    for source_fund in charts['funds']:
        fund=copy.deepcopy(source_fund)
        fund['daily']=[point for point in fund['daily'] if point['date'] <= section['asOf']]
        if not fund['daily']: raise ValueError('No chart observation at or before analysis session: '+fund['code'])
        code=fund['code']; rep=fund.get('representatives',{}); holdings=rep.get('holdings',[])
        if rep.get('status')!='verified' or len(holdings)<5: raise ValueError('Unverified holdings: '+code)
        hs='kr-chart-holdings-'+code
        sources[hs]={'id':hs,'title':fund['name']+' 실제 편입비중','url':rep['sourceUrls'][0],'note':'기존 ETF 차트 검증 자료 재사용. 구성 기준일 '+rep['universeAsOf']+'; 실제 확인 '+rep['asOf']}
        holding={'status':'verified','asOf':rep['universeAsOf'],'sourceIds':[hs],'top5':[{'name':h['name'],'ticker':h.get('code') or 'ISIN:'+h['isin'],'code':h.get('code'),'isin':h.get('isin'),'identifierType':'ticker' if h.get('code') else 'isin','weightPct':h['weightPct']} for h in holdings[:5]],'retrievedAt':rep['asOf'],'methodology':rep['methodology']}
        if code in existing and existing[code].get('asOf', section['asOf']) >= fund['daily'][-1]['date']:
            row=existing[code]
            if row.get('holdings', {}).get('asOf', '') <= holding['asOf']: row['holdings']=holding
            row['chartUniverseMember']=True
            continue
        prior=existing.get(code)
        if fund['daily'][-1]['date'] > section['asOf']: raise ValueError('Chart is newer than analysis session: '+code)
        daily=fund['daily']; end=daily[-1]; date=dt.date.fromisoformat(end['date']); month=date.month-1 or 12;year=date.year-(date.month==1)
        targets={'day':(date-dt.timedelta(days=1)).isoformat(),'week':(date-dt.timedelta(days=7)).isoformat(),'month':dt.date(year,month,min(date.day,calendar.monthrange(year,month)[1])).isoformat()}
        bases={'day':daily[-2] if len(daily)>1 else None,**{k:next((x for x in reversed(daily) if x['date']<=v),None) for k,v in targets.items() if k != 'day'}}
        source='kr-chart-price-'+code;sha=hashlib.sha256(json.dumps(daily,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
        sources[source]={'id':source,'title':fund['name']+' 기존 검증 일봉','url':fund['dailySourceUrl'],'note':'별도 ETF 수집 결과 재사용; 스냅샷 수집 '+charts['updatedAt']+'; 실제 종가 '+end['date']}
        name=prior['name'] if prior else fund['category'];name=name if prior or name not in names else name+' · '+fund['name'];names.add(name)
        component={'ticker':code+'.KS','providerName':fund['name'],'currency':'KRW','exchangeTimezone':'Asia/Seoul','priceField':'close','priceBasis':fund['dailyAdjustment'],'sourceId':source,'observations':{x['date']:copy.deepcopy(x) for x in [end,*bases.values()] if x},'collectionMethod':'reused_verified_etf_chart','retrievedAt':charts['updatedAt'],'sourceSnapshotSha256':sha}
        row={'id':'chart-etf-'+code,'name':name,'ticker':code+'.KS','benchmark':fund['name'],'group':'세부업종 ETF' if fund['group']=='industry' else '세부테마 ETF','instrumentType':'etf','holdings':holding,'sourceIds':[source,hs],'asOf':end['date'],'currency':'KRW','proxyTypeLabel':'ETF 대용지표','chartUniverseMember':True,'scopeNote':fund.get('selectionNote','')+' ETF 투자범위의 대용지표이며 업종 전수지수가 아닙니다.','methodology':'기존 국내 ETF 차트와 동일: 1일은 직전 관측 종가, 1주는 7일 전, 1개월은 달력상 1개월 전까지의 가장 최근 종가 대비 가격수익률. 분배금 재투자 제외. 편입비중 상위3종목을 표시하되 수익률은 ETF 가격 기준입니다.','calculation':{'formula':'100 * (close[end] / close[base] - 1)','weighting':'ETF market price, not equal-weight holdings','currency':'KRW','end':end['date'],'bases':{k:v['date'] if v else None for k,v in bases.items()},'targetDates':targets,'availableHistoryStart':daily[0]['date'],'constituentData':[component]},'periodStatus':{},'refreshStatus':'updated' if end['date']==section['asOf'] else 'retained_previous','refreshNote':'별도 ETF 차트의 실제 검증 스냅샷 '+end['date']+' 재사용. 새 시세가 확인되기 전 날짜를 변경하지 않습니다.'}
        for period,base in bases.items():
            row[period]=(end['close']/base['close']-1)*100 if base else None
            row['periodStatus'][period]='verified' if base else 'insufficient_history'
        if prior:
            for field in ('id','group'): row[field]=prior.get(field,row[field])
            if prior.get('holdings',{}).get('asOf','') > holding['asOf']: row['holdings']=prior['holdings']
            rows[rows.index(prior)]=row
        else: rows.append(row)
    section['chartUniverseCoverage']={'count':len(charts['funds']),'codes':[f['code'] for f in charts['funds']],'snapshotUpdatedAt':charts['updatedAt'],'snapshotAsOf':charts['asOf'],'method':'reuse_published_chart_snapshot_no_collection'}
    section['chartUniverseNote']='국내 업종별/테마별 차트 전체 ETF를 포함합니다. 각 행의 실제 가격 기준일을 확인하세요. 신규 상장으로 비교기간 이력이 부족한 값은 미확인으로 남기며 과거 가격을 만들지 않습니다.'
    out['sources']=list(sources.values());return out
def sync_briefings(archive, market):
    result=copy.deepcopy(archive)
    latest=max((e for e in result['entries'] if e['market']=='KR'),key=lambda e:e['date'],default=None)
    if latest is None or latest['date'] != market['sectorReturns']['asOf']: return result
    section=market['sectorReturns']
    latest['sectors']=copy.deepcopy({k:section[k] for k in ('rows','asOf','title','note')})
    for row in latest['sectors']['rows']:
        row.pop('calculation',None)
        row.pop('periodStatus',None)
        if row.get('instrumentType')!='etf': row.pop('holdings',None)
    sources={s['id']:s for s in latest['sources']}
    needed={sid for r in latest['sectors']['rows'] for sid in r.get('sourceIds',[])+r.get('holdings',{}).get('sourceIds',[])}
    for source in market['sources']:
        if source['id'] in needed: sources[source['id']]=source
    latest['sources']=list(sources.values())
    return result
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--market',type=Path,default=ROOT/'data/korea-market.json');p.add_argument('--charts',type=Path,default=ROOT/'data/korean_etf_charts.json');p.add_argument('--briefings',type=Path,default=None);a=p.parse_args()
    result=sync(json.loads(a.market.read_text()),json.loads(a.charts.read_text()));a.market.write_text(json.dumps(result,ensure_ascii=False,separators=(',',':'))+'\n')
    briefings=a.briefings or a.market.parent/'briefings.json'
    if briefings.exists():
        archive=sync_briefings(json.loads(briefings.read_text()),result);briefings.write_text(json.dumps(archive,ensure_ascii=False,separators=(',',':'))+'\n')
    print('ETF chart universe:',result['sectorReturns']['chartUniverseCoverage']['count'],'total rows:',len(result['sectorReturns']['rows']))
