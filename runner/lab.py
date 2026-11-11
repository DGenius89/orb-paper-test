"""Strategy lab: five pre-registered low-frequency ETF ideas (lab/IDEAS.md).

  python runner/lab.py dev                      # 2017 .. HOLDOUT_START, hold-out data never loaded
  python runner/lab.py final --ideas a,b        # ONE shot on the hold-out; refuses to run twice

Signals on day t's close, executed at day t+1's open, 5 bps per side on traded value.
"""
import argparse
import json
import math
import os
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(__file__))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LAB = os.path.join(ROOT, "lab")
DATA_START = date(2016, 1, 4)
DEV_START = date(2017, 1, 3)
HOLDOUT_START = date(2025, 11, 11)
COST_BPS = 5
SECTORS = ["XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY", "XLRE", "XLC"]
MULTI = ["SPY", "EFA", "EEM", "IEF", "TLT", "GLD", "DBC", "VNQ"]
SYMBOLS = sorted(set(["SPY", "EFA", "BIL", "AGG"] + SECTORS + MULTI))


# ---------- helpers on a per-symbol close history (list, oldest first, up to today) ----------
def ret(c, n, skip=0):
    if len(c) <= n:
        return None
    return c[-1 - skip] / c[-1 - n] - 1


def sma(c, n):
    return sum(c[-n:]) / n if len(c) >= n else None


def vol(c, n):
    if len(c) <= n:
        return None
    r = [c[i] / c[i - 1] - 1 for i in range(len(c) - n, len(c))]
    m = sum(r) / n
    return math.sqrt(sum((x - m) ** 2 for x in r) / (n - 1))


def rsi(c, n=2):
    if len(c) <= n:
        return None
    gains = [max(c[i] - c[i - 1], 0) for i in range(len(c) - n, len(c))]
    losses = [max(c[i - 1] - c[i], 0) for i in range(len(c) - n, len(c))]
    g, l = sum(gains) / n, sum(losses) / n
    return 100.0 if l == 0 else 100 - 100 / (1 + g / l)


# ---------- the five ideas: f(hist, month_end, state) -> weights dict or None (no change) ----------
def trend_spy(h, month_end, st):
    if not month_end:
        return None
    s = h["SPY"]
    return {"SPY": 1.0} if s[-1] > sma(s, 200) else {"BIL": 1.0}


def dual_momentum(h, month_end, st):
    if not month_end:
        return None
    best = max(["SPY", "EFA"], key=lambda x: ret(h[x], 252))
    return {best: 1.0} if ret(h[best], 252) > ret(h["BIL"], 252) else {"AGG": 1.0}


def sector_momentum(h, month_end, st):
    if not month_end:
        return None
    if h["SPY"][-1] < sma(h["SPY"], 200):
        return {"BIL": 1.0}
    ok = [s for s in SECTORS if len(h.get(s, [])) > 252]
    top = sorted(ok, key=lambda s: ret(h[s], 252, skip=21), reverse=True)[:3]
    return {s: 1 / len(top) for s in top}


def tsmom_multi(h, month_end, st):
    if not month_end:
        return None
    pos = [s for s in MULTI if len(h.get(s, [])) > 252 and ret(h[s], 252) > 0]
    if not pos:
        return {"BIL": 1.0}
    inv = {s: 1 / vol(h[s], 63) for s in pos}
    tot = sum(inv.values())
    return {s: w / tot for s, w in inv.items()}


def rsi2_spy(h, month_end, st):
    s = h["SPY"]
    if not st.get("long"):
        if s[-1] > sma(s, 200) and rsi(s, 2) < 10:
            st["long"] = True
            return {"SPY": 1.0}
        return None if st.get("init") else (st.update(init=True) or {"BIL": 1.0})
    if s[-1] > sma(s, 5):
        st["long"] = False
        return {"BIL": 1.0}
    return None


def buy_hold_spy(h, month_end, st):
    if st.get("done"):
        return None
    st["done"] = True
    return {"SPY": 1.0}


IDEAS = {f.__name__: f for f in (trend_spy, dual_momentum, sector_momentum, tsmom_multi, rsi2_spy)}


# ---------- simulator ----------
def simulate(data, idea, start):
    """data: {sym: {date: (open, close)}}. Returns [(date, equity)] from `start` on."""
    cal = sorted(data["SPY"])
    hist = {s: [] for s in data}
    units, cash, eq = {}, 1.0, []
    pending, st, turnover = None, {}, 0.0
    for i, d in enumerate(cal):
        # 1. execute yesterday's signal at today's open
        if pending is not None and d >= start:
            px = {s: data[s][d][0] for s in set(units) | set(pending) if d in data[s]}
            if all(s in px for s in pending):
                val = cash + sum(u * px[s] for s, u in units.items() if s in px)
                cur = {s: units.get(s, 0) * px[s] for s in px}
                tgt = {s: pending.get(s, 0) * val for s in px}
                traded = sum(abs(tgt[s] - cur.get(s, 0)) for s in px)
                cost = traded * COST_BPS / 10000
                val -= cost
                turnover += traded
                units = {s: pending[s] * val / px[s] for s in pending}
                cash = 0.0
            pending = None
        # 2. mark to market on the close
        for s in data:
            if d in data[s]:
                hist[s].append(data[s][d][1])
        if d >= start:
            val = cash + sum(u * data[s][d][1] for s, u in units.items() if d in data[s])
            eq.append((d, val))
        # 3. signal on today's close (needs 253 days of SPY history)
        nxt = cal[i + 1] if i + 1 < len(cal) else None
        if len(hist["SPY"]) > 252 and nxt is not None and nxt >= start:
            month_end = nxt is None or nxt.month != d.month or not st.get("_started")
            st["_started"] = True
            w = idea({s: c for s, c in hist.items() if c}, month_end, st)
            if w is not None:
                pending = w
    return eq, turnover


def metrics(eq, frm, to):
    e = [(d, v) for d, v in eq if frm <= d < to and v > 0]
    if len(e) < 20:
        return None
    vals = [v for _, v in e]
    r = [vals[i] / vals[i - 1] - 1 for i in range(1, len(vals))]
    m = sum(r) / len(r)
    sd = math.sqrt(sum((x - m) ** 2 for x in r) / (len(r) - 1))
    peak, dd = vals[0], 0.0
    for v in vals:
        peak = max(peak, v)
        dd = max(dd, 1 - v / peak)
    yrs = len(r) / 252
    return {"from": e[0][0].isoformat(), "to": e[-1][0].isoformat(),
            "total_return_pct": round((vals[-1] / vals[0] - 1) * 100, 2),
            "cagr_pct": round(((vals[-1] / vals[0]) ** (1 / yrs) - 1) * 100, 2),
            "vol_pct": round(sd * math.sqrt(252) * 100, 2),
            "sharpe": round(m / sd * math.sqrt(252), 2) if sd else None,
            "max_drawdown_pct": round(dd * 100, 2)}


def load(end):
    import alpaca
    raw = {}
    for i in range(0, len(SYMBOLS), 10):
        got = alpaca.bars(SYMBOLS[i:i + 10], DATA_START.isoformat() + "T00:00:00Z",
                          end.isoformat() + "T00:00:00Z", timeframe="1Day", feed="sip", adjustment="all")
        raw.update(got)
    return {s: {b["t"].date(): (b["o"], b["c"]) for b in bars if b["t"].date() < end} for s, bars in raw.items()}


def run_all(data, names, frm, to):
    out = {}
    for name in ["buy_hold_spy"] + names:
        f = buy_hold_spy if name == "buy_hold_spy" else IDEAS[name]
        eq, turnover = simulate(data, f, DEV_START)
        m = metrics(eq, frm, to)
        if m:
            m["turnover_x_per_year"] = round(turnover / max(1, len(eq) / 252), 2)
        out[name] = m
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["dev", "final"])
    ap.add_argument("--ideas", default="")
    a = ap.parse_args(argv)
    os.makedirs(LAB, exist_ok=True)

    if a.mode == "dev":
        data = load(HOLDOUT_START)  # hold-out data is never fetched in dev
        res = run_all(data, list(IDEAS), DEV_START, HOLDOUT_START)
        spy = res["buy_hold_spy"]
        passed = [n for n in IDEAS if res[n] and res[n]["sharpe"] > spy["sharpe"]
                  and res[n]["max_drawdown_pct"] < spy["max_drawdown_pct"]]
        passed = sorted(passed, key=lambda n: -res[n]["sharpe"])[:2]
        out = {"period": [DEV_START.isoformat(), HOLDOUT_START.isoformat()], "results": res,
               "to_final": passed}
        path = os.path.join(LAB, "dev.json")
    else:
        path = os.path.join(LAB, "final.json")
        if os.path.exists(path):
            raise SystemExit("De eindtoets is al gedaan. Eén keer = één keer (zie lab/IDEAS.md).")
        dev = json.load(open(os.path.join(LAB, "dev.json")))
        names = [n for n in a.ideas.split(",") if n]
        if not names or any(n not in dev["to_final"] for n in names):
            raise SystemExit(f"Alleen ideeën die de dev-fase haalden mogen: {dev['to_final']}")
        data = load(date.today() + timedelta(days=1))
        res = run_all(data, names, HOLDOUT_START, date.today() + timedelta(days=1))
        spy = res["buy_hold_spy"]
        verdict = {n: "PASS" if res[n]["total_return_pct"] > 0
                   and res[n]["max_drawdown_pct"] <= spy["max_drawdown_pct"] else "FAIL" for n in names}
        out = {"holdout_from": HOLDOUT_START.isoformat(), "results": res, "verdict": verdict}
    json.dump(out, open(path, "w"), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
