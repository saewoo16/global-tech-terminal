import copy
from datetime import datetime
import unittest
from scripts.prepare_korean_etf_daily import prepare


def row(day, close):
    return dict(date=day, open=close, high=close+1, low=close-1, close=close, volume=100)


class DailyPrepare(unittest.TestCase):
    def setUp(self):
        self.sessions = ["2026-11-19", "2026-11-20"]
        self.a, self.b = (row(day, close) for day, close in zip(self.sessions, [100, 105]))
        self.snapshot = {"asOf":"2026-11-19","funds":[{"code":"123456","daily":[self.a],
            "dailyCoverage":{},"intraday":{"note":"retain but do not touch"},"name":"Preserve"}]}
        self.evidence = {"session":self.sessions[-1],"sourceUrl":"https://example.com/official","funds":{"123456":[self.a,self.b]},
            "priceBasis":"verified-krx-regular-session","historicalBasisCompatible":True,"publicReuseVerified":True}
        self.now = datetime.fromisoformat("2026-11-20T17:59:00+09:00")

    def test_only_new_daily_is_appended(self):
        before = copy.deepcopy(self.snapshot)
        out, changed = prepare(self.snapshot,self.evidence,self.sessions,self.now)
        self.assertEqual(changed,["123456"])
        self.assertEqual(out["funds"][0]["daily"],[self.a,self.b])
        self.assertEqual(out["funds"][0]["intraday"],before["funds"][0]["intraday"])
        self.assertEqual(before,self.snapshot)
        self.assertEqual(prepare(out,self.evidence,self.sessions,self.now)[1],[])

    def test_invalid_session_missing_row_and_changed_historical_price_are_rejected(self):
        with self.assertRaises(ValueError):
            prepare(self.snapshot,self.evidence,self.sessions,datetime.fromisoformat("2026-11-20T15:29:00+09:00"))
        for rows in [[self.b], [row(self.sessions[0],101),self.b], [self.a,self.b,self.b]]:
            e = {**self.evidence,"funds":{"123456":rows}}
            with self.assertRaises(ValueError):
                prepare(self.snapshot,e,self.sessions,self.now)
        with self.assertRaises(ValueError):
            prepare(self.snapshot,{**self.evidence,"publicReuseVerified":False},self.sessions,self.now)
