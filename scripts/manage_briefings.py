#!/usr/bin/env python3
"""Validate and atomically upsert verified daily market briefs; never fabricate missing data."""
import argparse
import copy
from datetime import date, datetime, timezone
import json
import math
import os
from pathlib import Path
import tempfile
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PATH = ROOT / 'data' / 'briefings.json'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def valid_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def valid_url(value):
    if not isinstance(value, str):
        return False
    parsed = urlparse(value)
    return parsed.scheme in ('https', 'http') and bool(parsed.hostname) and not parsed.username and not parsed.password


def validate_entry(entry):
    require(isinstance(entry, dict), 'Each entry must be an object')
    require(entry.get('market') in ('US', 'KR'), 'market must be US or KR')
    try:
        require(date.fromisoformat(entry['date']).isoformat() == entry['date'], 'Invalid trading date')
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError('date must be a real YYYY-MM-DD trading date') from exc
    require(entry.get('status') in ('partial', 'complete'), 'status must be partial or complete')
    require(isinstance(entry.get('title'), str) and entry['title'].strip(), 'A title is required')
    sources = entry.get('sources', [])
    require(isinstance(sources, list) and sources, 'At least one verified source is required')
    source_ids = set()
    for source in sources:
        require(isinstance(source, dict), 'Each source must be an object')
        require(isinstance(source.get('id'), str) and source['id'] not in source_ids, 'Source IDs must be unique strings')
        require(isinstance(source.get('title'), str) and source['title'].strip(), 'Source title is required')
        require(valid_url(source.get('url')), 'Source URL must be HTTP(S), without credentials')
        source_ids.add(source['id'])
    for field in ('summary', 'indices', 'watchlist', 'limitations'):
        require(isinstance(entry.get(field, []), list), field+' must be an array')
    for field in ('watchlist', 'limitations'):
        require(all(isinstance(item, str) for item in entry.get(field, [])), field+' must contain strings')
    for item in entry.get('summary', []):
        require(isinstance(item, dict) and isinstance(item.get('title'), str) and isinstance(item.get('text'), str), 'Summary points need title and text')
    for item in entry.get('indices', []):
        require(isinstance(item, dict) and isinstance(item.get('name'), str), 'Index rows need a name')
    for field in ('sectors', 'movers', 'highs', 'earnings', 'flows'):
        section = entry.get(field, {})
        require(isinstance(section, dict) and isinstance(section.get('rows', []), list), field+' must have a rows array')
        for row in section.get('rows', []):
            require(isinstance(row, dict), field+' rows must be objects')
            if field != 'flows':
                require(isinstance(row.get('name'), str) and isinstance(row.get('ticker'), str), field+' rows need name and ticker')
            else:
                require(isinstance(row.get('market'), str), 'flows rows need market')
            if field == 'sectors':
                require(row.get('instrumentType') in (None, 'etf', 'basket'), 'instrumentType must be etf or basket')
                holdings = row.get('holdings')
                if holdings is not None:
                    require(row.get('instrumentType') == 'etf', 'Holdings metadata requires an ETF row')
                    require(isinstance(holdings, dict), 'holdings must be an object')
                    require(holdings.get('status') in ('verified', 'unverified'), 'Holdings status is required')
                    if holdings['status'] == 'verified':
                        try:
                            require(date.fromisoformat(holdings['asOf']).isoformat() == holdings['asOf'], 'Invalid holdings date')
                        except (KeyError, TypeError, ValueError) as exc:
                            raise ValueError('Holdings asOf must be a real YYYY-MM-DD date') from exc
                        require(isinstance(holdings.get('sourceIds'), list) and holdings['sourceIds'], 'Verified holdings need sources')
                        top = holdings.get('top5')
                        require(isinstance(top, list) and len(top) == 5, 'Verified holdings require exactly five constituents')
                        seen, weights = set(), []
                        for item in top:
                            require(isinstance(item, dict) and isinstance(item.get('name'), str) and item['name'].strip(), 'Holding name is required')
                            require(isinstance(item.get('ticker'), str) and item['ticker'].strip() and item['ticker'] not in seen, 'Holding tickers must be unique nonempty strings')
                            require('shortName' not in item or (isinstance(item['shortName'], str) and item['shortName'].strip()), 'Holding shortName must be nonempty text')
                            seen.add(item['ticker'])
                            weight = item.get('weightPct')
                            require(valid_number(weight) and 0 < weight <= 100, 'Holding weightPct must be between 0 and 100')
                            weights.append(weight)
                        require(weights == sorted(weights, reverse=True), 'Holdings must be in descending weight order')
                        require(sum(weights) <= 100.05, 'Top-five weights cannot exceed 100% beyond rounding')
                    else:
                        require(not holdings.get('top5'), 'Unverified holdings cannot claim top-five constituents')
                        require(isinstance(holdings.get('note'), str) and holdings['note'].strip(), 'Unverified holdings need an explanation')
            if field == 'earnings':
                require(isinstance(row.get('callHighlights', []), list), 'callHighlights must be an array')
                require(all(isinstance(item, str) for item in row.get('callHighlights', [])), 'callHighlights must contain strings')
                require(isinstance(row.get('metrics', []), list), 'metrics must be an array')
                for metric in row.get('metrics', []):
                    require(isinstance(metric, dict) and isinstance(metric.get('label'), str) and isinstance(metric.get('value'), str), 'metrics need string label and value')
    numeric_fields = {'close', 'changePct', 'day', 'week', 'month', 'marketCapUSD', 'volumeCurrent', 'volumePrevious', 'volumeChangePct', 'foreign', 'institution', 'individual'}
    nonnegative = {'close', 'marketCapUSD', 'volumeCurrent', 'volumePrevious'}
    returns = {'changePct', 'day', 'week', 'month', 'volumeChangePct'}
    def walk(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key == 'sourceIds':
                    require(isinstance(item, list) and all(isinstance(x, str) and x in source_ids for x in item), 'Unknown or malformed sourceIds')
                elif key in numeric_fields and item is not None:
                    require(valid_number(item), key+' must be a finite number or null')
                    require(key not in nonnegative or item >= 0, key+' cannot be negative')
                    require(key not in returns or item >= -100, key+' cannot be below -100%')
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)
        elif isinstance(value, float):
            require(math.isfinite(value), 'Non-finite values are forbidden')
    walk(entry)
    return entry


def validate_document(payload):
    require(isinstance(payload, dict) and payload.get('schemaVersion') == 1, 'schemaVersion must be 1')
    require(isinstance(payload.get('entries'), list), 'entries must be an array')
    keys = set()
    for entry in payload['entries']:
        validate_entry(entry)
        key = (entry['market'], entry['date'])
        require(key not in keys, 'Duplicate market/date: '+str(key))
        keys.add(key)
    return payload


def upsert(payload, incoming):
    validate_document(payload)
    new_entries = incoming.get('entries') if isinstance(incoming, dict) and 'entries' in incoming else [incoming]
    require(isinstance(new_entries, list), 'Incoming entries must be an array')
    index = {(entry['market'], entry['date']): copy.deepcopy(entry) for entry in payload['entries']}
    for entry in new_entries:
        validate_entry(entry)
        index[(entry['market'], entry['date'])] = copy.deepcopy(entry)
    result = {'schemaVersion': 1, 'updatedAt': datetime.now(timezone.utc).isoformat(),
              'entries': sorted(index.values(), key=lambda item: (item['date'], item['market']), reverse=True)}
    return validate_document(result)


def save_atomic(path, payload):
    path = Path(path)
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, delete=False) as output:
        tmp = output.name
        try:
            json.dump(payload, output, ensure_ascii=False, indent=2, allow_nan=False)
            output.write('\n')
            output.flush()
            os.fsync(output.fileno())
        except BaseException:
            os.unlink(tmp)
            raise
    os.replace(tmp, path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--file', type=Path, default=DEFAULT_PATH)
    parser.add_argument('--entry', type=Path, help='Verified entry or schemaVersion:1 document to upsert')
    args = parser.parse_args()
    payload = json.loads(args.file.read_text(encoding='utf-8'))
    if args.entry:
        payload = upsert(payload, json.loads(args.entry.read_text(encoding='utf-8')))
        save_atomic(args.file, payload)
    else:
        validate_document(payload)
    print('Validated '+str(len(payload['entries']))+' daily market briefings')


if __name__ == '__main__':
    main()
