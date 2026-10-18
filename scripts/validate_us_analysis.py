"""Validate source-backed completed US daily analysis before publication."""
import datetime as dt
import json
import math
from pathlib import Path
from urllib.parse import urlparse
ROOT = Path(__file__).resolve().parents[1]


ET = __import__('zoneinfo').ZoneInfo('America/New_York')


def finite_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def market_time(value):
    assert isinstance(value, str), 'Market timestamp required'
    parsed = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
    assert parsed.tzinfo is not None, 'Market timestamps must include an offset'
    return parsed.astimezone(ET)


def validate_earnings_prices(row):
    # Optional additive fields keep historical schemaVersion 1 rows readable.
    if 'releaseTiming' not in row and 'priceReaction' not in row:
        return
    timing = row.get('releaseTiming', {})
    session = timing.get('session', 'unknown')
    assert session in ('before_open', 'during_session', 'after_close', 'unknown')
    if session != 'unknown':
        assert timing.get('sourceIds'), 'Known earnings session requires source evidence'
    release_date = dt.date.fromisoformat(row['releaseDate'])
    published = market_time(timing['publishedAt']) if timing.get('publishedAt') is not None else None
    if published:
        assert published.date() == release_date, 'Release timestamp must use releaseDate in ET'
        if session == 'before_open':
            assert published.time() < dt.time(9, 30)
    reaction = row.get('priceReaction', {})
    if not reaction:
        return
    assert reaction.get('currency') == 'USD'
    regular = reaction.get('regular') or {}
    known = [regular.get(key) is not None for key in ('close', 'previousClose', 'changePct')]
    assert all(known) or not any(known), 'Partial regular-close comparisons must remain unverified'
    close_time = None
    if all(known):
        assert regular.get('sourceIds'), 'Regular closes require sources'
        assert regular['date'] == row['releaseDate'], 'Do not mix a later regular session into earnings'
        assert dt.date.fromisoformat(regular['previousDate']) < release_date
        close_time = market_time(regular['closedAt'])
        assert close_time.date() == release_date
        assert dt.time(9,30) < close_time.time() <= dt.time(16), 'Use actual exchange close, including half days'
        assert all(finite_number(regular[k]) for k in ('close','previousClose','changePct'))
        assert regular['close'] > 0 and regular['previousClose'] > 0
        expected = (regular['close'] / regular['previousClose'] - 1) * 100
        assert math.isclose(regular['changePct'], expected, abs_tol=0.005), 'Regular return is relative to previous close'
    if published and session == 'after_close':
        assert published.time() >= (close_time.time() if close_time else dt.time(16))
    if published and session == 'during_session':
        assert dt.time(9,30) <= published.time() <= (close_time.time() if close_time else dt.time(16))
    after = reaction.get('afterHours') or {}
    assert after.get('status') in ('verified', 'unverified', 'not_applicable')
    if after['status'] == 'verified':
        assert session == 'after_close', 'This reaction field is only for earnings released after close'
        assert close_time and published, 'Post-earnings quote needs verified close and exact release time'
        observed = market_time(after['observedAt'])
        assert observed.date() == release_date, 'No next-day premarket or stale prior-day quote'
        assert close_time <= published < observed, 'Quote must be strictly after the earnings release'
        assert observed.time() < dt.time(20), 'Not an overnight-session quote'
        assert after.get('sourceIds'), 'After-hours quote requires timestamped source'
        assert finite_number(after.get('price')) and after['price'] > 0
        assert finite_number(after.get('changePct'))
        expected = (after['price'] / regular['close'] - 1) * 100
        assert math.isclose(after['changePct'], expected, abs_tol=0.005), 'After-hours return is relative to same-day regular close'
    else:
        assert all(after.get(k) is None for k in ('price','changePct','observedAt')), 'Unavailable is null, never zero or a stale quote'
        if after['status'] == 'not_applicable':
            assert session in ('before_open','during_session'), 'Unknown or after-close release is unverified, not inapplicable'


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
            validate_earnings_prices(r)
    return len(entries)


if __name__ == '__main__':
    import sys
    p=Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'data/us_analysis.json'
    print(f'Validated {validate(json.loads(p.read_text()))} completed US daily entries.')
