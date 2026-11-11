"""Broad backtest of the skill's ORB rule: whole watchlist, many months, after costs,
split in-sample / out-of-sample, against SPY buy-and-hold.

  python runner/backtest.py --months 12            # Alpaca data (needs keys)
  python runner/backtest.py --yahoo-fixture F.gz   # offline check on a Yahoo chart dump
"""
import argparse
import csv
import gzip
import json
import os
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.dirname(__file__))
from strategy import ET, find_trigger, pick_day, session_bars, simulate  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def by_day(bars):
    d = defaultdict(list)
    for b in bars:
        d[b["t"].date()].append(b)
    return {k: sorted(v, key=lambda b: b["t"]) for k, v in d.items()}


def load_yahoo(path):
    j = json.load(gzip.open(path) if path.endswith(".gz") else open(path))
    r = j["chart"]["result"][0]
    q = r["indicators"]["quote"][0]
    out = []
    for i, ts in enumerate(r["timestamp"]):
        if None in (q["open"][i], q["high"][i], q["low"][i], q["close"][i]):
            continue
        out.append({"t": datetime.fromtimestamp(ts, ET), "o": q["open"][i], "h": q["high"][i],
                    "l": q["low"][i], "c": q["close"][i], "v": q["volume"][i] or 0})
    return {r["meta"]["symbol"]: out}


def load_alpaca(symbols, months):
    import alpaca
    end = date.today()
    start = end - timedelta(days=int(months * 30.5))
    data = {s: [] for s in symbols}
    cur = start
    while cur < end:  # month by month, 10 symbols at a time
        nxt = min(cur + timedelta(days=31), end)
        for i in range(0, len(symbols), 10):
            chunk = symbols[i:i + 10]
            got = alpaca.bars(chunk, cur.isoformat() + "T00:00:00Z", nxt.isoformat() + "T00:00:00Z")
            for s in chunk:
                data[s].extend(got.get(s, []))
        print(f"  data t/m {nxt}", file=sys.stderr)
        cur = nxt
    return data


def run(data, cfg):
    days = defaultdict(list)
    for sym, bars in data.items():
        for d, dbars in by_day(session_bars(bars)).items():
            trig = find_trigger(dbars, cfg)
            if trig:
                days[d].append({"sym": sym, "trig": trig, "trade": simulate(dbars, trig, cfg)})
    trades, signals = [], 0
    for d in sorted(days):
        signals += len(days[d])
        for c in pick_day(days[d], cfg):
            trades.append({"date": d.isoformat(), "sym": c["sym"], **c["trade"]})
    return trades, signals, sorted(days)


def stats(trades, key="net"):
    n = len(trades)
    if not n:
        return {"trades": 0}
    pnl = [t[key] for t in trades]
    wins = [p for p in pnl if p > 0]
    losses = [-p for p in pnl if p < 0]
    eq, peak, dd = 0.0, 0.0, 0.0
    for p in pnl:
        eq += p
        peak = max(peak, eq)
        dd = max(dd, peak - eq)
    why = defaultdict(int)
    for t in trades:
        why[t["why"]] += 1
    return {"trades": n, "total": round(sum(pnl), 2), "per_trade": round(sum(pnl) / n, 2),
            "win_rate": round(len(wins) / n * 100, 1),
            "profit_factor": round(sum(wins) / sum(losses), 2) if losses else None,
            "avg_r": round(sum(t["r"] for t in trades) / n, 3), "max_drawdown": round(dd, 2),
            "exits": dict(why)}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--months", type=float, default=12)
    ap.add_argument("--yahoo-fixture")
    ap.add_argument("--out", default=os.path.join(ROOT, "backtest"))
    a = ap.parse_args(argv)
    cfg = json.load(open(os.path.join(ROOT, "config.json")))

    data = load_yahoo(a.yahoo_fixture) if a.yahoo_fixture else load_alpaca(cfg["watchlist"], a.months)
    trades, signals, day_list = run(data, cfg)
    split = day_list[int(len(day_list) * 2 / 3)].isoformat() if day_list else ""
    ins = [t for t in trades if t["date"] < split]
    oos = [t for t in trades if t["date"] >= split]
    res = {"period": [day_list[0].isoformat(), day_list[-1].isoformat()] if day_list else None,
           "symbols": len(data), "signals": signals, "split_date": split,
           "all_net": stats(trades), "all_gross": stats(trades, "gross"),
           "in_sample_net": stats(ins), "out_of_sample_net": stats(oos)}

    if not a.yahoo_fixture and day_list:
        import alpaca
        b = alpaca.bars([cfg["benchmark"]], day_list[0].isoformat() + "T00:00:00Z",
                        (day_list[-1] + timedelta(days=1)).isoformat() + "T00:00:00Z", timeframe="1Day")
        spy = b[cfg["benchmark"]]
        if spy:
            res["spy_buy_hold_usd"] = round(cfg["budget"] * (spy[-1]["c"] / spy[0]["o"] - 1), 2)

    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, "summary.json"), "w") as fh:
        json.dump(res, fh, indent=1, default=str)
    if trades:
        with open(os.path.join(a.out, "trades.csv"), "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(trades[0]))
            w.writeheader()
            w.writerows(trades)
    print(json.dumps(res, indent=1, default=str))


if __name__ == "__main__":
    main()
