"""The "10 AM trap" (lab/TRAP.md).

  python runner/trap.py dev
  python runner/trap.py final     # ONE shot on the hold-out, only after a dev PASS
"""
import argparse
import csv
import json
import math
import os
import sys
from collections import defaultdict
from datetime import date, time, timedelta

sys.path.insert(0, os.path.dirname(__file__))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LAB = os.path.join(ROOT, "lab")
SYMBOLS = ["SPY", "QQQ"]
DEV_START, DEV_END, HOLDOUT_START = date(2018, 1, 1), date(2024, 12, 31), date(2025, 1, 1)
R = {"cost_bps": 1.0, "risk_pct": 1.0, "max_leverage": 4.0}


def mins(t):
    return t.hour * 60 + t.minute


def between(b, a, z):
    return a <= mins(b["t"]) < z


def flip(bars):
    """Mirror prices so a short setup becomes a long one (R is unchanged)."""
    return [{"t": b["t"], "o": -b["o"], "h": -b["l"], "l": -b["h"], "c": -b["c"]} for b in bars]


def bias(day):
    four = [b for b in day if between(b, 6 * 60, 10 * 60)]
    if len(four) < 60:
        return None
    o, c = four[0]["o"], four[-1]["c"]
    return "long" if c > o else "short" if c < o else None


def long_setup(day):
    """Find the trap + gap + retrace on a long-bias day. Returns a trade dict or a skip reason."""
    s = [b for b in day if mins(b["t"]) >= 9 * 60 + 30]
    rng = [b for b in s if between(b, 600, 615)]
    if len(rng) < 10:
        return "geen data"
    rl = min(b["l"] for b in rng)
    idx = [i for i, b in enumerate(s) if between(b, 615, 690)]
    if not idx:
        return "geen data"
    trap_low, trapped_at = None, None
    gap = None
    for i in idx:
        b = s[i]
        if b["l"] < rl:
            trap_low = b["l"] if trap_low is None else min(trap_low, b["l"])
            trapped_at = trapped_at if trapped_at is not None else i
        if trapped_at is not None and i - 2 >= trapped_at:
            if s[i]["l"] > s[i - 2]["h"] and s[i]["c"] > rl:
                gap = i
                break
    if trapped_at is None:
        return "geen trap"
    if gap is None:
        return "trap zonder gap"
    entry = s[gap]["l"]
    stop = round(trap_low - 0.01, 2)
    target = max(b["h"] for b in s[:gap + 1])
    if target <= entry or entry <= stop:
        return "doel niet boven instap"
    # entry: limit, valid until 12:00
    fill = None
    for k in range(gap + 1, len(s)):
        b = s[k]
        if mins(b["t"]) >= 720:
            break
        if b["l"] <= entry:
            fill = k
            break
    if fill is None:
        return "gap niet teruggetest"
    px_in = min(entry, s[fill]["o"])
    if s[fill]["l"] <= stop:
        return {"entry": px_in, "stop": stop, "target": target, "exit": min(stop, s[fill]["o"]),
                "why": "stop", "t_in": s[fill]["t"], "t_out": s[fill]["t"]}
    for b in s[fill + 1:]:
        if mins(b["t"]) >= 15 * 60 + 55:
            return {"entry": px_in, "stop": stop, "target": target, "exit": b["o"], "why": "close",
                    "t_in": s[fill]["t"], "t_out": b["t"]}
        if b["l"] <= stop:
            return {"entry": px_in, "stop": stop, "target": target, "exit": min(stop, b["o"]), "why": "stop",
                    "t_in": s[fill]["t"], "t_out": b["t"]}
        if b["h"] >= target:
            return {"entry": px_in, "stop": stop, "target": target, "exit": max(target, b["o"]),
                    "why": "target", "t_in": s[fill]["t"], "t_out": b["t"]}
    last = s[-1]
    return {"entry": px_in, "stop": stop, "target": target, "exit": last["c"], "why": "close",
            "t_in": s[fill]["t"], "t_out": last["t"]}


def day_trade(day, sym):
    b = bias(day)
    if b is None:
        return None, "geen bias"
    res = long_setup(day if b == "long" else flip(day))
    if isinstance(res, str):
        return None, res
    risk = res["entry"] - res["stop"]
    cost = abs(res["entry"]) * R["cost_bps"] / 10000 * 2
    r = (res["exit"] - res["entry"] - cost) / risk
    sign = 1 if b == "long" else -1
    planned = (res["target"] - res["entry"]) / risk
    risk_frac = min(R["risk_pct"] / 100, R["max_leverage"] * risk / abs(res["entry"]))
    return {"date": res["t_in"].date().isoformat(), "sym": sym, "side": b,
            "t_in": res["t_in"].strftime("%H:%M"), "t_out": res["t_out"].strftime("%H:%M"),
            "entry": round(sign * res["entry"], 2), "stop": round(sign * res["stop"], 2),
            "target": round(sign * res["target"], 2), "exit": round(sign * res["exit"], 2),
            "why": res["why"], "planned_rr": round(planned, 2), "r": round(r, 4),
            "ret": round(r * risk_frac, 6)}, None


def stats(tr):
    n = len(tr)
    if n < 2:
        return {"trades": n}
    r = [t["r"] for t in tr]
    m = sum(r) / n
    sd = math.sqrt(sum((x - m) ** 2 for x in r) / (n - 1))
    eq, peak, dd = 1.0, 1.0, 0.0
    for t in sorted(tr, key=lambda t: (t["date"], t["t_in"])):
        eq *= 1 + t["ret"]
        peak = max(peak, eq)
        dd = max(dd, 1 - eq / peak)
    why = defaultdict(int)
    for t in tr:
        why[t["why"]] += 1
    return {"trades": n, "mean_r": round(m, 3), "t_stat": round(m / (sd / math.sqrt(n)), 2) if sd else None,
            "win_rate_pct": round(sum(1 for x in r if x > 0) / n * 100, 1),
            "median_planned_rr": sorted(t["planned_rr"] for t in tr)[n // 2],
            "exits": dict(why), "equity_total_return_pct": round((eq - 1) * 100, 1),
            "equity_max_drawdown_pct": round(dd * 100, 1)}


def months(a, b):
    d = date(a.year, a.month, 1)
    while d <= b:
        nxt = date(d.year + (d.month == 12), d.month % 12 + 1, 1)
        yield d, min(nxt, b + timedelta(days=1))
        d = nxt


def main(argv=None):
    import alpaca
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["dev", "final"])
    a = ap.parse_args(argv)
    if a.mode == "dev":
        frm, to = DEV_START, DEV_END
        path = os.path.join(LAB, "trap-dev.json")
    else:
        path = os.path.join(LAB, "trap-final.json")
        if os.path.exists(path):
            sys.exit("De eindtoets is al gedaan. Eén keer = één keer.")
        if json.load(open(os.path.join(LAB, "trap-dev.json"))).get("verdict") != "PASS":
            sys.exit("Dev-fase niet gehaald: geen eindtoets (lab/TRAP.md).")
        frm, to = HOLDOUT_START, date.today() - timedelta(days=1)

    trades, skips, days_seen = [], defaultdict(int), 0
    for m0, m1 in months(frm, to):
        got = alpaca.bars(SYMBOLS, m0.isoformat() + "T00:00:00Z", m1.isoformat() + "T00:00:00Z",
                          timeframe="1Min", feed="sip")
        for sym, bars in got.items():
            byd = defaultdict(list)
            for b in bars:
                byd[b["t"].date()].append(b)
            for d, day in byd.items():
                if not frm <= d <= to:
                    continue
                days_seen += 1
                t, why = day_trade(sorted(day, key=lambda x: x["t"]), sym)
                if t:
                    trades.append(t)
                else:
                    skips[why] += 1
        print(f"  {m0:%Y-%m}: {len(trades)} trades", file=sys.stderr)

    spy = alpaca.bars(["SPY"], frm.isoformat() + "T00:00:00Z", (to + timedelta(days=1)).isoformat() + "T00:00:00Z",
                      timeframe="1Day", feed="sip", adjustment="all")["SPY"]
    res = {"mode": a.mode, "period": [frm.isoformat(), to.isoformat()], "rules": R,
           "symbol_days": days_seen, "skipped": dict(skips), "all": stats(trades),
           "long": stats([t for t in trades if t["side"] == "long"]),
           "short": stats([t for t in trades if t["side"] == "short"]),
           "by_year": {y: stats([t for t in trades if t["date"].startswith(str(y))])
                       for y in range(frm.year, to.year + 1)},
           "spy_buy_hold_pct": round((spy[-1]["c"] / spy[0]["o"] - 1) * 100, 1) if spy else None}
    s = res["all"]
    if a.mode == "dev":
        ok = s.get("trades", 0) >= 100 and s.get("mean_r", 0) > 0 and (s.get("t_stat") or 0) >= 2
    else:
        ok = s.get("mean_r", 0) > 0
    res["verdict"] = "PASS" if ok else "FAIL"
    os.makedirs(LAB, exist_ok=True)
    json.dump(res, open(path, "w"), indent=1, default=str)
    if trades:
        with open(path.replace(".json", "-trades.csv"), "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(trades[0]))
            w.writeheader()
            w.writerows(trades)
    print(json.dumps(res, indent=1, default=str))


if __name__ == "__main__":
    main()
