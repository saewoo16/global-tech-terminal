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
        if seen:
            c=s.get('coverage',{})
            if (c.get('start'),c.get('end'),c.get('count'))!=(seen[0],seen[-1],len(seen)):errors.append(f'{market} turnover coverage mismatch')
    return errors
