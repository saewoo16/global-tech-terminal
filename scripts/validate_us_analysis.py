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


def validate_fx(rows):
    """FX timestamps are observations, never an exchange-close assertion."""
    assert isinstance(rows, list)
    for row in rows:
        assert row.get('name') and row.get('basis'), 'FX needs name and observation/comparison basis'
        if 'decimals' in row:
            assert isinstance(row['decimals'], int) and not isinstance(row['decimals'], bool) and 0 <= row['decimals'] <= 8
        value = row.get('value')
        change = row.get('changePct')
        if value is None:
            assert change is None, 'Unknown FX value cannot have a verified percentage'
        else:
            assert finite_number(value) and value > 0
            assert row.get('sourceIds'), 'FX observation requires a source'
            market_time(row.get('observedAt'))
        assert change is None or finite_number(change)
        if row.get('observedAt') is not None:
            market_time(row['observedAt'])


def validate_unusual_movers(screen, member_symbols, date, cap500=False):
    """Validate exact two-session volume and price filters within a stated universe."""
    assert isinstance(screen, dict)
    assert screen.get('criteria') and screen.get('note') and screen.get('sourceIds')
    coverage = screen.get('coverage', {})
    assert coverage.get('universe') == ('미국 상장 시총 상위 500 (공급사 대표 티커)' if cap500 else 'S&P 500'), 'Screen must state its actual universe'
    if cap500:
        roster = screen.get('constituents', [])
        assert len(roster) == 500 and {r['rank'] for r in roster} == set(range(1, 501))
        assert len({r['ticker'] for r in roster}) == 500
        member_symbols = {r['ticker'] for r in roster}
        assert dt.date.fromisoformat(coverage['universeAsOf']) <= date
        assert market_time(coverage['rankingObservedAt']).date().isoformat() == coverage['universeAsOf']
    for key in ('selected', 'volumeValid', 'missingCount'):
        count = coverage.get(key)
        assert isinstance(count, int) and not isinstance(count, bool) and count >= 0
    assert coverage['selected'] == coverage['volumeValid'] + coverage['missingCount']
    if member_symbols:
        assert coverage['selected'] == len(member_symbols), 'Coverage must include the stated S&P 500 membership'
    assert dt.date.fromisoformat(coverage['previousSession']) < date
    rows = screen.get('rows')
    assert isinstance(rows, list) and len(rows) <= coverage['volumeValid']
    assert len({r['ticker'] for r in rows}) == len(rows), 'Duplicate unusual-mover row'
    for row in rows:
        assert not member_symbols or row['ticker'] in member_symbols
        assert row.get('name') and row.get('sector') and row.get('sourceIds')
        assert finite_number(row.get('changePct')) and abs(row['changePct']) >= 5
        for key in ('volumeCurrent', 'volumePrevious'):
            volume = row.get(key)
            assert isinstance(volume, int) and not isinstance(volume, bool) and 0 < volume <= 2**53 - 1, 'Exact positive share volumes required'
        ratio = row['volumeCurrent'] / row['volumePrevious']
        assert ratio >= 2, 'Volume must be at least twice the previous session'
        assert finite_number(row.get('volumeRatio')) and math.isclose(row['volumeRatio'], ratio, rel_tol=0, abs_tol=1e-9), 'Volume ratio must use exact two-session volumes'
        assert isinstance(row.get('reasonVerified'), bool)
        if row['reasonVerified']:
            assert row.get('reason')


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
        observed = market_time(after['observedAt'])
        assert observed.date() == release_date, 'No next-day premarket or stale prior-day quote'
        if after.get('basis') == 'same_session_regular_close':
            # Neutral same-day movement is valid for morning/unknown release times too.
            assert close_time and close_time < observed, 'Session quote must be after verified regular close'
            assert observed.time() <= dt.time(20), 'Not an overnight-session quote'
            assert after.get('collectedAt'), 'Session quote requires actual collection time'
            assert market_time(after['collectedAt']) >= observed
            if row.get('reportCutoffAt'):
                assert market_time(after['collectedAt']) <= market_time(row['reportCutoffAt']), 'Later collection belongs in subsequentAfterHours'
        else:
            # Preserve the stricter historical post-announcement reaction contract.
            assert session == 'after_close', 'This reaction field is only for earnings released after close'
            assert close_time and published, 'Post-earnings quote needs verified close and exact release time'
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

    supplement = reaction.get('subsequentAfterHours')
    if supplement:
        assert supplement.get('status') == 'verified'
        assert close_time, 'Session after-hours comparison needs verified regular close'
        observed = market_time(supplement['observedAt'])
        assert observed.date() == release_date, 'After-hours supplement must use the same ET trading date'
        assert close_time < observed and observed.time() <= dt.time(20), 'After-hours supplement must be after close, not overnight'
        assert supplement.get('sourceIds'), 'After-hours supplement requires timestamped source'
        assert finite_number(supplement.get('price')) and supplement['price'] > 0
        expected = (supplement['price'] / regular['close'] - 1) * 100
        assert finite_number(supplement.get('changePct')) and math.isclose(supplement['changePct'], expected, abs_tol=0.005), 'After-hours supplement uses same-day regular close'
        if supplement.get('collectedAt'):
            assert market_time(supplement['collectedAt']) >= observed
            assert supplement.get('presentationPhase') == 'supplement'


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
        if 'fx' in e:
            validate_fx(e['fx'])
        for row in e['sectors']['rows']:
            for k in ('day','week','month'):
                assert row.get(k) is None or isinstance(row[k], (int,float))
            if row.get('instrumentType') == 'etf' and row.get('holdings',{}).get('status') == 'verified':
                h=row['holdings']; assert len(h.get('top3',h.get('top5',[]))) >= 3
                dt.date.fromisoformat(h['asOf']); assert h['sourceIds']
        member_symbols={r['ticker'] for r in e.get('constituents',[])}
        if member_symbols:
            assert len(member_symbols)>=500
        if 'unusualMovers' in e:
            validate_unusual_movers(e['unusualMovers'], member_symbols, date)
        if 'marketCapUnusualMovers' in e:
            validate_unusual_movers(e['marketCapUnusualMovers'], set(), date, cap500=True)
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
        top = e.get('earnings', {}).get('topMarketCapUniverse', {})
        top_members = set()
        if top:
            assert top.get('status') == 'verified' and top.get('sourceIds')
            assert dt.date.fromisoformat(top['asOf']) <= date
            assert len(top.get('rows', [])) == 10 and {x['rank'] for x in top['rows']} == set(range(1, 11))
            assert len({x['ticker'] for x in top['rows']}) == 10
            top_members = {x['ticker'] for x in top['rows']}
        for r in e.get('earnings',{}).get('rows',[]):
            assert r['ticker'] in member_symbols or r['ticker'] in top_members or r['ticker'] == 'SPCX', 'Earnings scope is S&P500 plus verified US top10 plus explicit SPCX only'
            assert r.get('sourceIds') and r.get('releaseDate')
            dt.date.fromisoformat(r['releaseDate'])
            assert r['releaseDate'] == e['date'], 'Earnings stay on their actual ET announcement session'
            if r.get('releaseTiming', {}).get('publishedAt'):
                assert market_time(r['releaseTiming']['publishedAt']).date().isoformat() == e['date'], 'Announcement timestamp must match entry in America/New_York, not KST or refresh date'
                if e.get('earnings', {}).get('reportCutoffAt'):
                    assert market_time(r['releaseTiming']['publishedAt']) <= market_time(e['earnings']['reportCutoffAt']), 'Release was not available at the stated report cutoff'
            metrics = r.get('metrics', [])
            if r.get('presentationVersion') == 3:
                assert [m.get('label') for m in metrics] == ['매출', '매출총이익', '매출총이익률', '영업이익', 'EPS'], 'Exactly five requested principal metrics'
                history = r.get('quarterlyHistory', {})
                assert len(history.get('rows', [])) == 4, 'Four reported quarters required'
                for quarter in history['rows']:
                    assert all(key in quarter for key in ('revenue', 'grossProfit', 'grossMargin', 'operatingIncome', 'eps'))
                    assert quarter.get('sourceIds')
            elif r.get('presentationVersion') == 2:
                assert len(metrics) == 4, 'Current earnings show exactly four principal metrics'
                labels = [m.get('label', '') for m in metrics]
                assert any(label in ('매출', '매출액') for label in labels)
                assert '영업이익' in labels and '영업이익률' in labels
                assert any('순이익' in label for label in labels)
                history = r.get('quarterlyHistory', {})
                assert len(history.get('rows', [])) == 4, 'Four reported quarters required'
            else:
                assert len(metrics) >= 8
            validate_earnings_prices(r)
    return len(entries)


if __name__ == '__main__':
    import sys
    p=Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'data/us_analysis.json'
    print(f'Validated {validate(json.loads(p.read_text()))} completed US daily entries.')
