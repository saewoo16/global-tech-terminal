"""Validate the public Korean-market snapshot. No estimates or synthetic fills."""
import argparse
import json
import math
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
MARKETS = ("KOSPI", "KOSDAQ")
STATUSES = ("verified", "partial", "unavailable")


def valid_date(value):
    if not isinstance(value, str):
        return False
    try:
        return date.fromisoformat(value).isoformat() == value
    except ValueError:
        return False


def number(value):
    return isinstance(value, (float, int)) and not isinstance(value, bool) and math.isfinite(value)


def validate(payload):
    errors = []
    def check(ok, message):
        if not ok:
            errors.append(message)
    check(payload.get("schemaVersion") == 1, "schemaVersion must be 1")
    check(valid_date(payload.get("asOf")), "asOf must be a valid ISO date")
    try:
        timestamp = datetime.fromisoformat(payload.get("updatedAt", "").replace("Z", "+00:00"))
        check(timestamp.tzinfo is not None, "updatedAt needs timezone")
    except (ValueError, TypeError):
        errors.append("updatedAt must be an ISO timestamp")
    sources = payload.get("sources", [])
    check(isinstance(sources, list) and bool(sources), "sources required")
    ids = set()
    for source in sources:
        sid = source.get("id")
        check(isinstance(sid, str) and bool(sid) and sid not in ids, "source IDs must be unique")
        ids.add(sid)
        url = urlparse(source.get("url", ""))
        check(url.scheme in ("http", "https") and bool(url.netloc) and not url.username and not url.password, f"unsafe source URL: {sid}")
        check(bool(source.get("title")), f"source needs title: {sid}")

    theme_catalog = {b.get('id'): b for b in payload.get('themes', {}).get('baskets', [])}

    def section(value, path, row_kind, keys, size=None):
        check(isinstance(value, dict), f"{path}: section required")
        if not isinstance(value, dict):
            return
        check(value.get("status") in STATUSES, f"{path}: explicit status required")
        refs = value.get("sourceIds", [])
        check(isinstance(refs, list) and all(ref in ids for ref in refs), f"{path}: unknown source reference")
        rows = value.get("rows", [])
        check(isinstance(rows, list), f"{path}: rows must be array")
        if not isinstance(rows, list):
            return
        if rows:
            check(bool(refs), f"{path}: populated rows need source IDs")
            check(value.get("status") != "unavailable", f"{path}: unavailable cannot contain data")
        if not rows:
            check(value.get("status") == "unavailable", f"{path}: no observations must be unavailable")
            check(bool(value.get("note")), f"{path}: unavailable needs explanation")
        seen = set()
        previous = None
        for row in rows:
            if row_kind == "time":
                key = row.get("date")
                check(valid_date(key), f"{path}: invalid row date {key}")
                if valid_date(key):
                    check(not valid_date(payload.get("asOf")) or key <= payload["asOf"], f"{path}: row after asOf")
                    check(previous is None or key > previous, f"{path}: dates must ascend")
                    previous = key
            elif row_kind == "rank":
                key = row.get("code")
                check(isinstance(key, str) and bool(key), f"{path}: missing stock code")
                check(bool(row.get("name")), f"{path}: missing stock name")
                check(row.get("market") in MARKETS, f"{path}: invalid stock market")
                amount = row.get("value")
                check(number(amount) and amount >= 0, f"{path}: ranking values must be non-negative numbers")
                if number(amount):
                    check(previous is None or amount <= previous, f"{path}: rankings must descend")
                    previous = amount
            else:
                key = row.get("name")
                check(isinstance(key, str) and bool(key), f"{path}: missing theme name")
            check(key not in seen, f"{path}: duplicate row {key}")
            seen.add(key)
            if "sourceId" in row:
                check(row["sourceId"] in ids, f"{path}: unknown row source ID")
            for field in keys:
                check(field in row and (row[field] is None or number(row[field])), f"{path}: {field} must be finite number or null")
            if row_kind == "theme":
                basket = theme_catalog.get(row.get("id"), {})
                members = row.get("members", basket.get("members", []))
                codes = [m.get("code") for m in members]
                check(bool(members) and len(set(codes)) == len(codes), f"{path}: unique theme members required")
                check(len(members) == row.get("memberCount"), f"{path}: member count mismatch")
                for member in members:
                    evidence = member.get("classificationEvidence")
                    check(isinstance(evidence, dict) and evidence.get("classification_status") == "verified", f"{path}: verified membership evidence required")
                    if isinstance(evidence, dict):
                        check(all(sid in ids for sid in evidence.get("sourceIds", [])), f"{path}: unknown classification source")
                display = row.get("displayMembers", basket.get("displayMembers"))
                if display is not None:
                    cap_date = basket.get("marketCapAsOf", payload.get("themes", {}).get("marketCapAsOf"))
                    check(valid_date(cap_date), f"{path}: market cap date required")
                    caps_valid = all(number(m.get("marketCapKRW")) and m["marketCapKRW"] > 0 for m in members)
                    check(caps_valid, f"{path}: market caps required for every display candidate")
                    if caps_valid:
                        top = sorted(members, key=lambda m: (-m["marketCapKRW"], m["code"]))[:3]
                        check([m.get("code") for m in display] == [m["code"] for m in top], f"{path}: display members must be full-universe market cap top3")
                    check(all(m.get("marketCapSourceId") in ids for m in members), f"{path}: unknown market cap source")
                    check(all(m.get("marketCapAsOf") == cap_date for m in members), f"{path}: mixed market cap dates")
                for investor in ("foreign", "institution"):
                    cell = row.get("coverage", {}).get(investor, {})
                    components = cell.get("memberFlows", [])
                    check(len(components) == len(members), f"{path}: component count mismatch")
                    check({r.get("code") for r in components} == set(codes) and len({r.get("code") for r in components}) == len(components), f"{path}: component codes must match full membership")
                    check(all(r.get("netBuyKRW") is None or number(r.get("netBuyKRW")) for r in components), f"{path}: invalid constituent amount")
                    available = [r for r in components if number(r.get("netBuyKRW"))]
                    check(cell.get("expectedCount") == len(members), f"{path}: expected constituent count mismatch")
                    if "knownSubtotalKRW" in cell:
                        expected_subtotal = sum(r["netBuyKRW"] for r in available) if available else None
                        check(cell.get("knownSubtotalKRW") == expected_subtotal, f"{path}: known subtotal mismatch")
                        expected_eok = None if expected_subtotal is None else expected_subtotal / 1e8
                        check(cell.get("knownSubtotalEok") == expected_eok, f"{path}: known subtotal unit mismatch")
                    check(cell.get("availableCount") == len(available), f"{path}: available constituent count mismatch")
                    if len(available) == len(members):
                        theme_value = row.get(investor)
                        check(number(theme_value) and abs(theme_value - sum(r["netBuyKRW"] for r in available) / 1e8) < 1e-7, f"{path}: theme sum mismatch")
                    else:
                        check(row.get(investor) is None and cell.get("netBuyKRW") is None and cell.get("netBuyEok") is None, f"{path}: incomplete theme must stay null")
                        check(cell.get("rank") is None, f"{path}: incomplete theme cannot have rank")
                        check(cell.get("status") != "complete", f"{path}: incomplete theme cannot claim complete")
                    check(all(r.get("sourceId") in ids for r in available), f"{path}: unknown constituent amount source")

            if row_kind == "time" and keys == ("value",):
                check(row.get("value") is None or number(row.get("value")) and row["value"] >= 0, f"{path}: balance cannot be negative")
        if size:
            check(len(rows) <= size, f"{path}: too many rank rows")
        coverage = value.get("coverage", {})
        if row_kind == "time" and rows:
            check(coverage.get("start") == rows[0].get("date"), f"{path}: coverage start mismatch")
            check(coverage.get("end") == rows[-1].get("date"), f"{path}: coverage end mismatch")
            check(coverage.get("count") == len(rows), f"{path}: coverage count mismatch")

    flows = payload.get("flows", {})
    check(flows.get("unit") == "억원", "flow unit must be 억원")
    for market in MARKETS:
        section(flows.get("markets", {}).get(market), f"flows.{market}", "time", ("foreign", "institution", "individual"))
    liquidity = payload.get("liquidity", {})
    check(liquidity.get("unit") == "억원", "liquidity unit must be 억원")
    check(liquidity.get("depositScope") == "market-wide", "deposits must be labeled market-wide")
    for key in ("deposits", "creditKOSPI", "creditKOSDAQ"):
        section(liquidity.get("series", {}).get(key), f"liquidity.{key}", "time", ("value",))
    for group in ("rankings", "themes"):
        obj = payload.get(group, {})
        check(obj.get("unit") == "억원", f"{group} unit must be 억원")
        dates = obj.get("dates", [])
        check(isinstance(dates, list) and len(dates) <= 5 and len(set(dates)) == len(dates) and all(valid_date(d) for d in dates), f"{group}: invalid recent trading dates")
        daily = obj.get("daily", {})
        check(isinstance(daily, dict) and set(daily) == set(dates), f"{group}: dates and daily keys mismatch")
        periods = list(daily.items()) + [("5d", obj.get("aggregate5d", {}))]
        if "monthly" in obj:
            periods.append(("1m", obj["monthly"]))
        for day, entry in periods:
            if group == "rankings":
                for key in ("foreign", "institution", "tradedValue"):
                    section(entry.get(key), f"{group}.{day}.{key}", "rank", ("value",), 20 if key == "tradedValue" else 10)
            else:
                section(entry, f"{group}.{day}", "theme", ("foreign", "institution"))
    movers = payload.get("indexMovers", {})
    mover_periods = list(movers.get("daily", {}).items()) + [(name, movers.get(name, {})) for name in ("aggregate5d", "monthly")]
    for period_name, entries in mover_periods:
        for index, item in entries.items():
            check(index in ("KOSPI200", "KOSDAQ150"), "unknown index")
            check(item.get("status") in STATUSES, f"{index}: index section status required")
            check(all(ref in ids for ref in item.get("sourceIds", [])), f"{index}: unknown source ID")
            if item.get("gainers") or item.get("losers"):
                check(bool(item.get("sourceIds")), f"{index}: populated index needs sources")
                check(valid_date(item.get("comparisonStart")) and valid_date(item.get("comparisonEnd")), f"{index}: comparison dates required")
                if valid_date(item.get("comparisonStart")) and valid_date(item.get("comparisonEnd")):
                    check(item["comparisonStart"] < item["comparisonEnd"], f"{index}: comparison dates must increase")
            seen = set()
            for kind in ("gainers", "losers"):
                rows = item.get(kind, [])
                check(len(rows) <= 10, f"{index}: more than 10 {kind}")
                previous = None
                for row in rows:
                    value = row.get("changePct")
                    check(number(value), f"{index}: numeric percent required")
                    check(bool(row.get("code")) and bool(row.get("name")), f"{index}: code/name required")
                    check(row.get("code") not in seen, f"{index}: repeated stock")
                    seen.add(row.get("code"))
                    check(all(sid in ids for sid in row.get("sourceIds", [])), f"{index}: unknown row source")
                    a, b = row.get("startClose"), row.get("endClose")
                    check(number(a) and number(b) and a > 0 and b > 0, f"{index}: positive start/end closes required")
                    if number(a) and number(b) and a > 0 and number(value):
                        check(abs(value - (b / a - 1) * 100) < 1e-8, f"{index}: return arithmetic mismatch")
                    if number(value):
                        check(value > 0 if kind == "gainers" else value < 0, f"{index}: wrong {kind} sign")
                        check(previous is None or (value <= previous if kind == "gainers" else value >= previous), f"{index}: wrong {kind} ordering")
                        previous = value
    return errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("path", nargs="?", default=str(ROOT / "data/korea-market.json"))
    args = parser.parse_args()
    data = json.loads(Path(args.path).read_text())
    errors = validate(data)
    if errors:
        raise SystemExit("\n".join(errors))
    print(f"Korean market data valid: asOf={data['asOf']}, {len(data['sources'])} sources")


if __name__ == "__main__":
    main()
