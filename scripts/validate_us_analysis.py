"""Validate source-backed completed US daily analysis before publication."""
import datetime as dt
import json
import math
from pathlib import Path
from urllib.parse import urlparse
ROOT = Path(__file__).resolve().parents[1]


def validate(payload):
    assert payload.get('schemaVersion') == 1
    entries = payload.get('entries')
    assert isinstance(entries, list) and entries
    dates = set()
    for e in entries:
        date = dt.date.fromisoformat(e['date'])
        assert date.weekday() < 5, 'Weekend must never become a trading session'
        assert e['date'] not in dates, 'Duplicate daily entry'
        dates.add(e['date'])
        assert e.get('sessionStatus') == 'closed'
        assert e.get('universe') == 'S&P 500'
        assert len(e.get('indices', [])) == 4
        ids = {s['id'] for s in e['sources']}
        assert len(ids) == len(e['sources']), 'Duplicate source IDs'
        for source in e['sources']:
            u = urlparse(source['url'])
            assert u.scheme in ('https', 'http') and u.netloc and not u.username and not u.password
        def walk(value):
            if isinstance(value, dict):
                if 'sourceIds' in value:
                    assert set(value['sourceIds']) <= ids, f"Unknown source: {value['sourceIds']}"
                for v in value.values(): walk(v)
            elif isinstance(value, list):
                for v in value: walk(v)
            elif isinstance(value, float): assert math.isfinite(value)
        walk(e)
        for row in e['sectors']['rows']:
            for k in ('day','week','month'):
                assert row.get(k) is None or isinstance(row[k], (int,float))
            if row.get('instrumentType') == 'etf' and row.get('holdings',{}).get('status') == 'verified':
                h=row['holdings']; assert len(h.get('top3',h.get('top5',[]))) >= 3
                dt.date.fromisoformat(h['asOf']); assert h['sourceIds']
        member_symbols={r['ticker'] for r in e.get('constituents',[])}
        if member_symbols:
            assert len(member_symbols)>=500
        highs=e.get('highs',{}).get('rows',[])
        assert len({r['ticker'] for r in highs}) == len(highs)
        for r in highs:
            assert not member_symbols or r['ticker'] in member_symbols
            assert r['classification'] in ('new_high','near_high')
            assert r.get('sector') and r.get('business')
            if r['classification']=='new_high':
                assert r['dayHigh'] > r['priorHigh52'], 'True new high must strictly exceed previous high'
            else:
                assert -3.0001 <= r['distancePct'] <= 0.0001
        for side,reverse in [('gainers',True),('losers',False)]:
            rows=e.get('movers',{}).get(side,[])
            assert len(rows)<=10
            assert len({r['ticker'] for r in rows})==len(rows)
            assert [r['changePct'] for r in rows]==sorted((r['changePct'] for r in rows),reverse=reverse)
            for r in rows:
                assert not member_symbols or r['ticker'] in member_symbols
                assert isinstance(r.get('reasonVerified'),bool)
                if r['reasonVerified']: assert r.get('reason') and r.get('sourceIds')
        for r in e.get('earnings',{}).get('rows',[]):
            assert not member_symbols or r['ticker'] in member_symbols
            assert r.get('sourceIds') and r.get('releaseDate')
            dt.date.fromisoformat(r['releaseDate'])
            assert len(r.get('metrics',[]))>=8
    return len(entries)


if __name__ == '__main__':
    import sys
    p=Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'data/us_analysis.json'
    print(f'Validated {validate(json.loads(p.read_text()))} completed US daily entries.')
