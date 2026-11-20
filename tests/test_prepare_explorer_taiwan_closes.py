import datetime as dt
import hashlib
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from prepare_explorer_taiwan_closes import BASIS, catalog_symbols, extract, prepare, roc_date, should_update

DAY = dt.date(2026, 11, 19)
AFTER = dt.datetime(2026, 11, 19, 6, 0, tzinfo=dt.timezone.utc)
CATALOG = [{"symbol": "TWSE:2308"}, {"symbol": "TWSE:2344"}, {"symbol": "TWSE:2308"},
           {"symbol": "TPEX:6488"}, {"symbol": "NASDAQ:NVDA"}]
TWSE = ('日期,證券代號,證券名稱,收盤價\r\n'
        '"1151119","2308","台達電","1,000.00"\r\n'
        '"1151119","2344","華邦電","98.00"\r\n'
        '"1151119","00400A","Other security","56.00"\r\n').encode()
TPEX = ('資料日期,代號,名稱,收盤\r\n'
        '"1151119","6488","環球晶","490.00"\r\n').encode()


class TaiwanOfficialCloseTests(unittest.TestCase):
    def prepare(self, twse=TWSE, tpex=TPEX, day=DAY, now=AFTER):
        return prepare(CATALOG, {"TWSE": twse, "TPEX": tpex}, day, now)

    def test_exact_source_rows_and_basis(self):
        self.assertEqual(roc_date("1151119"), DAY)
        self.assertEqual(catalog_symbols(CATALOG), {"TWSE": {"2308", "2344"}, "TPEX": {"6488"}})
        result = self.prepare()
        self.assertEqual(result["sessionDate"], "2026-11-19")
        self.assertEqual(result["basis"], BASIS)
        self.assertEqual(result["quotes"]["TWSE:2308"]["close"], 1000)
        self.assertEqual(result["quotes"]["TWSE:2344"]["close"], 98)
        self.assertEqual(result["quotes"]["TPEX:6488"]["close"], 490)
        self.assertEqual(result["sources"]["twse"]["sha256"], hashlib.sha256(TWSE).hexdigest())
        self.assertEqual(result["sources"]["tpex"]["matchingListings"], 1)
        for q in result["quotes"].values():
            self.assertEqual(set(q), {"asOf", "close", "currency", "basis", "sourceId"})

    def test_gated_before_close_or_future(self):
        for now in [AFTER.replace(hour=5, minute=29), AFTER - dt.timedelta(days=1), AFTER.replace(tzinfo=None)]:
            with self.subTest(now=now), self.assertRaises(ValueError):
                self.prepare(now=now)
        with self.assertRaises(ValueError):
            self.prepare(day=dt.date(2026, 11, 21), now=AFTER + dt.timedelta(days=3))

    def test_fail_closed_for_stale_mixed_wrong_or_partial(self):
        for twse in [TWSE.replace(b'1151119', b'1151118', 1), TWSE.replace(b'2344', b'2345'),
                     TWSE.replace(b'98.00', b''), TWSE.replace(b'98.00', b'0'),
                     TWSE.replace(b'98.00', b'1e3'), TWSE + TWSE.splitlines(keepends=True)[2],
                     b'<html>Not CSV</html>', TWSE + b'bad,line\r\n']:
            with self.subTest(twse=twse[-35:]), self.assertRaises(ValueError):
                self.prepare(twse=twse)
        with self.assertRaises(ValueError):
            self.prepare(tpex=TPEX.replace(b'1151119', b'1151118'))

    def test_idempotent_and_never_rolls_back_or_silently_revises(self):
        one = self.prepare()
        self.assertFalse(should_update(one, self.prepare(now=AFTER + dt.timedelta(minutes=10))))
        with self.assertRaisesRegex(ValueError, "Same-session"):
            should_update(one, self.prepare(twse=TWSE.replace(b'98.00', b'99.00')))
        with self.assertRaisesRegex(ValueError, "later snapshot"):
            should_update({**one, "sessionDate": "2026-11-20"}, one)
        self.assertTrue(should_update({**one, "sessionDate": "2026-11-18"}, one))

    def test_refuses_unknown_listing_keys_and_dates(self):
        with self.assertRaises(ValueError):
            catalog_symbols([{"symbol": "TWSE:2000"}, {"symbol": "TPEX:XXXX"}])
        with self.assertRaises(ValueError):
            roc_date("20261119")
        with self.assertRaises(ValueError):
            extract("TWSE", TWSE.splitlines()[0], {"2344"}, DAY)


if __name__ == "__main__":
    unittest.main()
