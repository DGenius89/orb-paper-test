"""ICT Silver Bullet (lab/SILVER.md).

  python runner/silver.py dev
  python runner/silver.py final     # ONE shot on the hold-out, only after a dev PASS
"""
import argparse
import csv
import json
import os
import sys
from collections import defaultdict
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(__file__))
from trap import between, flip, mins, months, stats  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LAB = os.path.join(ROOT, "lab")
SYMBOLS = ["SPY", "QQQ"]
DEV_START, DEV_END, HOLDOUT_START = date(2018, 1, 1), date(2024, 12, 31), date(2025, 1, 1)
R = {"cost_bps": 1.0, "risk_pct": 1.0, "max_leverage": 4.0}
# (name, window start, window end, reference start, reference end) in minutes after midnight ET
WINDOWS = [("NY", 600, 660, 570, 600), ("PM", 840, 900, 720, 840)]


def long_setup(s, ref_lo, ref_hi, w0, w1):
    """s: regular-session 5-min bars (prices possibly mirrored). Returns dict or skip reason."""
    win = [i for i, b in enumerate(s) if between(b, w0, w1)]
    if len(win) < 8:
        return "geen data"
    swept, sweep_low, gap = None, None, None
    for i in win:
        if s[i]["l"] < ref_lo:
            sweep_low = s[i]["l"] if sweep_low is None else min(sweep_low, s[i]["l"])
            swept = i if swept is None else swept
        if swept is not None and i - 2 >= swept and s[i]["l"] > s[i - 2]["h"]:
            gap = i
            break
    if swept is None:
        return "geen sweep"
    if gap is None:
        return "sweep zonder gap"
    if s[gap]["c"] <= ref_lo:
        return "eerste gap niet terug boven range"
    entry = (s[gap - 2]["h"] + s[gap]["l"]) / 2
    stop = round(sweep_low - 0.01, 2)
    target = ref_hi
    if not target > entry > stop:
        return "doel niet boven instap"
    fill = None
    for k in range(gap + 1, len(s)):
        if mins(s[k]["t"]) >= w1:
            break
        if s[k]["l"] <= entry:
            fill = k
            break
    if fill is None:
        return "gap niet teruggetest"
    base = {"entry": min(entry, s[fill]["o"]), "stop": stop, "target": target,
            "t_gap": s[gap]["t"], "t_in": s[fill]["t"]}
    if s[fill]["l"] <= stop:
        return {**base, "exit": min(stop, s[fill]["o"]), "why": "stop", "t_out": s[fill]["t"]}
    for b in s[fill + 1:]:
        if mins(b["t"]) >= 15 * 60 + 55:
            return {**base, "exit": b["o"], "why": "close", "t_out": b["t"]}
        if b["l"] <= stop:
            return {**base, "exit": min(stop, b["o"]), "why": "stop", "t_out": b["t"]}
        if b["h"] >= target:
            return {**base, "exit": max(target, b["o"]), "why": "target", "t_out": b["t"]}
    return {**base, "exit": s[-1]["c"], "why": "close", "t_out": s[-1]["t"]}


def window_trade(day, sym, name, w0, w1, r0, r1):
    s = [b for b in day if 570 <= mins(b["t"]) < 960]
    ref = [b for b in s if between(b, r0, r1)]
    if len(ref) < (r1 - r0) // 5 - 1:
        return None, "geen data"
    lo, hi = min(b["l"] for b in ref), max(b["h"] for b in ref)
    up = long_setup(s, lo, hi, w0, w1)
    dn = long_setup(flip(s), -hi, -lo, w0, w1)
    cands = [(x, side) for x, side in ((up, "long"), (dn, "short")) if isinstance(x, dict)]
    if not cands:
        return None, up if up != "geen sweep" else dn
    res, side = min(cands, key=lambda c: c[0]["t_gap"])
    risk = res["entry"] - res["stop"]
    cost = abs(res["entry"]) * R["cost_bps"] / 10000 * 2
    r = (res["exit"] - res["entry"] - cost) / risk
    sign = 1 if side == "long" else -1
    risk_frac = min(R["risk_pct"] / 100, R["max_leverage"] * risk / abs(res["entry"]))
    return {"date": res["t_in"].date().isoformat(), "sym": sym, "window": name, "side": side,
            "t_in": res["t_in"].strftime("%H:%M"), "t_out": res["t_out"].strftime("%H:%M"),
            "entry": round(sign * res["entry"], 2), "stop": round(sign * res["stop"], 2),
            "target": round(sign * res["target"], 2), "exit": round(sign * res["exit"], 2),
            "why": res["why"], "planned_rr": round((res["target"] - res["entry"]) / risk, 2),
            "risk_bp": round(risk / abs(res["entry"]) * 1e4, 1),
            "r": round(r, 4), "ret": round(r * risk_frac, 6)}, None


def main(argv=None):
    import alpaca
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["dev", "final"])
    a = ap.parse_args(argv)
    if a.mode == "dev":
        frm, to = DEV_START, DEV_END
        path = os.path.join(LAB, "silver-dev.json")
    else:
        path = os.path.join(LAB, "silver-final.json")
        if os.path.exists(path):
            sys.exit("De eindtoets is al gedaan. Eén keer = één keer.")
        if json.load(open(os.path.join(LAB, "silver-dev.json"))).get("verdict") != "PASS":
            sys.exit("Dev-fase niet gehaald: geen eindtoets (lab/SILVER.md).")
        frm, to = HOLDOUT_START, date.today() - timedelta(days=1)

    trades, skips = [], defaultdict(int)
    for m0, m1 in months(frm, to):
        got = alpaca.bars(SYMBOLS, m0.isoformat() + "T00:00:00Z", m1.isoformat() + "T00:00:00Z",
                          timeframe="5Min", feed="sip")
        for sym, bars in got.items():
            byd = defaultdict(list)
            for b in bars:
                byd[b["t"].date()].append(b)
            for d, day in byd.items():
                if not frm <= d <= to:
                    continue
                day = sorted(day, key=lambda x: x["t"])
                for w in WINDOWS:
                    t, why = window_trade(day, sym, *w)
                    if t:
                        trades.append(t)
                    else:
                        skips[f"{w[0]}: {why}"] += 1
        print(f"  {m0:%Y-%m}: {len(trades)} trades", file=sys.stderr)

    res = {"mode": a.mode, "period": [frm.isoformat(), to.isoformat()], "rules": R,
           "skipped": dict(skips), "all": stats(trades),
           "by_window": {w[0]: stats([t for t in trades if t["window"] == w[0]]) for w in WINDOWS},
           "by_side": {s: stats([t for t in trades if t["side"] == s]) for s in ("long", "short")},
           "by_year": {y: stats([t for t in trades if t["date"].startswith(str(y))])
                       for y in range(frm.year, to.year + 1)}}
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
