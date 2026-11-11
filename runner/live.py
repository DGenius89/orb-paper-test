"""Live PAPER runner. Started by GitHub Actions every 30 minutes on weekdays; each run
loops for up to --minutes, then exits (the next run takes over). Stateless: everything
it needs (today's bars, today's orders) is re-read from Alpaca, so a missed or delayed
run cannot double-trade. Duplicate entries are also blocked by Alpaca itself through
the client_order_id "orb-<SYMBOL>-<YYYYMMDD>".
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(__file__))
import alpaca  # noqa: E402
from strategy import ET, find_trigger, hm, session_bars, size  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STALE_MIN = 10  # don't chase a trigger we noticed too late


def log(msg):
    print(f"{datetime.now(ET):%H:%M:%S} ET  {msg}", flush=True)


def todays_orders(today):
    after = datetime.combine(today, hm("04:00"), ET).isoformat()
    rows = alpaca.trade("GET", "/v2/orders", {"status": "all", "after": after, "limit": 500, "nested": "true"})
    return [o for o in rows if (o.get("client_order_id") or "").startswith("orb-")]


def flatten():
    log("15:55 ET: alles sluiten")
    alpaca.trade("DELETE", "/v2/positions", {"cancel_orders": "true"})


def tick(cfg, today, now):
    acct = alpaca.trade("GET", "/v2/account")
    day_pnl = float(acct["equity"]) - float(acct["last_equity"])
    orders = todays_orders(today)
    traded = {o["symbol"] for o in orders}
    if len(traded) >= cfg["max_trades_per_day"]:
        return "max trades bereikt"
    if day_pnl <= -cfg["max_daily_loss_usd"]:
        return f"dagverlies-limiet ({day_pnl:.2f})"
    if now.time() > hm(cfg["no_entries_after"]):
        return "na entry-cutoff"

    start = datetime.combine(today, hm("09:30"), ET)
    data = alpaca.bars(cfg["watchlist"], start.isoformat(), now.isoformat())
    cands = []
    for sym, bars in data.items():
        if sym in traded:
            continue
        # only COMPLETED bars: a 5-min bar starting at t is done at t+5
        done = [b for b in session_bars(bars) if b["t"] + timedelta(minutes=5) <= now]
        trig = find_trigger(done, cfg)
        if not trig:
            continue
        age = (now - (trig["bar_t"] + timedelta(minutes=5))).total_seconds() / 60
        if age > STALE_MIN:
            log(f"{sym}: trigger van {trig['bar_t']:%H:%M} te oud ({age:.0f} min), overgeslagen")
            traded.add(sym)  # only the first trigger of the day counts, like the backtest
            continue
        cands.append((sym, trig))
    cands.sort(key=lambda x: (x[1]["bar_t"], -x[1]["breakout_pct"]))

    for sym, trig in cands:
        if len(traded) >= cfg["max_trades_per_day"]:
            break
        q = alpaca.call("GET", alpaca.DATA, f"/v2/stocks/{sym}/quotes/latest", {"feed": "iex"})["quote"]
        px = float(q.get("ap") or 0) or trig["entry_ref"]
        stop = trig["stop"]
        if px <= stop * 1.001:
            log(f"{sym}: koers {px} al bij stop {stop}, overgeslagen")
            continue
        risk = px - stop
        target = round(px + cfg["target_r"] * risk, 2)
        qty = size(px, stop, cfg)
        if qty < 1:
            continue
        body = {"symbol": sym, "qty": str(qty), "side": "buy", "type": "market",
                "time_in_force": "day", "order_class": "bracket",
                "client_order_id": f"orb-{sym}-{today:%Y%m%d}",
                "take_profit": {"limit_price": f"{target:.2f}"},
                "stop_loss": {"stop_price": f"{stop:.2f}"}}
        try:
            alpaca.trade("POST", "/v2/orders", body=body)
            log(f"KOOP {qty} {sym} ~{px:.2f} stop {stop:.2f} target {target:.2f} "
                f"(range {trig['range']['low']:.2f}-{trig['range']['high']:.2f})")
            traded.add(sym)
        except RuntimeError as e:
            log(f"{sym}: order geweigerd: {e}")
            traded.add(sym)
    return f"{len(traded)} symbolen vandaag, dag-P&L {day_pnl:+.2f}"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--minutes", type=float, default=29)
    a = ap.parse_args(argv)
    cfg = json.load(open(os.path.join(ROOT, "config.json")))

    clock = alpaca.trade("GET", "/v2/clock")
    if not clock["is_open"]:
        log("markt dicht, niets te doen")
        return
    stop_at = time.time() + a.minutes * 60
    while time.time() < stop_at:
        now = datetime.now(ET)
        today = now.date()
        if now.time() >= hm(cfg["flat_by"]):
            flatten()
            return
        if now.time() >= hm("09:45"):
            try:
                log(tick(cfg, today, now))
            except Exception as e:  # keep looping; next tick re-reads everything
                log(f"fout: {e}")
        # wake ~20 s after the next 5-minute boundary, when the new bar is complete
        nxt = (now.replace(second=0, microsecond=0) + timedelta(minutes=5 - now.minute % 5, seconds=20))
        flat_t = datetime.combine(today, hm(cfg["flat_by"]), ET)
        time.sleep(max(5, min((nxt - datetime.now(ET)).total_seconds(),
                              (flat_t - datetime.now(ET)).total_seconds() + 1,
                              stop_at - time.time())))


if __name__ == "__main__":
    main()
