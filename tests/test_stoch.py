import os, sys, unittest
from datetime import datetime, timedelta
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "runner"))
from strategy import ET
import stoch


def session(prices, spread=0.02):
    """1-min bars 09:30-16:00 following `prices` (padded flat at the last price)."""
    t0 = datetime(2024, 3, 5, 9, 30, tzinfo=ET)
    p = list(prices) + [prices[-1]] * (390 - len(prices))
    out, prev = [], p[0]
    for k, c in enumerate(p):
        o = prev
        out.append({"t": t0 + timedelta(minutes=k), "o": o, "h": max(o, c) + spread,
                    "l": min(o, c) - spread, "c": c})
        prev = c
    return out


def dip_then(after):
    """Fall from 100 to 99 over 20 bars, then rebound path `after`."""
    return [100 - 0.05 * k for k in range(21)] + after


class Stoch(unittest.TestCase):
    def test_k_uses_only_past_bars(self):
        s = session([100 + 0.01 * k for k in range(60)])
        k1 = stoch.stoch_k(s[:40], 14)
        k2 = stoch.stoch_k(s, 14)
        self.assertEqual(k1, k2[:40])
        self.assertIsNone(k2[12])
        self.assertIsNotNone(k2[13])

    def test_signal_levels(self):
        self.assertEqual(stoch.signal(20, 35), "long")
        self.assertEqual(stoch.signal(80, 65), "short")
        self.assertIsNone(stoch.signal(35, 40))
        self.assertIsNone(stoch.signal(None, 40))

    def test_long_hits_target_entry_next_open(self):
        up = [99 + 0.1 * k for k in range(1, 15)]
        tr, why = stoch.day_trades(session(dip_then(up)), "QQQ")
        self.assertIsNone(why)
        t = tr[0]
        self.assertEqual((t["side"], t["why"]), ("long", "target"))
        self.assertGreater(t["t_in"], "09:50")
        self.assertAlmostEqual(t["exit"], round(t["entry"] * 1.005, 2), places=2)
        self.assertAlmostEqual(t["gross_r"], 0.5 / 0.3, places=3)
        self.assertLess(t["r"], t["gross_r"])  # costs deducted

    def test_long_stopped(self):
        path = [99.0, 99.2, 99.4, 99.45, 99.3, 98.9, 98.5, 98.2]
        tr, _ = stoch.day_trades(session(dip_then(path)), "QQQ")
        t = tr[0]
        self.assertEqual((t["side"], t["why"]), ("long", "stop"))
        self.assertAlmostEqual(t["gross_r"], -1.0, places=2)

    def test_stop_wins_when_bar_hits_both(self):
        s = session([100.0] * 30)
        s[20] = {**s[20], "o": 100.0, "h": 101.0, "l": 99.0}
        (px, why), j = stoch.run_trade(s, 20, "long")
        self.assertEqual((why, j), ("stop", 20))
        self.assertAlmostEqual(px, 99.7)

    def test_flat_at_1555(self):
        s = session([100.0] * 390)
        (px, why), j = stoch.run_trade(s, 300, "short")
        self.assertEqual(why, "close")
        self.assertEqual(s[j]["t"].strftime("%H:%M"), "15:55")

    def test_flat_market_no_signal(self):
        s = session([100.0] * 390)
        tr, _ = stoch.day_trades(s, "QQQ")
        self.assertEqual(tr, [])  # flat market: %K pinned at 50 -> no signal


if __name__ == "__main__":
    unittest.main()
