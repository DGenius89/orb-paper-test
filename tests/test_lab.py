import os, random, sys, unittest
from datetime import date, timedelta
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "runner"))
import lab


def fake(days=900, seed=1):
    rnd = random.Random(seed)
    cal, d = [], date(2016, 1, 4)
    while len(cal) < days:
        if d.weekday() < 5:
            cal.append(d)
        d += timedelta(days=1)
    data = {}
    for s in lab.SYMBOLS:
        px, rows = 100.0, {}
        for x in cal:
            o = px * (1 + rnd.gauss(0, 0.002))
            px = o * (1 + rnd.gauss(0.0003, 0.01))
            rows[x] = (o, px)
        data[s] = rows
    return data, cal


class Lab(unittest.TestCase):
    def test_all_ideas_run_and_buy_hold_matches_spy(self):
        data, cal = fake()
        res = lab.run_all(data, list(lab.IDEAS), lab.DEV_START, cal[-1] + timedelta(days=1))
        for n, m in res.items():
            self.assertIsNotNone(m, n)
        # buy & hold: bought at the open after the first signal, so compare from that open
        eq, _ = lab.simulate(data, lab.buy_hold_spy, lab.DEV_START)
        first_inv = next(i for i, (_, v) in enumerate(eq) if v != 1.0)
        d0, v0 = eq[first_inv]
        self.assertAlmostEqual(eq[-1][1] / v0, data["SPY"][cal[-1]][1] / data["SPY"][d0][1], places=6)

    def test_no_lookahead_signal_executes_next_open(self):
        data, cal = fake()
        seen = []
        def spy_on_last_close(h, me, st):
            seen.append(h["SPY"][-1])
            return None
        lab.simulate(data, spy_on_last_close, lab.DEV_START)
        i = len(cal) - 1 - len(seen)  # last day has no next open, so no call
        self.assertEqual(seen[0], data["SPY"][cal[i]][1])  # only closes up to that day

    def test_costs_charged(self):
        data, cal = fake()
        flip = lambda h, me, st: {"SPY": 1.0} if len(h["SPY"]) % 2 else {"BIL": 1.0}
        _, turnover = lab.simulate(data, flip, lab.DEV_START)
        self.assertGreater(turnover, 100)


if __name__ == "__main__":
    unittest.main()
