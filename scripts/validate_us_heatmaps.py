#!/usr/bin/env python3
"""Fail closed on stale/cross-date prices, fake caps, counts, or source drift."""
import hashlib,json,math
from pathlib import Path
from datetime import datetime

ROOT=Path(__file__).resolve().parents[1]

def validate_entry(e,root=ROOT):
    date=e['date']; rows=e['rows']; c=e['coverage']
    assert e['session']==date
    datetime.strptime(date,'%Y-%m-%d')
    if e['previousSession'] is not None: assert e['previousSession']<date
    assert e['regularSessionOnly'] is True
    assert e['weighting']['basis']=='equal-security' and e['weighting']['asOf'] is None
    if e['status']=='unavailable':
        assert not rows and c['verified']==0 and c['missingCount']==c['expected'] and c['missingReason']
        return
    assert e['status']=='verified'
    source=root/e['evidenceFile']; raw=source.read_bytes(); evidence=json.loads(raw)
    assert hashlib.sha256(raw).hexdigest()==e['evidenceSha256']
    assert evidence['session']==date
    assert evidence['sessionVerification']['previousSession']==e['previousSession']
    assert datetime.fromisoformat(e['observedAt'].replace('Z','+00:00'))>=datetime.fromisoformat(e['closedAt'])
    assert e['observedAt']==evidence['screens']['coverage']['retrievedAt']
    assert e['constituentDate']==evidence['screens']['coverage']['universeAsOf']
    source_rows={r['ticker']:r for r in evidence['screens']['dailyRows']}
    tickers=[r['ticker'] for r in rows]
    assert len(tickers)==len(set(tickers))==len(source_rows)==c['verified']==c['expected']==evidence['screens']['coverage']['selected']==evidence['screens']['coverage']['securities']
    assert set(tickers)==set(source_rows)
    assert len({r['cik'] for r in rows})==c['companies']==evidence['screens']['coverage']['companies']
    assert c['missingCount']==0 and c['missing']==[]
    for r in rows:
        assert r['asOf']==date and r['previousSession']==e['previousSession']
        for field in ['close','previousClose']:
            assert isinstance(r[field],(int,float)) and not isinstance(r[field],bool) and math.isfinite(r[field]) and r[field]>0
        assert math.isfinite(r['changePct']) and math.isclose(r['changePct'],100*(r['close']/r['previousClose']-1),abs_tol=1e-10)
        assert r['weight']==1 and r['marketCapUSD'] is None
        for field in ['close','previousClose','changePct','sector','sectorEnglish','cik','asOf','previousSession','sourceUrl','chartSource','priceBasis']:
            assert r[field]==source_rows[r['ticker']][field],(date,r['ticker'],field)
        assert r['sector'] and r['sectorEnglish'] and r['sourceUrl'].startswith('https://')

def validate(data,root=ROOT):
    assert data['schemaVersion']==1
    entries=data['entries']; dates=[e['date'] for e in entries]
    assert len(dates)==len(set(dates))
    requested={e['date'] for e in json.loads((root/'data/us_analysis.json').read_text())['entries']}
    assert requested.issubset(dates)
    for e in entries: validate_entry(e,root)
    verified=[e['date'] for e in entries if e['status']=='verified']
    assert data['defaultDate']==(max(verified) if verified else None)
    return {'verifiedDates':verified,'verifiedRows':sum(len(e['rows']) for e in entries),'weighting':'equal-security'}

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=ROOT);p.add_argument('--data',type=Path);a=p.parse_args()
    print(json.dumps(validate(json.loads((a.data or a.root/'data/us_heatmaps.json').read_text()),a.root)))
