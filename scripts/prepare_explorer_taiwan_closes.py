"""Prepare a small, licensed, regular-close Explorer update without refreshing other data.

Read-only by default. With --apply, write only the canonical Taiwan snapshot locally;
no git commands, remote writes, permissions changes, or historic price adjustments.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal, InvalidOperation
import hashlib
import io
import json
import math
from pathlib import Path
import re
import tempfile
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
SAVE = "data/explorer-taiwan-open-close-latest.json"
TZ = ZoneInfo("Asia/Taipei")
BASIS = "regular_close_unadjusted"
LICENSE = "https://data.gov.tw/license"
AGENCY = "Securities and Futures Bureau, Financial Supervisory Commission, Taiwan (金融監督管理委員會證券期貨局)"
VENUES = {
    "TWSE": (
        "日期", "證券代號", "收盤價", "https://data.gov.tw/en/datasets/11549",
        "https://www.twse.com.tw/exchangeReport/STOCK_DAY_ALL?response=open_data",
        "Taiwan Stock Exchange (臺灣證券交易所)",
        "After-hours information Stock daily transaction information (盤後資訊 > 個股日成交資訊)",
    ),
    "TPEX": (
        "資料日期", "代號", "收盤", "https://data.gov.tw/dataset/11371",
        "https://www.tpex.org.tw/web/stock/aftertrading/otc_quotes_no1430/stk_wn1430_result.php?l=zh-tw&o=data&se=EW",
        "Taipei Exchange (櫃買中心)",
        "OTC stock closing quotations (上櫃股票收盤行情)",
    ),
}
SIZE_LIMIT = 2_000_000


def roc_date(text: str) -> dt.date:
    if not re.fullmatch(r"[0-9]{7}", text):
        raise ValueError(f"Unexpected exchange date {text!r}")
    return dt.date(int(text[:3]) + 1911, int(text[3:5]), int(text[5:]))


def catalog_symbols(catalog: list[dict]) -> dict[str, set[str]]:
    result = {venue: set() for venue in VENUES}
    for item in catalog:
        venue, _, code = item["symbol"].partition(":")
        if venue not in VENUES:
            continue
        if not re.fullmatch(r"[0-9]{4}", code):
            raise ValueError(f"Unsupported Taiwan listing: {item['symbol']}")
        result[venue].add(code)
    if not all(result.values()):
        raise ValueError("Exchange roster is incomplete")
    return result


def source_csv(venue: str) -> bytes:
    url = VENUES[venue][4]
    request = Request(url, headers={"Accept": "text/csv", "User-Agent": "GlobalTechTerminal official close/1.0"})
    with urlopen(request, timeout=10) as response:
        if response.geturl() != url:
            raise ValueError(f"{venue}: unexpected source redirect")
        raw = response.read(SIZE_LIMIT + 1)
    if len(raw) > SIZE_LIMIT:
        raise ValueError(f"{venue}: oversized CSV")
    return raw


def extract(venue: str, raw: bytes, symbols: set[str], session: dt.date) -> dict:
    if not raw or len(raw) > SIZE_LIMIT:
        raise ValueError(f"{venue}: invalid CSV size")
    date_field, code_field, price_field, *_ = VENUES[venue]
    rows = csv.DictReader(io.StringIO(raw.decode("utf-8-sig"), newline=""), strict=True)
    header = rows.fieldnames or []
    if len(set(header)) != len(header) or not {date_field, code_field, price_field} <= set(header):
        raise ValueError(f"{venue}: unexpected CSV headers")
    quotes = {}
    for row in rows:
        if None in row or any(v is None for v in row.values()):
            raise ValueError(f"{venue}: malformed CSV row")
        date = roc_date(row[date_field].strip())
        if date != session:
            raise ValueError(f"{venue}: feed is {date}, not requested {session}")
        code = row[code_field].strip()
        if code not in symbols:
            continue
        if code in quotes:
            raise ValueError(f"{venue}:{code}: duplicate close")
        price = row[price_field].strip()
        if not re.fullmatch(r"(?:[0-9]+|[0-9]{1,3}(?:,[0-9]{3})+)(?:\.[0-9]+)?", price):
            raise ValueError(f"{venue}:{code}: missing or malformed close")
        value = float(Decimal(price.replace(",", "")))
        if not math.isfinite(value) or value <= 0:
            raise ValueError(f"{venue}:{code}: invalid close")
        quotes[code] = value
    if symbols - quotes.keys():
        raise ValueError(f"{venue}: no valid close for {', '.join(sorted(symbols - quotes.keys()))}")
    return quotes


def prepare(catalog: list[dict], raw: dict[str, bytes], session: dt.date, now: dt.datetime) -> dict:
    if now.utcoffset() is None:
        raise ValueError("The observation timestamp must be timezone-aware")
    local = now.astimezone(TZ)
    if session > local.date() or (session == local.date() and local.time() < dt.time(13, 30)):
        raise ValueError("Requested session has not completed in Taipei")
    if session.weekday() >= 5:
        raise ValueError("Requested date is not a regular trading weekday")
    roster = catalog_symbols(catalog)
    sources, quotes = {}, {}
    day = session.isoformat()
    for venue, data in VENUES.items():
        rates = extract(venue, raw[venue], roster[venue], session)
        key = venue.lower()
        for code in sorted(rates):
            quotes[f"{venue}:{code}"] = {
                "asOf": day, "close": rates[code], "currency": "TWD", "basis": BASIS, "sourceId": key,
            }
        _, _, _, dataset, url, market_name, dataset_name = data
        sources[key] = {
            "agency": AGENCY, "marketName": market_name, "datasetName": dataset_name,
            "datasetUrl": dataset, "rawUrl": url, "licenseName": "Open Government Data License, version 1.0 (Taiwan)",
            "licenseUrl": LICENSE, "attributionYear": session.year, "edition": f"{day} dated extract",
            "observedAt": now.astimezone(dt.timezone.utc).isoformat(),
            "sha256": hashlib.sha256(raw[venue]).hexdigest(), "matchingListings": len(rates),
        }
    return {
        "schemaVersion": 1, "sessionDate": day, "sessionTimezone": "Asia/Taipei", "basis": BASIS,
        "note": "Official raw regular-session closes only. Historical adjusted prices, returns, FX, and capitalization are maintained independently. Taiwan Open Government Data is reused under the referenced v1.0 license.",
        "sources": sources, "quotes": dict(sorted(quotes.items())),
    }


def should_update(previous: dict, candidate: dict) -> bool:
    prior = dt.date.fromisoformat(previous["sessionDate"])
    session = dt.date.fromisoformat(candidate["sessionDate"])
    if session < prior:
        raise ValueError(f"Refusing to replace later snapshot {prior} with {session}")
    if session > prior:
        return True
    if previous["quotes"] != candidate["quotes"]:
        raise ValueError("Same-session official closes differ; investigate revisions before publishing")
    return False


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", required=True, type=dt.date.fromisoformat)
    parser.add_argument("--twse-csv", type=Path)
    parser.add_argument("--tpex-csv", type=Path)
    parser.add_argument("--apply", action="store_true", help="Write the canonical local file; does not publish")
    parser.add_argument("--candidate-out", type=Path, help="Save a new-session dry-run candidate outside published paths")
    args = parser.parse_args()
    if bool(args.twse_csv) != bool(args.tpex_csv):
        parser.error("Provide both archived CSV files or neither")
    try:
        if args.apply and (args.twse_csv or args.candidate_out):
            raise ValueError("Local apply needs live exchange feeds and no alternate output")
        if args.candidate_out and args.candidate_out.resolve().is_relative_to(ROOT.resolve()):
            raise ValueError("Dry-run output must be outside the repository")
        now = dt.datetime.now(dt.timezone.utc)
        local = now.astimezone(TZ)
        if args.session > local.date() or (args.session == local.date() and local.time() < dt.time(13, 30)):
            raise ValueError("Requested session has not completed in Taipei")
        if args.twse_csv:
            raw = {"TWSE": args.twse_csv.read_bytes(), "TPEX": args.tpex_csv.read_bytes()}
        else:
            with ThreadPoolExecutor(max_workers=2) as pool:
                raw = dict(zip(VENUES, pool.map(source_csv, VENUES)))
            now = dt.datetime.now(dt.timezone.utc)
        dest = ROOT / SAVE
        current = json.loads(dest.read_text(encoding="utf-8"))
        catalog = json.loads((ROOT / "data/companies.json").read_text(encoding="utf-8"))
        candidate = prepare(catalog, raw, args.session, now)
        fresh = should_update(current, candidate)
        if fresh and (args.apply or args.candidate_out):
            output = dest if args.apply else args.candidate_out
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=output.parent, delete=False) as file:
                tmp = Path(file.name)
                try:
                    file.write(json.dumps(candidate, ensure_ascii=False, indent=2) + "\n")
                    file.flush()
                    tmp.chmod(0o644)
                    tmp.replace(output)
                finally:
                    tmp.unlink(missing_ok=True)
        print(json.dumps({"session": candidate["sessionDate"], "listings": len(candidate["quotes"]),
                          "status": "new" if fresh else "unchanged", "wroteLocalSnapshot": bool(fresh and args.apply)}))
    except (OSError, KeyError, ValueError, TypeError, InvalidOperation, csv.Error) as error:
        parser.exit(2, f"Taiwan close refresh stopped without publication: {error}\n")


if __name__ == "__main__":
    main()
