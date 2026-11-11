import os, sys, unittest
from datetime import datetime, timedelta
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "runner"))
from strategy import ET
import backtest_sip as bs


def daily(closes, opens=None, vol=2_000_000):
    t0 = datetime(2026, 1, 1, 16, tzinfo=ET)
    opens = opens or closes
    return [{"t": t0 + timedelta(days=i), "o": o, "h": max(o, c), "l": min(o, c), "c": c, "v": vol}
            for i, (o, c) in enumerate(zip(opens, closes))]


class Selection(unittest.TestCase):
    def test_gap_uses_only_prior_data(self):
        closes = [10.0] * 15 + [11.0]
        opens = [10.0] * 15 + [10.5]           # day 15 opens +5 % over prev close 10
        g = bs.gappers({"AAA": daily(closes, opens)})
        (d, rows), = g.items()
        self.assertEqual(rows[0][0], "AAA")
        self.assertAlmostEqual(rows[0][1], 5.0)

    def test_filters_cheap_and_illiquid(self):
        opens = [4.0] * 15 + [4.4]
        self.assertEqual(bs.gappers({"CHP": daily([4.0] * 16, opens)}), {})
        self.assertEqual(bs.gappers({"ILQ": daily([10.0] * 16, [10.0] * 15 + [11.0], vol=10_000)}), {})

    def test_in_play_ranks_by_relative_volume(self):
        t = datetime(2026, 3, 2, 9, 30, tzinfo=ET)
        bar = lambda m, v: {"t": t + timedelta(minutes=m), "o": 1, "h": 1, "l": 1, "c": 1, "v": v}
        intraday = {"LO": [bar(m, 1000) for m in (0, 5, 10)], "HI": [bar(m, 90000) for m in (0, 5, 10)]}
        self.assertEqual(bs.in_play(intraday, [("LO", 3, 1e6), ("HI", 2, 1e6)]), ["HI", "LO"])


if __name__ == "__main__":
    unittest.main()
