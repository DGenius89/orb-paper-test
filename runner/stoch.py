"""Stochastic scalp, 'LongShort PRO v2' (lab/STOCH.md).

  python runner/stoch.py dev
  python runner/stoch.py final     # ONE shot on the hold-out, only after a dev PASS
"""
import argparse
import csv
import json
import os
import sys
from collections import defaultdict
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(__file__))
from trap import mins, months, stats  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LAB = os.path.join(ROOT, "lab")
SYMBOLS = ["QQQ"]
DEV_START, DEV_END, HOLDOUT_START = date(2018, 1, 1), date(2024, 12, 31), date(2025, 1, 1)
R = {"k_len": 14, "lo": 30.0, "hi": 70.0, "sl_pct": 0.3, "tp_pct": 0.5, "cost_bps": 1.0,
     "risk_pct": 1.0, "max_leverage": 4.0, "last_signal": 15 * 60 + 49, "flat": 15 * 60 + 55}


def stoch_k(s, n):
    """%K per bar (None during warm-up), using only bars up to and including i."""
    out = []
    for i in range(len(s)):
        if i + 1 < n:
            out.append(None)
            continue
        w = s[i + 1 - n:i + 1]
        hh, ll = max(b["h"] for b in w), min(b["l"] for b in w)
        out.append(50.0 if hh == ll else 100 * (s[i]["c"] - ll) / (hh - ll))
    return out


def signal(k_prev, k_now):
    if k_prev is None or k_now is None:
        return None
    if k_prev < R["lo"] <= k_now:
        return "long"
    if k_prev > R["hi"] >= k_now:
        return "short"
    return None


def run_trade(s, i, side):
    """Enter at open of bar i. Returns (trade dict, exit index)."""
    e = s[i]["o"]
    sg = 1 if side == "long" else -1
    stop = e * (1 - sg * R["sl_pct"] / 100)
    tgt = e * (1 + sg * R["tp_pct"] / 100)
    for j in range(i, len(s)):
        b = s[j]
        if mins(b["t"]) >= R["flat"]:
            return (b["o"], "close"), j
        lo_hit = b["l"] <= stop if sg > 0 else b["h"] >= stop
        tp_hit = b["h"] >= tgt if sg > 0 else b["l"] <= tgt
        if lo_hit:  # stop first when both are touched
            px = b["o"] if j > i and ((sg > 0 and b["o"] < stop) or (sg < 0 and b["o"] > stop)) else stop
            return (px, "stop"), j
        if tp_hit:
            px = b["o"] if j > i and ((sg > 0 and b["o"] > tgt) or (sg < 0 and b["o"] < tgt)) else tgt
            return (px, "target"), j
    return (s[-1]["c"], "close"), len(s) - 1


def day_trades(day, sym):
    s = [b for b in sorted(day, key=lambda x: x["t"]) if 570 <= mins(b["t"]) < 960]
    if len(s) < 300:
        return [], "geen volledige sessie"
    k = stoch_k(s, R["k_len"])
    out, i = [], 1
    while i < len(s) - 1:
        side = signal(k[i - 1], k[i])
        if side is None or mins(s[i]["t"]) > R["last_signal"]:
            i += 1
            continue
        (px, why), j = run_trade(s, i + 1, side)
        e = s[i + 1]["o"]
        sg = 1 if side == "long" else -1
        risk = e * R["sl_pct"] / 100
        gross = sg * (px - e)
        cost = e * R["cost_bps"] / 1e4 + px * R["cost_bps"] / 1e4
        r = (gross - cost) / risk
        risk_frac = min(R["risk_pct"] / 100, R["max_leverage"] * R["sl_pct"] / 100)
        out.append({"date": s[i]["t"].date().isoformat(), "sym": sym, "side": side,
                    "t_in": s[i + 1]["t"].strftime("%H:%M"), "t_out": s[j]["t"].strftime("%H:%M"),
                    "entry": round(e, 2), "exit": round(px, 2), "why": why,
                    "planned_rr": round(R["tp_pct"] / R["sl_pct"], 2),
                    "gross_r": round(gross / risk, 4), "r": round(r, 4), "ret": round(r * risk_frac, 6)})
        i = j + 1
    return out, None


def gross_mean(tr):
    return round(sum(t["gross_r"] for t in tr) / len(tr), 3) if tr else None


def main(argv=None):
    import alpaca
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["dev", "final"])
    a = ap.parse_args(argv)
    if a.mode == "dev":
        frm, to = DEV_START, DEV_END
        path = os.path.join(LAB, "stoch-dev.json")
    else:
        path = os.path.join(LAB, "stoch-final.json")
        if os.path.exists(path):
            sys.exit("De eindtoets is al gedaan. Eén keer = één keer.")
        if json.load(open(os.path.join(LAB, "stoch-dev.json"))).get("verdict") != "PASS":
            sys.exit("Dev-fase niet gehaald: geen eindtoets (lab/STOCH.md).")
        frm, to = HOLDOUT_START, date.today() - timedelta(days=1)

    trades, skips = [], defaultdict(int)
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
                t, why = day_trades(day, sym)
                trades += t
                if why:
                    skips[why] += 1
        print(f"  {m0:%Y-%m}: {len(trades)} trades", file=sys.stderr)

    def block(tr):
        return {**stats(tr), "gross_mean_r": gross_mean(tr)}

    res = {"mode": a.mode, "period": [frm.isoformat(), to.isoformat()], "rules": R,
           "skipped_days": dict(skips), "all": block(trades),
           "by_side": {s: block([t for t in trades if t["side"] == s]) for s in ("long", "short")},
           "by_year": {y: block([t for t in trades if t["date"].startswith(str(y))])
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
    print(json.dumps({k: res[k] for k in ("verdict", "all", "by_side")}, indent=1, default=str))


if __name__ == "__main__":
    main()
