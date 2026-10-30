"""Validate market-wide turnover observations, never stock-rank sums/volume."""
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import math

def validate(section, sources):
    errors=[]
    if not isinstance(section,dict): return ['marketTurnover must be an object']
    ids={s.get('id') for s in sources}
    for market in ('KOSPI','KOSDAQ'):
        s=section.get('markets',{}).get(market,{})
        if s.get('unit')!='억원': errors.append(f'{market} turnover unit must be 억원')
        if s.get('scope')!='whole-market': errors.append(f'{market} turnover must be whole-market')
        if not s.get('sourceIds') or not set(s['sourceIds'])<=ids:errors.append(f'{market} turnover sources missing')
        seen=[]
        for r in s.get('rows',[]):
            d=r.get('date')
            try:date.fromisoformat(d)
            except (ValueError,TypeError):errors.append(f'{market} invalid turnover date')
            seen.append(d)
            v=r.get('turnover')
            if v is not None:
                if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or v<0:errors.append(f'{market} invalid turnover amount')
                try:
                    if Decimal(str(v))!=Decimal(str(r['sourceValue']))*Decimal(str(r['conversionToEokKRW'])):errors.append(f'{market} turnover conversion mismatch {d}')
                except (KeyError,ValueError,InvalidOperation): errors.append(f'{market} missing source precision {d}')
                if r.get('sourceUnit') not in ('억원','백만원','원'):errors.append(f'{market} missing source unit')
            elif not r.get('missingReason'):errors.append(f'{market} unknown turnover requires missingReason')
            try:
                t=datetime.fromisoformat(r.get('observedAt','').replace('Z','+00:00'))
                if t.tzinfo is None:raise ValueError()
            except (ValueError,TypeError):errors.append(f'{market} turnover observedAt needs offset')
        if seen!=sorted(set(seen)):errors.append(f'{market} turnover dates must be unique and sorted')
        comparison=s.get('comparisonSeries')
        if comparison is not None:
            errors.extend(validate_comparison(comparison, sources, market))
        if seen:
            c=s.get('coverage',{})
            if (c.get('start'),c.get('end'),c.get('count'))!=(seen[0],seen[-1],len(seen)):errors.append(f'{market} turnover coverage mismatch')
    for market in ('KOSPI','KOSDAQ'):
        observation=section.get('markets',{}).get(market,{}).get('currentObservation')
        if observation:
            if observation.get('marketVenue')!='KRX' or observation.get('session')!='regular-close':errors.append('current turnover needs KRX regular-close scope')
            errors.extend(validate_observation(observation, sources))
    nxt=section.get('nxtObservation')
    if nxt:
        if nxt.get('marketVenue')!='NXT' or nxt.get('session')!='premarket-and-regular':errors.append('NXT scope must remain separate premarket-and-regular')
        errors.extend(validate_observation(nxt,sources))
    return errors

def validate_observation(row,sources):
    series={'unit':'억원','scope':'whole-market','sourceIds':row.get('sourceIds',[]),'rows':[row],'coverage':{'start':row.get('date'),'end':row.get('date'),'count':1}}
    return validate({'markets':{'KOSPI':series,'KOSDAQ':series}},sources)


def validate_comparison(comparison, sources, market):
    """Independent same-market venue/session series; never sum an integrated feed."""
    errors=[]
    if not isinstance(comparison,dict) or set(comparison)!={'regular','integrated'}:
        return [f'{market} comparison requires regular and integrated series']
    for key,series in comparison.items():
        if not isinstance(series,dict):
            errors.append(f'{market} {key} series must be object');continue
        if series.get('scope')!='whole-market' or series.get('market')!=market:
            errors.append(f'{market} {key} must identify whole same market')
        if series.get('unit')!='억원': errors.append(f'{market} {key} unit must be 억원')
        expected=['KRX'] if key=='regular' else ['KRX','NXT']
        if series.get('venues')!=expected: errors.append(f'{market} {key} incorrect venues')
        if key=='regular' and series.get('sessionScope')!='regular': errors.append(f'{market} regular requires regular session')
        if key=='integrated' and series.get('sessionScope') not in ('all-sessions','regular-plus-nxt-all-sessions'):
            errors.append(f'{market} integrated requires explicit session scope')
        if not series.get('label') or not series.get('scopeNote'): errors.append(f'{market} {key} missing visible scope')
        if series.get('status') not in ('verified','partial','unavailable'): errors.append(f'{market} {key} invalid coverage status')
        rows=series.get('rows',[])
        if not isinstance(rows,list): errors.append(f'{market} {key} rows must be array');continue
        # Reuse precision/date/source checks on a nonrecursive standalone series.
        base={k:series[k] for k in ('unit','scope','sourceIds','rows','coverage') if k in series}
        if rows or series.get('status')!='unavailable':
            errors.extend(validate({'markets':{'KOSPI':base,'KOSDAQ':base}},sources))
        valid=[r for r in rows if r.get('turnover') is not None]
        if series.get('asOf')!=(valid[-1]['date'] if valid else None): errors.append(f'{market} {key} asOf differs from actual last value')
        for row in rows:
            if row.get('turnover') is None: continue
            if row.get('valueStatus') not in ('final','provisional'): errors.append(f'{market} {key} missing final/provisional status')
            if row.get('scopeVerified') is not True: errors.append(f'{market} {key} scope must be verified')
            if not row.get('sourceIds') or not set(row['sourceIds'])<={s.get('id') for s in sources}:
                errors.append(f'{market} {key} observation sources missing')
        if not valid and series.get('status')!='unavailable': errors.append(f'{market} {key} empty series must be unavailable')
    return errors
