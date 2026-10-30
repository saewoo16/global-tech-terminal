"""Merge independently verified market/session turnover; never derive totals from mixed feeds.
The input is an evidence-backed JSON bundle, not an unverified network response.
It contains source definitions and one or both series for each supplied market.
Use --mode regular for 18:00 KST, --mode integrated for 20:30 KST.
"""
import argparse,copy,json
from pathlib import Path
from datetime import date,datetime,timezone
from korean_turnover import validate
ROOT=Path(__file__).resolve().parents[1]
LABELS={'regular':'KRX 정규장','integrated':'KRX + NXT 전체 거래'}
def empty_series(market,key):
 return {'market':market,'unit':'억원','scope':'whole-market','venues':['KRX'] if key=='regular' else ['KRX','NXT'],'sessionScope':'regular' if key=='regular' else 'all-sessions','label':LABELS[key],'scopeNote':'같은 범위의 검증된 시장 전체 원자료를 확인한 날짜만 표시합니다.','status':'unavailable','asOf':None,'sourceIds':[],'rows':[],'coverage':{'count':0}}
def merge(payload,bundle,mode,as_of):
 date.fromisoformat(as_of)
 if mode not in LABELS: raise ValueError('Unknown mode')
 result=copy.deepcopy(payload)
 sources={s['id']:s for s in result['sources']}
 for source in bundle.get('sources',[]):
  if not source.get('id') or not source.get('url','').startswith('https://'):raise ValueError('Evidence source id and HTTPS URL required')
  if source['id'] in sources and sources[source['id']]!=source:raise ValueError('Existing source definitions must not be overwritten')
  sources[source['id']]=source
 result['sources']=list(sources.values())
 for market,incoming in bundle.get('markets',{}).items():
  if market not in ('KOSPI','KOSDAQ'):raise ValueError('Unknown market')
  target=result['marketTurnover']['markets'][market]
  comparison=target.setdefault('comparisonSeries',{key:empty_series(market,key) for key in LABELS})
  series=incoming.get(mode)
  if series is None:continue
  if set(incoming)!={mode}:raise ValueError('Bundle may only update requested mode')
  if not series.get('scopeNote') or not series.get('sessionScope'):raise ValueError('Verified session coverage required')
  old=comparison[mode]
  if old['rows'] and any(old.get(k)!=series.get(k) for k in ('sessionScope','venues','unit','market','scope')):
   raise ValueError('Do not mix changed session coverage with prior history')
  rows={r['date']:r for r in old['rows']}
  for row in series.get('rows',[]):
   if row['date']>as_of:raise ValueError('Future/uncompleted trading date not allowed')
   # Do not overwrite a final amount with an intraday or unavailable amount.
   prior=rows.get(row['date'])
   if prior and prior.get('valueStatus')=='final' and row.get('valueStatus')!='final':continue
   if prior and all(prior.get(k)==row.get(k) for k in ('turnover','sourceValue','sourceUnit','conversionToEokKRW','valueStatus','sourceIds','scopeVerified')):continue
   rows[row['date']]=row
  merged=copy.deepcopy(series);merged['rows']=[v for _,v in sorted(rows.items())]
  merged['sourceIds']=list(dict.fromkeys(old['sourceIds']+series.get('sourceIds',[])))
  valid=[r for r in merged['rows'] if r.get('turnover') is not None]
  merged['asOf']=valid[-1]['date'] if valid else None
  merged['coverage']={'start':merged['rows'][0]['date'],'end':merged['rows'][-1]['date'],'count':len(merged['rows'])} if merged['rows'] else {'count':0}
  comparison[mode]=merged
 errors=validate(result['marketTurnover'],result['sources'])
 if errors:raise ValueError('; '.join(errors))
 if result==payload:return payload
 result['marketTurnover']['comparisonUpdatedAt']=datetime.now(timezone.utc).isoformat()
 return result

def main():
 p=argparse.ArgumentParser();p.add_argument('--entry',required=True);p.add_argument('--mode',choices=LABELS,required=True);p.add_argument('--as-of',required=True);p.add_argument('--path',default=str(ROOT/'data/korea-market.json'));a=p.parse_args()
 path=Path(a.path);old=json.loads(path.read_text());bundle=json.loads(Path(a.entry).read_text());new=merge(old,bundle,a.mode,a.as_of)
 if new is old:print('No new verified comparison turnover; unchanged.');return
 temp=path.with_suffix('.tmp');temp.write_text(json.dumps(new,ensure_ascii=False,separators=(',',':'))+'\n');temp.replace(path);print('Verified turnover comparison merged.')
if __name__=='__main__':main()
