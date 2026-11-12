"""The wheel vs. the S&P 500 using Cboe PutWrite (PUT) and BuyWrite (BXM) indexes (lab/WHEEL.md).

  python runner/wheel.py
"""
import csv
import io
import json
import os
import sys
import time
import urllib.request
from datetime import date, datetime

sys.path.insert(0, os.path.dirname(__file__))
from lab import metrics  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LAB = os.path.join(ROOT, "lab")
CBOE = "https://cdn.cboe.com/api/global/us_indices/daily_prices/{}_History.csv"


def parse_cboe(text):
    """Cboe history CSVs: some have 'DATE,PUT', others 'DATE,OPEN,HIGH,LOW,CLOSE', sometimes with
    a disclaimer above the header. Returns [(date, value)] using the last numeric column."""
    out = []
    for row in csv.reader(io.StringIO(text)):
        if not row:
            continue
        d = None
        for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%m/%d/%y"):
            try:
                d = datetime.strptime(row[0].strip(), fmt).date()
                break
            except ValueError:
                pass
        if d is None:
            continue
        vals = []
        for x in row[1:]:
            try:
                vals.append(float(x.replace(",", "")))
            except ValueError:
                pass
        if vals and vals[-1] > 0:
            out.append((d, vals[-1]))
    return sorted(set(out))


def fetch(name):
    req = urllib.request.Request(CBOE.format(name), headers={"User-Agent": "Mozilla/5.0 orb-paper-test research"})
    for n in range(4):
        try:
            return parse_cboe(urllib.request.urlopen(req, timeout=120).read().decode("utf-8", "replace"))
        except Exception as e:
            err = e
            time.sleep(3 * (n + 1))
    raise RuntimeError(f"Cboe {name}: {err}")


def yearly(series):
    out, prev = {}, None
    by = {}
    for d, v in series:
        by.setdefault(d.year, []).append(v)
    for y in sorted(by):
        if prev is not None:
            out[y] = round((by[y][-1] / prev - 1) * 100, 1)
        prev = by[y][-1]
    return out


def window(series, frm, to=None):
    return [(d, v) for d, v in series if d >= frm and (to is None or d <= to)]


def main():
    s = {n: fetch(n) for n in ("PUT", "BXM", "SPX")}
    for n, v in s.items():
        print(f"{n}: {len(v)} dagen, {v[0][0]} t/m {v[-1][0]}", file=sys.stderr)
    import alpaca
    spy = alpaca.bars(["SPY"], "2016-01-01T00:00:00Z", date.today().isoformat() + "T00:00:00Z",
                      timeframe="1Day", feed="sip", adjustment="all")["SPY"]
    s["SPY_TR"] = [(b["t"].date(), b["c"]) for b in spy]

    start_full = max(s["PUT"][0][0], s["BXM"][0][0], s["SPX"][0][0])
    end = min(v[-1][0] for v in s.values())
    full = {n: metrics(window(s[n], start_full, end), start_full, date(end.year, end.month, end.day))
            for n in ("PUT", "BXM", "SPX")}
    since16 = {n: metrics(window(s[n], date(2016, 1, 4), end), date(2016, 1, 4), end) for n in s}
    yrs = {n: yearly(window(s[n], date(start_full.year, 1, 1))) for n in ("PUT", "BXM", "SPX")}
    yrs["SPY_TR"] = yearly(s["SPY_TR"])
    crisis = {y: {n: yrs[n].get(y) for n in yrs} for y in (2008, 2020, 2022)}
    claim = {n: {"years": len(yrs[n]), "years_at_or_above_35": sum(1 for v in yrs[n].values() if v >= 35),
                 "negative_years": sum(1 for v in yrs[n].values() if v < 0),
                 "worst_year": min(yrs[n].items(), key=lambda x: x[1]) if yrs[n] else None,
                 "best_year": max(yrs[n].items(), key=lambda x: x[1]) if yrs[n] else None}
             for n in ("PUT", "BXM")}
    ok = all(c["years_at_or_above_35"] == c["years"] for c in claim.values())
    res = {"full_history": {"from": start_full.isoformat(), "to": end.isoformat(), "metrics": full},
           "since_2016_with_spy_total_return": since16, "crisis_years_pct": crisis,
           "claim_35pct_every_year": claim, "yearly_pct": yrs,
           "verdict_claim": "HOUDT STAND" if ok else "FAIL"}
    os.makedirs(LAB, exist_ok=True)
    json.dump(res, open(os.path.join(LAB, "wheel.json"), "w"), indent=1, default=str)
    print(json.dumps({k: v for k, v in res.items() if k != "yearly_pct"}, indent=1, default=str))


if __name__ == "__main__":
    main()
