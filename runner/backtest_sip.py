"""Variant: ORB on "stocks in play" instead of a fixed watchlist.

Every day, without look-ahead:
  1. 09:30  universe = all active US stocks with prev close >= $5 and 14-day average
            volume >= 1M shares; candidates = gap up >= 2 % (today's open vs prev close),
            the 50 biggest gappers.
  2. 09:45  rank those by relative volume (first 15 minutes' volume / 14-day avg daily
            volume) and keep the top 20.
  3. Same ORB rule, stop, target, sizing, costs and daily limits as backtest.py.

Pre-registered verdict (written before the run, see README): the variant passes only if
the OUT-OF-SAMPLE part is net profitable AND the whole period beats SPY buy-and-hold.

  python runner/backtest_sip.py --months 12
"""
import argparse
import csv
import json
import os
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.dirname(__file__))
import alpaca  # noqa: E402
from backtest import stats  # noqa: E402
from strategy import ET, find_trigger, pick_day, session_bars, simulate  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEL = {"min_price": 5.0, "min_adv": 1_000_000, "adv_days": 14, "min_gap_pct": 2.0,
       "gappers": 50, "in_play": 20}


def universe():
    rows = alpaca.trade("GET", "/v2/assets", {"status": "active", "asset_class": "us_equity"})
    ok = {"NASDAQ", "NYSE", "ARCA", "AMEX", "BATS"}
    return sorted(a["symbol"] for a in rows
                  if a.get("tradable") and a.get("exchange") in ok and a["symbol"].isalpha())


def daily(symbols, start, end, feed):
    out = {}
    for i in range(0, len(symbols), 400):
        chunk = symbols[i:i + 400]
        got = alpaca.bars(chunk, start, end, timeframe="1Day", feed=feed)
        out.update({s: b for s, b in got.items() if b})
        print(f"  dagdata {min(i + 400, len(symbols))}/{len(symbols)}", file=sys.stderr)
    return out


def gappers(daily_bars, cfg_sel=SEL):
    """{date: [(symbol, gap_pct, adv)]}: the day's biggest qualifying gap-ups."""
    by_day = defaultdict(list)
    n = cfg_sel["adv_days"]
    for sym, bars in daily_bars.items():
        for i in range(n, len(bars)):
            prev = bars[i - 1]
            adv = sum(b["v"] for b in bars[i - n:i]) / n
            if prev["c"] < cfg_sel["min_price"] or adv < cfg_sel["min_adv"]:
                continue
            gap = (bars[i]["o"] / prev["c"] - 1) * 100
            if gap >= cfg_sel["min_gap_pct"]:
                by_day[bars[i]["t"].date()].append((sym, gap, adv))
    return {d: sorted(v, key=lambda x: -x[1])[:cfg_sel["gappers"]] for d, v in by_day.items()}


def in_play(intraday, cands, cfg_sel=SEL):
    """Top N by first-15-minute volume relative to average daily volume."""
    rv = []
    for sym, gap, adv in cands:
        first = [b for b in intraday.get(sym, []) if b["t"].hour == 9 and 30 <= b["t"].minute < 45]
        if len(first) == 3:
            rv.append((sym, sum(b["v"] for b in first) / adv))
    return [s for s, _ in sorted(rv, key=lambda x: -x[1])[:cfg_sel["in_play"]]]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--months", type=float, default=12)
    ap.add_argument("--feed", default="sip")
    ap.add_argument("--out", default=os.path.join(ROOT, "backtest-sip"))
    a = ap.parse_args(argv)
    cfg = json.load(open(os.path.join(ROOT, "config.json")))

    end = date.today()
    start = end - timedelta(days=int(a.months * 30.5))
    syms = universe()
    print(f"universum: {len(syms)} aandelen", file=sys.stderr)
    dbars = daily(syms, (start - timedelta(days=30)).isoformat() + "T00:00:00Z", end.isoformat() + "T00:00:00Z", a.feed)
    gaps = {d: v for d, v in gappers(dbars).items() if d >= start}

    trades, signals, days = [], 0, sorted(gaps)
    for n, d in enumerate(days):
        s = datetime(d.year, d.month, d.day, 9, 30, tzinfo=ET)
        cands = gaps[d]
        intraday = alpaca.bars([c[0] for c in cands], s.isoformat(), (s + timedelta(hours=7)).isoformat(),
                               timeframe="5Min", feed=a.feed)
        picks = in_play(intraday, cands)
        day_c = []
        for sym in picks:
            b = session_bars(sorted(intraday[sym], key=lambda x: x["t"]))
            trig = find_trigger(b, cfg)
            if trig:
                day_c.append({"sym": sym, "trig": trig, "trade": simulate(b, trig, cfg)})
        signals += len(day_c)
        for c in pick_day(day_c, cfg):
            trades.append({"date": d.isoformat(), "sym": c["sym"], **c["trade"]})
        if n % 20 == 0:
            print(f"  {d}: {len(trades)} trades tot nu", file=sys.stderr)

    split = days[int(len(days) * 2 / 3)].isoformat() if days else ""
    ins = [t for t in trades if t["date"] < split]
    oos = [t for t in trades if t["date"] >= split]
    spy = alpaca.bars([cfg["benchmark"]], days[0].isoformat() + "T00:00:00Z",
                      (days[-1] + timedelta(days=1)).isoformat() + "T00:00:00Z", timeframe="1Day", feed=a.feed)
    spy = spy[cfg["benchmark"]]
    spy_usd = round(cfg["budget"] * (spy[-1]["c"] / spy[0]["o"] - 1), 2) if spy else None
    res = {"variant": "stocks in play", "selection": SEL, "feed": a.feed,
           "period": [days[0].isoformat(), days[-1].isoformat()] if days else None,
           "universe": len(syms), "signals": signals, "split_date": split,
           "all_net": stats(trades), "all_gross": stats(trades, "gross"),
           "in_sample_net": stats(ins), "out_of_sample_net": stats(oos), "spy_buy_hold_usd": spy_usd}
    oos_net = res["out_of_sample_net"].get("total", 0)
    all_net = res["all_net"].get("total", 0)
    res["verdict"] = "PASS" if oos_net > 0 and spy_usd is not None and all_net > spy_usd else "FAIL"

    os.makedirs(a.out, exist_ok=True)
    json.dump(res, open(os.path.join(a.out, "summary.json"), "w"), indent=1, default=str)
    if trades:
        with open(os.path.join(a.out, "trades.csv"), "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(trades[0]))
            w.writeheader()
            w.writerows(trades)
    print(json.dumps(res, indent=1, default=str))


if __name__ == "__main__":
    main()
