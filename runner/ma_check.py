"""Informatief (NIET vooraf vastgelegd): moving-average crossovers op SPY vs simpelweg
minder aandelen. Alleen ontwikkelperiode; de hold-out blijft dicht."""
import json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
import lab
from lab import sma


def cross(fast, slow):
    def f(h, month_end, st):
        s = h["SPY"]
        want = "SPY" if sma(s, fast) > sma(s, slow) else "BIL"
        if st.get("in") != want:
            st["in"] = want
            return {want: 1.0}
        return None
    f.__name__ = f"ma_{fast}_{slow}"
    return f


def mix(w):
    def f(h, month_end, st):
        return {"SPY": w, "BIL": 1 - w} if month_end else None
    f.__name__ = f"spy_{int(w*100)}_cash_{int(100-w*100)}"
    return f


data = lab.load(lab.HOLDOUT_START)
out = {}
for f in [lab.buy_hold_spy, cross(20, 50), cross(50, 200), lab.trend_spy, mix(0.6), mix(0.75)]:
    eq, turn = lab.simulate(data, f, lab.DEV_START)
    m = lab.metrics(eq, lab.DEV_START, lab.HOLDOUT_START)
    m["switches_per_year"] = round(turn / 2 / max(1, len(eq) / 252), 1)
    out[f.__name__] = m
json.dump(out, open(os.path.join(lab.LAB, "ma-check.json"), "w"), indent=1)
print(json.dumps(out, indent=1))
