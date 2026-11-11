"""Insider cluster buys (lab/INSIDER.md).

  python runner/insider.py dev      # signals until DEV_SIGNAL_END, data never past HOLDOUT_START
  python runner/insider.py final    # ONE shot on the hold-out

SEC requires a User-Agent with contact details: env SEC_USER_AGENT ("Name email").
"""
import argparse
import csv
import io
import json
import math
import os
import sys
import time
import urllib.request
import zipfile
from collections import defaultdict
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.dirname(__file__))
from lab import metrics  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LAB = os.path.join(ROOT, "lab")
CACHE = os.path.join(ROOT, ".cache", "sec")
SEC = "https://www.sec.gov/files/structureddata/data/insider-transactions-data-sets/{q}_form345.zip"

FIRST_Q = (2016, 1)
DEV_SIGNAL_START = date(2016, 3, 1)
DEV_SIGNAL_END = date(2023, 9, 15)
HOLDOUT_START = date(2024, 1, 1)
R = {"min_value": 25_000, "window_days": 30, "min_insiders": 2, "cooldown_days": 90,
     "min_price": 5.0, "min_dollar_vol": 1_000_000, "hold_days": 63, "cost_bps": 20,
     "slots": 20}

csv.field_size_limit(10 ** 8)


# ---------------- SEC data ----------------
def quarters(until):
    y, q = FIRST_Q
    while (y, q) <= until:
        yield f"{y}q{q}"
        y, q = (y, q + 1) if q < 4 else (y + 1, 1)


def fetch(q):
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, f"{q}.zip")
    if not os.path.exists(path):
        ua = os.environ.get("SEC_USER_AGENT")
        if not ua:
            raise SystemExit("SEC_USER_AGENT ontbreekt (zet het als GitHub Secret).")
        req = urllib.request.Request(SEC.format(q=q), headers={"User-Agent": ua})
        for n in range(4):
            try:
                data = urllib.request.urlopen(req, timeout=180).read()
                break
            except Exception as e:
                if "404" in str(e):
                    return None
                time.sleep(3 * (n + 1))
        else:
            raise RuntimeError(f"SEC {q} niet op te halen")
        open(path, "wb").write(data)
        time.sleep(0.5)
    return zipfile.ZipFile(path)


def table(z, name):
    fn = next(n for n in z.namelist() if n.upper().endswith(name))
    with z.open(fn) as fh:
        yield from csv.DictReader(io.TextIOWrapper(fh, "utf-8", errors="replace"), delimiter="\t")


def pdate(s):
    s = (s or "").strip()
    for fmt in ("%d-%b-%Y", "%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(s[:11] if fmt == "%d-%b-%Y" else s[:10], fmt).date()
        except ValueError:
            pass
    return None


def fnum(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return 0.0


def purchases(qs):
    """Open-market purchases by directors/officers, value >= min_value."""
    out = []
    for q in qs:
        z = fetch(q)
        if z is None:
            print(f"  {q}: (nog) niet gepubliceerd", file=sys.stderr)
            continue
        sub = {}
        for r in table(z, "SUBMISSION.TSV"):
            if r.get("DOCUMENT_TYPE", "").strip() == "4":
                sub[r["ACCESSION_NUMBER"]] = (pdate(r.get("FILING_DATE")), r.get("ISSUERCIK", "").strip(),
                                              (r.get("ISSUERTRADINGSYMBOL") or "").strip().upper())
        owners = defaultdict(list)
        for r in table(z, "REPORTINGOWNER.TSV"):
            rel = (r.get("RPTOWNER_RELATIONSHIP") or "").lower()
            if "director" in rel or "officer" in rel:
                owners[r["ACCESSION_NUMBER"]].append(r.get("RPTOWNERCIK", "").strip())
        n0 = len(out)
        for r in table(z, "NONDERIV_TRANS.TSV"):
            acc = r["ACCESSION_NUMBER"]
            if acc not in sub or acc not in owners:
                continue
            if (r.get("TRANS_CODE") or "").strip() != "P" or (r.get("TRANS_ACQUIRED_DISP_CD") or "").strip() != "A":
                continue
            value = fnum(r.get("TRANS_SHARES")) * fnum(r.get("TRANS_PRICEPERSHARE"))
            if value < R["min_value"]:
                continue
            fdate, cik, sym = sub[acc]
            if not fdate or not sym or not sym.isalpha():
                continue
            for o in owners[acc]:
                out.append({"filed": fdate, "trans": pdate(r.get("TRANS_DATE")) or fdate,
                            "cik": cik, "sym": sym, "owner": o, "value": value})
        print(f"  {q}: {len(out) - n0} aankopen", file=sys.stderr)
    return out


def clusters(buys, start, end):
    by = defaultdict(list)
    for b in buys:
        by[b["cik"]].append(b)
    sig = []
    for cik, rows in by.items():
        rows.sort(key=lambda r: (r["filed"], r["trans"]))
        last = None
        for i, r in enumerate(rows):
            if last and (r["filed"] - last).days < R["cooldown_days"]:
                continue
            win = {x["owner"] for x in rows[:i + 1] if 0 <= (r["trans"] - x["trans"]).days <= R["window_days"]
                   and x["filed"] <= r["filed"]}
            if len(win) >= R["min_insiders"] and start <= r["filed"] <= end:
                sig.append({"filed": r["filed"], "sym": r["sym"], "cik": cik, "insiders": len(win)})
                last = r["filed"]
    return sorted(sig, key=lambda s: s["filed"])


# ---------------- prices ----------------
def prices(symbols, end):
    import alpaca
    out = {}
    syms = sorted(set(symbols) | {"SPY", "BIL"})
    for i in range(0, len(syms), 100):
        got = alpaca.bars(syms[i:i + 100], "2016-01-01T00:00:00Z", end.isoformat() + "T00:00:00Z",
                          timeframe="1Day", feed="sip", adjustment="all")
        for s, bars in got.items():
            if bars:
                out[s] = {b["t"].date(): (b["o"], b["c"], b["v"]) for b in bars if b["t"].date() < end}
        print(f"  koersen {min(i + 100, len(syms))}/{len(syms)}", file=sys.stderr)
    return out


def trade(sig, px, cal_idx, cal):
    """Entry next open after filing, exit at the close of day hold_days. None if filtered."""
    p = px.get(sig["sym"])
    if not p:
        return None, "geen koersdata"
    days = sorted(p)
    after = [d for d in days if d > sig["filed"]]
    if not after:
        return None, "geen koersdata"
    e = after[0]
    k = days.index(e)
    if k < 20 or (e - sig["filed"]).days > 7:
        return None, "geen koersdata"
    prev_c = p[days[k - 1]][1]
    dvol = sum(p[d][1] * p[d][2] for d in days[k - 20:k]) / 20
    if prev_c < R["min_price"] or dvol < R["min_dollar_vol"]:
        return None, "te klein/goedkoop"
    xi = min(k + R["hold_days"] - 1, len(days) - 1)
    x = days[xi]
    c = R["cost_bps"] / 10000
    gross = p[x][1] / p[e][0] - 1
    net = (p[x][1] * (1 - c)) / (p[e][0] * (1 + c)) - 1
    spy = px["SPY"]
    spy_r = spy[x][1] / spy[e][0] - 1 if e in spy and x in spy else 0.0
    return {"filed": sig["filed"].isoformat(), "sym": sig["sym"], "insiders": sig["insiders"],
            "entry": e.isoformat(), "exit": x.isoformat(), "held": xi - k + 1,
            "gross": round(gross, 5), "net": round(net, 5), "spy": round(spy_r, 5),
            "excess": round(net - spy_r, 5)}, None


def portfolio(trades, px, start, end):
    """5% per position, max `slots`, idle cash in BIL. Returns [(date, equity)]."""
    cal = sorted(d for d in px["SPY"] if start <= d < end)
    bil = px["BIL"]
    c = R["cost_bps"] / 10000
    by_entry = defaultdict(list)
    for t in trades:
        by_entry[date.fromisoformat(t["entry"])].append(t)
    cash_units = 1.0 / bil[cal[0]][0]
    pos, eq = [], []
    for d in cal:
        # exits at the close happen after entries at the open; entries first
        for t in by_entry.get(d, []):
            if len(pos) >= R["slots"]:
                continue
            p = px[t["sym"]]
            if d not in p or d not in bil:
                continue
            val = cash_units * bil[d][0] + sum(u * px[s][d][0] for s, u, _ in pos if d in px[s])
            amt = min(val / R["slots"], cash_units * bil[d][0])
            if amt <= 0:
                continue
            cash_units -= amt / bil[d][0]
            pos.append((t["sym"], amt * (1 - c) / p[d][0], date.fromisoformat(t["exit"])))
        keep = []
        for s, u, x in pos:
            if d >= x and d in px[s] and d in bil:
                cash_units += u * px[s][d][1] * (1 - c) / bil[d][1]
            else:
                keep.append((s, u, x))
        pos = keep
        if d in bil:
            last = {s: px[s][max(k for k in px[s] if k <= d)][1] for s, _, _ in pos}
            eq.append((d, cash_units * bil[d][1] + sum(u * last[s] for s, u, _ in pos)))
    return eq


def event_stats(trades):
    n = len(trades)
    if n < 2:
        return {"trades": n}
    ex = [t["excess"] for t in trades]
    m = sum(ex) / n
    sd = math.sqrt(sum((x - m) ** 2 for x in ex) / (n - 1))
    return {"trades": n, "mean_net_pct": round(sum(t["net"] for t in trades) / n * 100, 2),
            "mean_excess_vs_spy_pct": round(m * 100, 2),
            "median_excess_pct": round(sorted(ex)[n // 2] * 100, 2),
            "t_stat": round(m / (sd / math.sqrt(n)), 2) if sd else None,
            "beat_spy_pct": round(sum(1 for x in ex if x > 0) / n * 100, 1)}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["dev", "final"])
    a = ap.parse_args(argv)
    os.makedirs(LAB, exist_ok=True)

    if a.mode == "dev":
        qs = list(quarters((2023, 3)))
        s_start, s_end, p_end, pf_start = DEV_SIGNAL_START, DEV_SIGNAL_END, HOLDOUT_START, DEV_SIGNAL_START
        path = os.path.join(LAB, "insider-dev.json")
    else:
        path = os.path.join(LAB, "insider-final.json")
        if os.path.exists(path):
            raise SystemExit("De eindtoets is al gedaan. Eén keer = één keer.")
        dev = json.load(open(os.path.join(LAB, "insider-dev.json")))
        if dev.get("verdict") != "PASS":
            raise SystemExit("Dev-fase niet gehaald: geen eindtoets (lab/INSIDER.md).")
        today = date.today()
        qs = list(quarters((today.year, (today.month - 1) // 3 + 1)))
        s_start, s_end, p_end, pf_start = HOLDOUT_START, today - timedelta(days=95), today + timedelta(days=1), HOLDOUT_START

    sigs = clusters(purchases(qs), s_start, s_end)
    print(f"signalen: {len(sigs)}", file=sys.stderr)
    px = prices([s["sym"] for s in sigs], p_end)
    trades, skipped = [], defaultdict(int)
    for s in sigs:
        t, why = trade(s, px, None, None)
        if t:
            trades.append(t)
        else:
            skipped[why] += 1
    eq = portfolio(trades, px, pf_start, p_end)
    spy_eq = [(d, px["SPY"][d][1]) for d in sorted(px["SPY"]) if pf_start <= d < p_end]
    pm, sm = metrics(eq, pf_start, p_end), metrics(spy_eq, pf_start, p_end)
    ev = event_stats(trades)
    res = {"mode": a.mode, "rules": R, "signals": len(sigs), "skipped": dict(skipped),
           "events": ev, "portfolio": pm, "spy": sm}
    if a.mode == "dev":
        ok = ev.get("mean_excess_vs_spy_pct", 0) > 0 and (ev.get("t_stat") or 0) >= 2 \
            and pm and sm and pm["sharpe"] > sm["sharpe"]
    else:
        ok = ev.get("mean_excess_vs_spy_pct", 0) > 0 and pm and sm \
            and pm["total_return_pct"] >= sm["total_return_pct"]
    res["verdict"] = "PASS" if ok else "FAIL"
    json.dump(res, open(path, "w"), indent=1, default=str)
    with open(path.replace(".json", "-trades.csv"), "w", newline="") as fh:
        if trades:
            w = csv.DictWriter(fh, fieldnames=list(trades[0]))
            w.writeheader()
            w.writerows(trades)
    print(json.dumps(res, indent=1, default=str))


if __name__ == "__main__":
    main()
