"""Daily report after the close. Appends to paper-log/:

  trades.csv   one row per round trip on the paper account (gross, and net after the
               slippage estimate from config.json, since paper fills are too kind)
  equity.csv   account equity per day next to a SPY buy-and-hold of the same budget
  shadow.csv   what the backtest rule says it would have done today, so live and
               theory can be compared (missed triggers, different fills)
  SUMMARY.md   running totals, rewritten every day
"""
import csv
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(__file__))
import alpaca  # noqa: E402
from strategy import ET, find_trigger, hm, pick_day, session_bars, simulate  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG = os.path.join(ROOT, "paper-log")


def append(name, rows, fields):
    if not rows:
        return
    path = os.path.join(LOG, name)
    new = not os.path.exists(path)
    with open(path, "a", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        if new:
            w.writeheader()
        w.writerows(rows)


def read(name):
    path = os.path.join(LOG, name)
    return list(csv.DictReader(open(path))) if os.path.exists(path) else []


def round_trips(day, cfg):
    fills = alpaca.trade("GET", "/v2/account/activities/FILL", {"date": day.isoformat()}) or []
    fills.sort(key=lambda f: f["transaction_time"])
    open_ = defaultdict(list)
    out = []
    s = cfg["slippage_bps"] / 10000
    for f in fills:
        sym, qty, px = f["symbol"], float(f["qty"]), float(f["price"])
        if f["side"] == "buy":
            open_[sym].append([qty, px, f["transaction_time"]])
            continue
        while qty > 0 and open_[sym]:
            lot = open_[sym][0]
            q = min(qty, lot[0])
            gross = (px - lot[1]) * q
            net = gross - (lot[1] + px) * s * q
            out.append({"date": day.isoformat(), "symbol": sym, "qty": q, "entry": lot[1], "exit": px,
                        "entry_time": lot[2][11:19], "exit_time": f["transaction_time"][11:19],
                        "gross": round(gross, 2), "net_est": round(net, 2)})
            lot[0] -= q
            qty -= q
            if lot[0] <= 0:
                open_[sym].pop(0)
    return out


def shadow(day, cfg):
    start = datetime.combine(day, hm("09:30"), ET)
    data = alpaca.bars(cfg["watchlist"], start.isoformat(), (start + timedelta(hours=7)).isoformat())
    cands = []
    for sym, bars in data.items():
        b = session_bars(bars)
        trig = find_trigger(b, cfg)
        if trig:
            cands.append({"sym": sym, "trig": trig, "trade": simulate(b, trig, cfg)})
    rows = []
    for c in pick_day(cands, cfg):
        t = c["trade"]
        rows.append({"date": day.isoformat(), "symbol": c["sym"], "trigger": f"{c['trig']['bar_t']:%H:%M}",
                     "entry": t["entry"], "exit": t["exit"], "why": t["why"], "qty": t["qty"], "net": t["net"]})
    return rows, len(cands)


def summary(cfg):
    tr, eq, sh = read("trades.csv"), read("equity.csv"), read("shadow.csv")
    n = len(tr)
    net = sum(float(r["net_est"]) for r in tr)
    gross = sum(float(r["gross"]) for r in tr)
    wins = sum(1 for r in tr if float(r["net_est"]) > 0)
    w = [float(r["net_est"]) for r in tr if float(r["net_est"]) > 0]
    l = [-float(r["net_est"]) for r in tr if float(r["net_est"]) < 0]
    sh_net = sum(float(r["net"]) for r in sh)
    lines = ["# Paper-test ORB (day-trader-skill)", "",
             f"Bijgewerkt {datetime.now(ET):%Y-%m-%d %H:%M} ET. Handelsdagen: {len(eq)}.", "",
             "| | waarde |", "|---|---|",
             f"| Trades | {n} |",
             f"| Winst bruto (paper-fills) | ${gross:,.2f} |",
             f"| Winst netto (na slippage-schatting) | ${net:,.2f} |",
             f"| Winrate netto | {wins / n * 100:.0f}% |" if n else "| Winrate | - |",
             f"| Profit factor netto | {sum(w) / sum(l):.2f} |" if l else "| Profit factor | - |",
             f"| Schaduw-backtest zelfde dagen | ${sh_net:,.2f} ({len(sh)} trades) |"]
    if eq:
        lines += [f"| Equity nu | ${float(eq[-1]['equity']):,.2f} (start ${float(eq[0]['start_equity']):,.2f}) |",
                  f"| SPY kopen-en-houden, zelfde budget | ${float(eq[-1]['spy_hold_pnl']):,.2f} |"]
    lines += ["", f"Beoordeling pas zinvol vanaf 50 trades; doel 100. Nu: {n}.", ""]
    open(os.path.join(LOG, "SUMMARY.md"), "w").write("\n".join(lines))


def main():
    cfg = json.load(open(os.path.join(ROOT, "config.json")))
    os.makedirs(LOG, exist_ok=True)
    day = datetime.now(ET).date()
    cal = alpaca.trade("GET", "/v2/calendar", {"start": day.isoformat(), "end": day.isoformat()})
    if not cal or cal[0]["date"] != day.isoformat():
        print("geen handelsdag")
        return
    if any(r["date"] == day.isoformat() for r in read("equity.csv")):
        print("vandaag al gerapporteerd")
        return

    trips = round_trips(day, cfg)
    append("trades.csv", trips, ["date", "symbol", "qty", "entry", "exit", "entry_time", "exit_time",
                                 "gross", "net_est"])
    sh, nsig = shadow(day, cfg)
    append("shadow.csv", sh, ["date", "symbol", "trigger", "entry", "exit", "why", "qty", "net"])

    acct = alpaca.trade("GET", "/v2/account")
    prev = read("equity.csv")
    start_eq = float(prev[0]["start_equity"]) if prev else float(acct["last_equity"])
    first_day = prev[0]["date"] if prev else day.isoformat()
    spy = alpaca.bars([cfg["benchmark"]], first_day + "T00:00:00Z",
                      (day + timedelta(days=1)).isoformat() + "T00:00:00Z", timeframe="1Day")[cfg["benchmark"]]
    spy_pnl = cfg["budget"] * (spy[-1]["c"] / spy[0]["o"] - 1) if spy else 0
    append("equity.csv", [{"date": day.isoformat(), "equity": acct["equity"], "start_equity": start_eq,
                           "trades": len(trips), "signals": nsig, "spy_hold_pnl": round(spy_pnl, 2)}],
           ["date", "equity", "start_equity", "trades", "signals", "spy_hold_pnl"])
    summary(cfg)
    print(open(os.path.join(LOG, "SUMMARY.md")).read())


if __name__ == "__main__":
    main()
