"""Fresh official KRX holiday list plus actual same-day KRX market flow evidence.
The anonymous public calendar response code is not a credential and is not saved.
Errors fail closed; no calendar-package or weekday-only fallback.
"""
from datetime import datetime, timezone, timedelta, date
import json
import urllib.parse
import urllib.request
from update_korean_market import collect_flows

KST = timezone(timedelta(hours=9))
BASE = 'https://open.krx.co.kr'
CALENDAR = BASE + '/contents/MKD/01/0110/01100305/MKD01100305.jsp'

def request(path, params, post=False):
    encoded = urllib.parse.urlencode(params)
    req = urllib.request.Request(BASE + path + ('' if post else '?' + encoded),
        data=encoded.encode() if post else None,
        headers={'User-Agent':'GlobalTechTerminal/1.0','Referer':CALENDAR})
    with urllib.request.urlopen(req, timeout=30) as response:
        return response.read().decode('utf-8')

def holiday_dates(payload, year):
    rows = payload.get('block1')
    if not isinstance(rows, list) or len(rows) < 5: raise ValueError('Incomplete official holiday calendar')
    dates = set()
    for row in rows:
        day = date.fromisoformat(row['calnd_dd'])
        if day.year != year or not row.get('holdy_nm'): raise ValueError('Unexpected official calendar schema/year')
        dates.add(day.isoformat())
    return dates

def collect_holidays(year):
    code = request('/contents/COM/GenerateOTP.jspx', {'name':'form','bld':'MKD/01/0110/01100305/mkd01100305_01'}).strip()
    if not code or '<' in code: raise ValueError('Official calendar response unavailable')
    return holiday_dates(json.loads(request('/contents/OPN/99/OPN99000001.jspx',
        {'search_bas_yy':str(year),'gridTp':'KRX','code':code}, post=True)), year)

def is_completed_session(now, holidays, market_dates, earliest=(17,30)):
    local = now.astimezone(KST)
    day = local.date().isoformat()
    return (local.weekday() < 5 and day not in holidays and (local.hour,local.minute) >= earliest
            and market_dates == {'KOSPI':day,'KOSDAQ':day})

def check(now, earliest=(17,30)):
    local = now.astimezone(KST)
    # Weekends need no publication and no source request.
    if local.weekday() >= 5: return False
    holidays = collect_holidays(local.year)
    if local.date().isoformat() in holidays: return False
    dates = {m:max(r['date'] for r in collect_flows(m,local.date().isoformat())) for m in ('KOSPI','KOSDAQ')}
    return is_completed_session(now,holidays,dates,earliest)
