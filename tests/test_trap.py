import os, sys, unittest
from datetime import datetime, timedelta
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "runner"))
from strategy import ET
import trap


def bar(t, o, h, l, c):
    return {"t": t, "o": o, "h": h, "l": l, "c": c}


def make_day(premarket_up=True, trap_dip=True, retest=True, hit_target=True):
    """06:00-10:00 drift, 09:30 morning high 101, range 100.0-100.5 at 10:00-10:15,
    dip to 99.5 at 10:20, gap up at 10:22-10:24, retest 10:30, then target or stop."""
    t0 = datetime(2024, 3, 5, 6, 0, tzinfo=ET)
    out, px = [], 100.0
    for i in range(240):                                    # 06:00-09:59
        t = t0 + timedelta(minutes=i)
        nxt = px + (0.002 if premarket_up else -0.002)
        if t.hour == 9 and t.minute == 45:
            out.append(bar(t, px, 101.0, px - 0.05, nxt))   # morning high 101
        else:
            out.append(bar(t, px, max(px, nxt) + 0.01, min(px, nxt) - 0.01, nxt))
        px = nxt
    t = t0 + timedelta(hours=4)
    m = lambda k: t + timedelta(minutes=k)
    for k in range(15):                                     # range 10:00-10:14
        out.append(bar(m(k), 100.2, 100.5, 100.0, 100.2))
    for k in range(15, 20):
        out.append(bar(m(k), 100.2, 100.3, 100.05, 100.15))
    low = 99.5 if trap_dip else 100.05
    out.append(bar(m(20), 100.15, 100.2, low, 99.7))        # trap
    lo = (lambda x: x) if trap_dip else (lambda x: max(x, 100.02))
    out.append(bar(m(21), 99.7, 100.1, lo(99.6), 100.0))    # candle 1 high 100.1
    out.append(bar(m(22), 100.0, 100.6, lo(99.95), 100.55)) # candle 2
    out.append(bar(m(23), 100.55, 100.8, 100.3, 100.7))     # candle 3 low 100.3 > 100.1: gap
    for k in range(24, 30):
        out.append(bar(m(k), 100.7, 100.8, 100.6, 100.7))
    out.append(bar(m(30), 100.7, 100.7, 100.25 if retest else 100.6, 100.4))   # retest -> fill at 100.3
    end = 101.2 if hit_target else 99.3
    for k in range(31, 60):
        p = 100.4 + (end - 100.4) * (k - 30) / 29
        out.append(bar(m(k), p, p + 0.05, p - 0.05, p))
    for k in range(60, 360):
        out.append(bar(m(k), end, end, end, end))
    return out


class Trap(unittest.TestCase):
    def test_full_long_setup_hits_target(self):
        t, why = trap.day_trade(make_day(), "SPY")
        self.assertIsNone(why)
        self.assertEqual((t["side"], t["why"]), ("long", "target"))
        self.assertAlmostEqual(t["entry"], 100.3)
        self.assertAlmostEqual(t["stop"], 99.49)
        self.assertAlmostEqual(t["target"], 101.0)
        self.assertGreater(t["r"], 0.8)

    def test_stop_case_loses_about_one_r(self):
        t, _ = trap.day_trade(make_day(hit_target=False), "SPY")
        self.assertEqual(t["why"], "stop")
        self.assertAlmostEqual(t["r"], -1.0, delta=0.05)

    def test_no_trap_no_trade(self):
        self.assertEqual(trap.day_trade(make_day(trap_dip=False), "SPY")[1], "geen trap")

    def test_no_retest_no_trade(self):
        self.assertEqual(trap.day_trade(make_day(retest=False), "SPY")[1], "gap niet teruggetest")

    def test_bearish_bias_mirrors(self):
        day = trap.flip(make_day())                           # perfect mirror: short setup
        t, why = trap.day_trade(day, "SPY")
        self.assertIsNone(why)
        self.assertEqual((t["side"], t["why"]), ("short", "target"))
        self.assertAlmostEqual(t["entry"], -100.3)            # mirrored prices are negative here
        self.assertGreater(t["r"], 0.8)


if __name__ == "__main__":
    unittest.main()
