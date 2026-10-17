"""NAVER FUT market investor net contracts; scope is provider-defined.

The public trader UI identifies FUT as futures, uses contracts for diffValue,
and separately exposes buyQuant/sellQuant. No claim is made about mini contracts,
individual maturities or night-session inclusion. This is not a position series.
"""
import json
from datetime import datetime
from urllib.parse import urlencode
from urllib.request import Request, urlopen

SOURCE_ID = 'naver-futures-investor-daily'
API = 'https://stock.naver.com/api/domestic/market/trend/daily'


def endpoint(as_of, page):
    return API + '?' + urlencode({'tradeType': 'KRX', 'marketType': 'FUT',
                                 'bizdate': as_of.replace('-', ''),
                                 'startIdx': page, 'pageSize': 30})


def exact_integer(value):
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise ValueError('contract count must be an exact integer')
    text = str(value)
    if not text.lstrip('-').isdigit() or text.count('-') > 1:
        raise ValueError('contract count must be an exact integer')
    return int(value)


def parse_foreign_page(payload, as_of, page):
    if exact_integer(payload.get('number')) != page or not isinstance(payload.get('content'), list) or not payload['content']:
        raise ValueError('futures pagination/schema/empty content')
    rows = []
    for row in payload['content']:
        day = datetime.strptime(row['bizdate'], '%Y%m%d').date().isoformat()
        if day > as_of:
            raise ValueError('future futures observation rejected')
        parts = row['netAmounts']
        categories = {part['investorGubun']: part for part in parts}
        if len(categories) != len(parts) or '9000' not in categories:
            raise ValueError('missing or duplicate foreign investor category')
        foreign = categories['9000']
        buy, sell, net = (exact_integer(foreign[key]) for key in ('buyQuant', 'sellQuant', 'diffValue'))
        if buy < 0 or sell < 0 or buy - sell != net:
            raise ValueError('futures net does not equal buy minus sell')
        result = {'date': day, 'foreign': net, 'buy': buy, 'sell': sell, 'sourceId': SOURCE_ID}
        imbalance = sum(exact_integer(part['diffValue']) for key, part in categories.items() if key != '9999')
        if imbalance:
            result.update(sourceBalanceWarning=True, sourceInvestorNetImbalance=imbalance)
        rows.append(result)
    return rows


def fetch(url):
    request = Request(url, headers={'User-Agent': 'GlobalTechTerminal/1.0 (public market statistics)', 'Accept': 'application/json'})
    with urlopen(request, timeout=25) as response:
        return json.load(response)


def collect_foreign_flows(as_of):
    rows = []
    for page in range(2):
        rows.extend(parse_foreign_page(fetch(endpoint(as_of, page)), as_of, page))
    if len({row['date'] for row in rows}) != len(rows):
        raise ValueError('duplicate futures observation')
    return sorted(rows, key=lambda row: row['date'])


def update_quality(section):
    flagged = [row for row in section['rows'] if row.get('sourceBalanceWarning')]
    section['status'] = 'partial' if flagged else 'verified'
    section['qualityFlags'] = {
        'status': 'source-balance-warning' if flagged else 'no-source-balance-warning',
        'count': len(flagged), 'affectedDates': [row['date'] for row in flagged],
        'note': '일부 날짜의 전체 투자자 순매수 합계가 0과 다릅니다. 어느 범주에 원인이 있는지 확정할 수 없어 외국인 값을 수정하지 않고 공급사 수치 그대로 표시합니다.'}
    section['windowChecks'] = {
        str(n): {'sessions': n, 'start': section['rows'][-n]['date'],
                 'end': section['rows'][-1]['date'],
                 'foreignTotal': sum(row['foreign'] for row in section['rows'][-n:]),
                 'flaggedDates': [row['date'] for row in section['rows'][-n:] if row.get('sourceBalanceWarning')]}
        for n in (5, 21, 63, 126, 252) if len(section['rows']) >= n}

DAUM_PAGE = 'https://finance.daum.net/domestic/futures'
DAUM_MASTER = 'https://finance.daum.net/api/futures/masters'
OI_CONTRACT = 'KR4A016C0004'
OI_CONTRACT_NAME = 'F 202612'
OI_SOURCE_ID = 'daum-kospi200-dec2026-open-interest'


def fetch_daum(url):
    request = Request(url, headers={'User-Agent': 'Mozilla/5.0', 'Referer': DAUM_PAGE})
    with urlopen(request, timeout=25) as response:
        result = json.load(response)
    if result.get('code') != 200:
        raise ValueError('Daum public data response unsuccessful')
    return result


def parse_open_interest(master, history, as_of, contract_code=OI_CONTRACT, contract_name=OI_CONTRACT_NAME):
    if contract_code != OI_CONTRACT or contract_name != OI_CONTRACT_NAME:
        raise ValueError('unverified OI contract change; no automatic roll')
    if not any(row.get('symbolCode') == contract_code and row.get('name') == contract_name for row in master.get('data', [])):
        raise ValueError('fixed OI contract absent from current master; preserve old dates, no automatic roll')
    raw = history.get('data')
    if not isinstance(raw, list) or not raw:
        raise ValueError('missing open-interest observations')
    result, seen = [], set()
    for row in raw:
        day = datetime.strptime(row['date'][:10], '%Y-%m-%d').date().isoformat()
        value = row.get('unsettledVolume')
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError('open interest must be a nonnegative integral contract level')
        if day in seen or day > as_of:
            raise ValueError('duplicate or future OI date')
        seen.add(day)
        result.append({'date': day, 'openInterest': value, 'contractCode': contract_code, 'sourceId': OI_SOURCE_ID})
    result.sort(key=lambda row: row['date'])
    if result[-1]['date'] < as_of:
        raise ValueError('open-interest feed is stale; preserve last actual observation date')
    return result


def collect_open_interest(as_of, contract_code=OI_CONTRACT, contract_name=OI_CONTRACT_NAME):
    master = fetch_daum(DAUM_MASTER)
    history = fetch_daum(f'https://finance.daum.net/api/future/{contract_code}/days?page=1&perPage=60')
    return parse_open_interest(master, history, as_of, contract_code, contract_name)
