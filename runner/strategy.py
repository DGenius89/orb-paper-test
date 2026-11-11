"""Opening-range breakout, the rule from the day-trader-skill (trader-entry/exit):

- Opening range: the 5-minute bars that START between 09:30 and 09:45 ET (15 min).
- Trigger: the first 5-minute bar that CLOSES above the range high, starting at or
  after 09:45 and no later than the entry cutoff.
- Stop: the range midpoint. Target: entry + 1R. Flat at 15:55 ET.

Pure functions only, shared by backtest.py and live.py so both trade the same rule.
Bars are dicts: {"t": aware datetime (bar start, America/New_York), "o","h","l","c","v"}.
"""
from datetime import time
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
OPEN = time(9, 30)


def hm(s):
    h, m = s.split(":")
    return time(int(h), int(m))


def session_bars(bars):
    """Regular-session bars only (09:30 <= start < 16:00)."""
    return [b for b in bars if time(9, 30) <= b["t"].time() < time(16, 0)]


def opening_range(bars, or_minutes=15):
    end = (9 * 60 + 30 + or_minutes)
    rng = [b for b in bars if 9 * 60 + 30 <= b["t"].hour * 60 + b["t"].minute < end]
    if len(rng) < or_minutes // 5:  # missing bars: no reliable range
        return None
    hi, lo = max(b["h"] for b in rng), min(b["l"] for b in rng)
    if hi <= lo:
        return None
    return {"high": hi, "low": lo, "mid": (hi + lo) / 2}


def find_trigger(bars, cfg):
    """First bar after the range that closes above its high. Returns dict or None."""
    rng = opening_range(bars, cfg["or_minutes"])
    if not rng:
        return None
    start = 9 * 60 + 30 + cfg["or_minutes"]
    cutoff = hm(cfg["no_entries_after"])
    for i, b in enumerate(bars):
        mins = b["t"].hour * 60 + b["t"].minute
        if mins < start:
            continue
        if b["t"].time() > cutoff:
            return None
        if b["c"] > rng["high"]:
            entry_ref = b["c"]
            risk = entry_ref - rng["mid"]
            if risk <= 0 or risk / entry_ref < cfg["min_risk_pct"] / 100:
                return None
            if risk / entry_ref > cfg["max_risk_pct"] / 100:
                return None
            return {"index": i, "bar_t": b["t"], "range": rng, "entry_ref": entry_ref,
                    "stop": round(rng["mid"], 2), "breakout_pct": (b["c"] / rng["high"] - 1) * 100}
    return None


def size(entry, stop, cfg):
    """Shares so that a stop-out loses at most max_loss_per_trade_usd, capped by order size."""
    per_share = entry - stop
    if per_share <= 0:
        return 0
    qty = int(cfg["max_loss_per_trade_usd"] // per_share)
    qty = min(qty, int(cfg["max_order_usd"] // entry))
    return max(qty, 0)


def slip(price, side, cfg):
    """Adverse fill: buys fill higher, sells fill lower."""
    s = cfg["slippage_bps"] / 10000
    return price * (1 + s) if side == "buy" else price * (1 - s)


def simulate(bars, trig, cfg):
    """Replay the trade on real bars after the trigger. Entry at the NEXT bar's open
    (you can only act after the trigger bar closes), with slippage. If one bar touches
    both stop and target we assume the stop came first (conservative)."""
    i = trig["index"] + 1
    if i >= len(bars):
        return None
    raw_entry = bars[i]["o"]
    stop = trig["stop"]
    if raw_entry <= stop:  # gapped through the stop before we could get in
        return None
    risk = raw_entry - stop
    target = raw_entry + cfg["target_r"] * risk
    entry = slip(raw_entry, "buy", cfg)
    qty = size(entry, stop, cfg)
    if qty < 1:
        return None
    flat = hm(cfg["flat_by"])
    exit_px, why, exit_t = None, None, None
    for b in bars[i:]:
        if b["t"].time() >= flat:
            exit_px, why, exit_t = b["o"], "close", b["t"]
            break
        if b["l"] <= stop:
            exit_px, why, exit_t = min(stop, b["o"]), "stop", b["t"]
            break
        if b["h"] >= target:
            exit_px, why, exit_t = max(target, b["o"]), "target", b["t"]
            break
    if exit_px is None:
        exit_px, why, exit_t = bars[-1]["c"], "close", bars[-1]["t"]
    fill_out = slip(exit_px, "sell", cfg)
    gross = (exit_px - raw_entry) * qty
    net = (fill_out - entry) * qty - 2 * cfg["commission_per_order_usd"]
    return {"entry_t": bars[i]["t"], "exit_t": exit_t, "entry": round(entry, 4), "stop": stop,
            "target": round(target, 2), "exit": round(fill_out, 4), "qty": qty, "why": why,
            "gross": round(gross, 2), "net": round(net, 2), "r": round((fill_out - entry) / risk, 3)}


def pick_day(candidates, cfg):
    """Several symbols trigger on one day: take them in time order (ties: strongest
    breakout first), max trades per day, stop after the daily loss limit."""
    candidates.sort(key=lambda x: (x["trig"]["bar_t"], -x["trig"]["breakout_pct"]))
    taken, pnl = [], 0.0
    for c in candidates:
        if len(taken) >= cfg["max_trades_per_day"] or pnl <= -cfg["max_daily_loss_usd"]:
            break
        if c["trade"] is None:
            continue
        taken.append(c)
        pnl += c["trade"]["net"]
    return taken
