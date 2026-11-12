import os, sys, unittest
from datetime import datetime, timedelta
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "runner"))
from strategy import ET
import silver
import trap


def bar(t, o, h, l, c):
    return {"t": t, "o": o, "h": h, "l": l, "c": c}


def make_day(sweep=True, retest=True, hit_target=True):
    """5-min session. Morning range 09:30-10:00 = 100.0-101.0; at 10:05 sweep to 99.6;
    gap 10:10-10:20 (c1 high 100.1, c3 low 100.5 -> mid 100.3); retest 10:30; then run."""
    t0 = datetime(2024, 3, 5, 9, 30, tzinfo=ET)
    m = lambda k: t0 + timedelta(minutes=5 * k)
    out = [bar(m(0), 100.5, 101.0, 100.0, 100.5)] + [bar(m(k), 100.5, 100.8, 100.2, 100.5) for k in range(1, 6)]
    out.append(bar(m(6), 100.5, 100.6, 99.6 if sweep else 100.1, 99.9))   # 10:00 sweep bar
    out.append(bar(m(7), 99.9, 100.1, 99.7 if sweep else 100.15, 100.0))  # 10:05 candle 1 (high 100.1)
    out.append(bar(m(8), 100.0, 100.7, 99.95 if sweep else 100.2, 100.65))  # 10:10 candle 2
    out.append(bar(m(9), 100.65, 100.9, 100.5, 100.8))                    # 10:15 candle 3: gap 100.1-100.5
    out.append(bar(m(10), 100.8, 100.85, 100.6, 100.7))
    out.append(bar(m(11), 100.7, 100.7, 100.25 if retest else 100.6, 100.4))   # 10:25 retest mid 100.3
    end = 101.3 if hit_target else 99.4
    for k in range(12, 78):
        p = 100.4 + (end - 100.4) * min(1, (k - 11) / 10)
        out.append(bar(m(k), p, p + 0.03, p - 0.03, p))
    return out


NY = silver.WINDOWS[0]


class Silver(unittest.TestCase):
    def test_long_setup_mid_gap_entry_hits_target(self):
        t, why = silver.window_trade(make_day(), "SPY", *NY)
        self.assertIsNone(why)
        self.assertEqual((t["side"], t["why"]), ("long", "target"))
        self.assertAlmostEqual(t["entry"], 100.3)
        self.assertAlmostEqual(t["stop"], 99.59)
        self.assertAlmostEqual(t["target"], 101.0)
        self.assertGreater(t["r"], 0.9)

    def test_stop(self):
        t, _ = silver.window_trade(make_day(hit_target=False), "SPY", *NY)
        self.assertEqual(t["why"], "stop")
        self.assertAlmostEqual(t["r"], -1.0, delta=0.05)

    def test_no_sweep_no_trade(self):
        t, why = silver.window_trade(make_day(sweep=False), "SPY", *NY)
        self.assertIsNone(t)

    def test_no_retest_no_trade(self):
        self.assertEqual(silver.window_trade(make_day(retest=False), "SPY", *NY)[1], "gap niet teruggetest")

    def test_short_is_mirror(self):
        t, why = silver.window_trade(trap.flip(make_day()), "SPY", *NY)
        self.assertIsNone(why)
        self.assertEqual((t["side"], t["why"]), ("short", "target"))
        self.assertGreater(t["r"], 0.9)

    def test_pm_window_ignores_morning_setup(self):
        t, why = silver.window_trade(make_day(), "SPY", *silver.WINDOWS[1])
        self.assertIsNone(t)


if __name__ == "__main__":
    unittest.main()
