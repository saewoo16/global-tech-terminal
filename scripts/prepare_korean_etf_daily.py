"""Validate bounded regular-close ETF tails without any network or intraday fetch."""
import argparse
import copy
from datetime import date, datetime
import json
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

try:
    from update_korean_etf_charts import preserve_daily_history
except ModuleNotFoundError:
    from scripts.update_korean_etf_charts import preserve_daily_history

ROOT = Path(__file__).resolve().parents[1]
KST = ZoneInfo("Asia/Seoul")
FIELDS = {"date", "open", "high", "low", "close", "volume"}


def valid_day(day):
    return isinstance(day, str) and date.fromisoformat(day).isoformat() == day


def prepare(snapshot, evidence, sessions, observed_at):
    """Call only with calendar dates and redistribution provenance verified upstream."""
    if not sessions or sorted(set(sessions)) != sessions or not all(map(valid_day, sessions)):
        raise ValueError("Need ordered verified exchange sessions")
    day = sessions[-1]
    now = observed_at.astimezone(KST)
    if day > now.date().isoformat() or (day == now.date().isoformat() and (now.hour, now.minute) < (15, 30)):
        raise ValueError("Not an elapsed regular-session close")
    url = urlparse(evidence["sourceUrl"])
    if url.scheme != "https" or not url.hostname or url.username or url.password:
        raise ValueError("Source must be a traceable HTTPS URL")
    if (evidence.get("session") != day or evidence.get("priceBasis") != "verified-krx-regular-session"
            or evidence.get("historicalBasisCompatible") is not True or evidence.get("publicReuseVerified") is not True):
        raise ValueError("Require regular-close evidence, compatible OHLC basis and public reuse verification")
    incoming = evidence.get("funds")
    if not isinstance(incoming, dict) or not incoming:
        raise ValueError("No new dated fund observations")
    out = copy.deepcopy(snapshot)
    roster = {f["code"]: f for f in out["funds"]}
    if set(incoming) - roster.keys():
        raise ValueError("Unknown fund code")
    changed = []
    for code, rows in incoming.items():
        old = roster[code]
        last = old["daily"][-1]["date"]
        if last > day or last not in sessions:
            raise ValueError(code + ": verified sessions must include retained boundary")
        first = rows[0].get("date") if isinstance(rows, list) and rows and isinstance(rows[0], dict) else None
        expected = [d for d in sessions if d >= first] if first in sessions and first <= last else []
        if not expected or not all(isinstance(r, dict) for r in rows) or [r.get("date") for r in rows] != expected:
            raise ValueError(code + ": missing, duplicated or wrong trading date")
        if any(set(r) != FIELDS or any(type(r[k]) is not int for k in FIELDS - {"date"})
               or r["volume"] < 0 or not (0 < r["low"] <= min(r["open"], r["close"]) <= max(r["open"], r["close"]) <= r["high"])
               for r in rows):
            raise ValueError(code + ": malformed same-basis OHLC")
        probe = copy.deepcopy(old)
        probe["daily"] = rows
        merged = preserve_daily_history(probe, old)
        if merged["daily"] != old["daily"]:
            old["daily"] = merged["daily"]
            old["dailyCoverage"] = merged["dailyCoverage"]
            old["historyPreservation"] = merged["historyPreservation"]
            old["latestDailySource"] = {"date": day, "url": evidence["sourceUrl"], "basis": evidence["priceBasis"]}
            changed.append(code)
    return out, changed


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True, type=Path, help="verified OHLC evidence bundle; never a quote snapshot")
    p.add_argument("--sessions", required=True, help="verified consecutive trading dates, including retained boundary")
    p.add_argument("--target", type=Path, default=ROOT / "data/korean_etf_charts.json")
    p.add_argument("--apply", action="store_true", help="write the validated candidate locally, never publish")
    a = p.parse_args()
    candidate, changed = prepare(json.loads(a.target.read_text()), json.loads(a.input.read_text()),
                                 a.sessions.split(","), datetime.now(KST))
    if changed and a.apply:
        path = a.target.with_suffix(".daily.tmp")
        path.write_text(json.dumps(candidate, ensure_ascii=False, separators=(",", ":")) + "\n")
        path.replace(a.target)
    print(json.dumps({"status": "candidate" if changed else "unchanged", "changed": sorted(changed), "wrote": bool(changed and a.apply)}))


if __name__ == "__main__":
    main()
