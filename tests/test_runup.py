import os, sys, unittest
from datetime import date, timedelta
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "runner"))
import runup as ru


def series(start, n, f):
    d, out, i = start, {}, 0
    while i < n:
        if d.weekday() < 5:
            out[d] = f(i)
            i += 1
        d += timedelta(days=1)
    return out


class Runup(unittest.TestCase):
    def test_names_match_across_fda_and_sec_styles(self):
        self.assertEqual(ru.norm("VERTEX PHARMS INC"), ru.norm("VERTEX PHARMACEUTICALS INC / MA"))
        self.assertEqual(ru.norm("Axsome Therap Inc"), ru.norm("Axsome Therapeutics, Inc."))

    def test_match_exact_and_unique_prefix(self):
        exact, first2 = {"vertex pharmaceuticals": "VRTX"}, {"acme bio": {"ACME"}}
        hit, miss = ru.match([{"sponsor": "VERTEX PHARMS", "date": date(2020, 1, 1)},
                              {"sponsor": "ACME BIO SCIENCES", "date": date(2020, 1, 1)},
                              {"sponsor": "NOBODY LLC", "date": date(2020, 1, 1)}], exact, first2)
        self.assertEqual([h["sym"] for h in hit], ["VRTX", "ACME"])
        self.assertIn("NOBODY LLC", miss)

    def test_trade_window_ends_day_before_decision(self):
        start = date(2019, 1, 1)
        px = {s: series(start, 300, lambda i: (10 + i * 0.01, 10 + i * 0.01, 1e6)) for s in ("ABC", "XBI", "SPY")}
        days = sorted(px["ABC"])
        t, _ = ru.trade({"date": days[200], "sym": "ABC", "kind": "approval", "sponsor": "x"}, px)
        self.assertEqual(t["entry"], days[170].isoformat())
        self.assertEqual(t["exit"], days[199].isoformat())
        self.assertAlmostEqual(t["ex_xbi"], t["net"] - t["xbi"], places=5)

    def test_big_pharma_filtered_by_dollar_volume(self):
        start = date(2019, 1, 1)
        px = {s: series(start, 300, lambda i: (100.0, 100.0, 1e8)) for s in ("BIG", "XBI", "SPY")}
        t, why = ru.trade({"date": sorted(px["BIG"])[200], "sym": "BIG", "kind": "approval", "sponsor": "x"}, px)
        self.assertIsNone(t)
        self.assertEqual(why, "te klein of te groot")


if __name__ == "__main__":
    unittest.main()
