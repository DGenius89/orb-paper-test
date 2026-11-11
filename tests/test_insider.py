import os, sys, unittest
from datetime import date, timedelta
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "runner"))
import insider as ins


def b(owner, filed, trans=None, cik="1", sym="ABC"):
    return {"filed": filed, "trans": trans or filed, "cik": cik, "sym": sym, "owner": owner, "value": 1e5}


def series(start, n, f):
    d, out, i = start, {}, 0
    while i < n:
        if d.weekday() < 5:
            out[d] = f(i)
            i += 1
        d += timedelta(days=1)
    return out


class Insider(unittest.TestCase):
    def test_cluster_needs_two_distinct_insiders(self):
        d = date(2020, 3, 2)
        self.assertEqual(ins.clusters([b("A", d), b("A", d + timedelta(5))], d, d + timedelta(99)), [])
        s = ins.clusters([b("A", d), b("B", d + timedelta(5))], d, d + timedelta(99))
        self.assertEqual([x["filed"] for x in s], [d + timedelta(5)])

    def test_cooldown_and_window(self):
        d = date(2020, 3, 2)
        buys = [b("A", d), b("B", d + timedelta(2)), b("C", d + timedelta(10)), b("D", d + timedelta(40))]
        s = ins.clusters(buys, d, d + timedelta(400))
        self.assertEqual(len(s), 1)                               # cooldown blocks the rest
        far = [b("A", d), b("B", d + timedelta(45))]
        self.assertEqual(ins.clusters(far, d, d + timedelta(400)), [])  # outside 30 days

    def test_trade_enters_next_open_and_costs(self):
        start = date(2020, 1, 1)
        px = {"ABC": series(start, 200, lambda i: (10.0, 10.0, 1e6)),
              "SPY": series(start, 200, lambda i: (100.0, 100.0, 1e6))}
        days = sorted(px["ABC"])
        t, why = ins.trade({"filed": days[30], "sym": "ABC", "insiders": 2}, px, None, None)
        self.assertEqual(t["entry"], days[31].isoformat())
        self.assertEqual(t["held"], 63)
        self.assertLess(t["net"], 0)                               # flat price, costs only
        self.assertAlmostEqual(t["excess"], t["net"], places=6)

    def test_filters_penny_stocks(self):
        start = date(2020, 1, 1)
        px = {"ABC": series(start, 200, lambda i: (2.0, 2.0, 1e7)), "SPY": series(start, 200, lambda i: (1, 1, 1))}
        t, why = ins.trade({"filed": sorted(px["ABC"])[30], "sym": "ABC", "insiders": 2}, px, None, None)
        self.assertIsNone(t)
        self.assertEqual(why, "te klein/goedkoop")


if __name__ == "__main__":
    unittest.main()
