import json
import os
import sys
import unittest
from datetime import datetime, timedelta

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, "..", "runner"))
from strategy import ET, find_trigger, simulate, size  # noqa: E402
import backtest  # noqa: E402

CFG = json.load(open(os.path.join(HERE, "..", "config.json")))


def day(closes, start=100.0):
    """Synthetic 5-min bars from 09:30; each bar spans prev close -> close (+-0.05)."""
    t0 = datetime(2026, 10, 19, 9, 30, tzinfo=ET)
    out, prev = [], start
    for i, c in enumerate(closes):
        out.append({"t": t0 + timedelta(minutes=5 * i), "o": prev, "h": max(prev, c) + 0.05,
                    "l": min(prev, c) - 0.05, "c": c, "v": 1000})
        prev = c
    return out


class Strategy(unittest.TestCase):
    def test_trigger_is_first_close_above_range(self):
        bars = day([100.5, 99.8, 100.2, 100.4, 101.0, 101.5])  # range 99.75-100.55
        t = find_trigger(bars, CFG)
        self.assertEqual(t["index"], 4)
        self.assertAlmostEqual(t["stop"], round((100.55 + 99.75) / 2, 2))

    def test_no_trigger_inside_range_bars(self):
        self.assertIsNone(find_trigger(day([100.5, 99.8, 100.2] + [100.0] * 60), CFG))

    def test_stop_wins_when_bar_hits_both(self):
        bars = day([100.5, 99.8, 100.2, 101.0, 101.0])
        bars.append({"t": bars[-1]["t"] + timedelta(minutes=5), "o": 101.0, "h": 110, "l": 90, "c": 100, "v": 1})
        trig = find_trigger(bars, CFG)
        self.assertEqual(simulate(bars, trig, CFG)["why"], "stop")

    def test_costs_make_net_below_gross(self):
        bars = day([100.5, 99.8, 100.2, 101.0] + [101.2] * 60)
        tr = simulate(bars, find_trigger(bars, CFG), CFG)
        self.assertLess(tr["net"], tr["gross"])

    def test_size_respects_max_loss_and_order_cap(self):
        self.assertEqual(size(100, 99, CFG), 40)       # $50 / $1 = 50, capped at $4000 -> 40
        self.assertEqual(size(100, 95, CFG), 10)       # $50 / $5

    def test_matches_skill_on_tsla_fixture(self):
        # The skill reports 33 fires on the 59 sessions before 2026-10-19 (+ that day).
        data = backtest.load_yahoo(os.path.join(HERE, "fixtures", "TSLA-60d5m.json.gz"))
        trades, signals, _ = backtest.run(data, CFG)
        self.assertEqual(signals, 34)


if __name__ == "__main__":
    unittest.main()
