"""FDA run-up (lab/RUNUP.md).

  python runner/runup.py dev
  python runner/runup.py final      # ONE shot on the hold-out, only after a dev PASS
"""
import argparse
import csv
import io
import json
import math
import os
import re
import sys
import time
import urllib.request
import zipfile
from collections import defaultdict
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.dirname(__file__))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LAB = os.path.join(ROOT, "lab")
DRUGSFDA = "https://download.open.fda.gov/drug/drugsfda/drug-drugsfda-0001-of-0001.json.zip"
CRL_API = "https://api.fda.gov/transparency/crl.json"
SEC_TICKERS = "https://www.sec.gov/files/company_tickers.json"

DEV_START, DEV_END, HOLDOUT_START = date(2016, 4, 1), date(2023, 12, 31), date(2024, 1, 1)
R = {"lead_days": 30, "min_price": 3.0, "min_dvol": 1_000_000, "max_dvol": 200_000_000,
     "cooldown_days": 60, "cost_bps": 30}

ABBR = {"pharms": "pharmaceuticals", "pharma": "pharmaceuticals", "pharmaceutical": "pharmaceuticals",
        "therap": "therapeutics", "theraps": "therapeutics", "labs": "laboratories", "lab": "laboratories",
        "intl": "international", "biosci": "biosciences", "biosciences": "biosciences", "hlthcare": "healthcare",
        "tech": "technologies", "techs": "technologies", "technology": "technologies", "corp": "", "corporation": "",
        "inc": "", "co": "", "ltd": "", "plc": "", "llc": "", "sa": "", "ag": "", "nv": "", "lp": "",
        "holdings": "", "holding": "", "the": "", "us": "", "usa": "", "limited": "", "company": "",
        "group": "", "ab": "", "as": "", "se": "", "kk": "", "gmbh": ""}


def get(url, ua=None, tries=4):
    h = {"User-Agent": ua or "orb-paper-test research"}
    for n in range(tries):
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=180).read()
        except Exception as e:
            if "404" in str(e):
                return None
            time.sleep(3 * (n + 1))
    raise RuntimeError(f"kan {url} niet ophalen")


def norm(name):
    w = re.sub(r"[^a-z0-9 ]", " ", (name or "").split("/")[0].lower()).split()
    w = [ABBR.get(x, x) for x in w]
    return " ".join(x for x in w if x)


def d8(s):
    try:
        return datetime.strptime(str(s)[:10].replace("-", "")[:8], "%Y%m%d").date()
    except ValueError:
        return None


# ---------------- events ----------------
def approvals():
    z = zipfile.ZipFile(io.BytesIO(get(DRUGSFDA)))
    data = json.load(z.open(z.namelist()[0]))["results"]
    ev = []
    for app in data:
        num = app.get("application_number", "")
        if not (num.startswith("NDA") or num.startswith("BLA")):
            continue
        for s in app.get("submissions", []):
            if s.get("submission_type") == "ORIG" and s.get("submission_status") == "AP":
                d = d8(s.get("submission_status_date"))
                if d:
                    ev.append({"date": d, "sponsor": app.get("sponsor_name", ""), "app": num, "kind": "approval"})
    print(f"goedkeuringen NDA/BLA ORIG: {len(ev)}", file=sys.stderr)
    return ev


def crls():
    out, skip, first = [], 0, None
    while True:
        raw = get(f"{CRL_API}?limit=1000&skip={skip}")
        if not raw:
            break
        rows = json.loads(raw).get("results", [])
        if not rows:
            break
        if first is None:
            first = rows[0]
            print("CRL-velden:", sorted(first.keys()), file=sys.stderr)
        for r in rows:
            name = r.get("company_name") or r.get("applicant") or r.get("sponsor_name") or r.get("company")
            d = d8(r.get("letter_date") or r.get("date") or r.get("crl_date") or r.get("letter_issue_date") or "")
            if name and d:
                out.append({"date": d, "sponsor": name, "app": r.get("application_number", ""), "kind": "crl"})
        skip += 1000
        if skip > 25000:
            break
        time.sleep(0.5)
    print(f"CRL's: {len(out)}", file=sys.stderr)
    return out


def tickers(ua):
    j = json.loads(get(SEC_TICKERS, ua))
    exact, first2 = {}, defaultdict(set)
    for r in j.values():
        n = norm(r["title"])
        exact.setdefault(n, r["ticker"])
        w = n.split()
        if len(w) >= 2:
            first2[" ".join(w[:2])].add(r["ticker"])
    return exact, first2


def match(ev, exact, first2):
    hit, miss = [], defaultdict(int)
    for e in ev:
        n = norm(e["sponsor"])
        t = exact.get(n)
        if not t:
            w = n.split()
            cand = first2.get(" ".join(w[:2])) if len(w) >= 2 else None
            t = next(iter(cand)) if cand and len(cand) == 1 else None
        if t and t.replace("-", "").isalpha():
            hit.append({**e, "sym": t.replace("-", ".")})
        else:
            miss[e["sponsor"]] += 1
    return hit, miss


# ---------------- prices & trades ----------------
def prices(symbols, end):
    import alpaca
    out = {}
    syms = sorted(set(symbols) | {"SPY", "XBI"})
    for i in range(0, len(syms), 100):
        got = alpaca.bars(syms[i:i + 100], "2015-10-01T00:00:00Z", end.isoformat() + "T00:00:00Z",
                          timeframe="1Day", feed="sip", adjustment="all")
        for s, bars in got.items():
            if bars:
                out[s] = {b["t"].date(): (b["o"], b["c"], b["v"]) for b in bars if b["t"].date() < end}
    return out


def trade(e, px):
    p = px.get(e["sym"])
    if not p:
        return None, "geen koersdata"
    days = sorted(p)
    on = [i for i, d in enumerate(days) if d >= e["date"]]
    if not on or (days[on[0]] - e["date"]).days > 5:
        return None, "geen koersdata"
    T = on[0]
    k, x = T - R["lead_days"], T - 1
    if k < 21:
        return None, "geen koersdata"
    prev_c = p[days[k - 1]][1]
    dvol = sum(p[d][1] * p[d][2] for d in days[k - 20:k]) / 20
    if prev_c < R["min_price"]:
        return None, "koers < $3"
    if not R["min_dvol"] <= dvol <= R["max_dvol"]:
        return None, "te klein of te groot"
    de, dx = days[k], days[x]
    c = R["cost_bps"] / 10000
    net = p[dx][1] * (1 - c) / (p[de][0] * (1 + c)) - 1

    def bench(s):
        b = px[s]
        return b[dx][1] / b[de][0] - 1 if de in b and dx in b else 0.0
    xbi, spy = bench("XBI"), bench("SPY")
    return {"decision": e["date"].isoformat(), "sym": e["sym"], "kind": e["kind"], "sponsor": e["sponsor"],
            "entry": de.isoformat(), "exit": dx.isoformat(), "net": round(net, 5),
            "xbi": round(xbi, 5), "spy": round(spy, 5),
            "ex_xbi": round(net - xbi, 5), "ex_spy": round(net - spy, 5)}, None


def stats(tr, key):
    n = len(tr)
    if n < 2:
        return {"n": n}
    v = [t[key] for t in tr]
    m = sum(v) / n
    sd = math.sqrt(sum((x - m) ** 2 for x in v) / (n - 1))
    return {"n": n, "mean_pct": round(m * 100, 2), "median_pct": round(sorted(v)[n // 2] * 100, 2),
            "t_stat": round(m / (sd / math.sqrt(n)), 2) if sd else None,
            "positive_pct": round(sum(1 for x in v if x > 0) / n * 100, 1)}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["dev", "final"])
    a = ap.parse_args(argv)
    ua = os.environ.get("SEC_USER_AGENT") or sys.exit("SEC_USER_AGENT ontbreekt")
    if a.mode == "dev":
        frm, to, p_end = DEV_START, DEV_END, HOLDOUT_START
        path = os.path.join(LAB, "runup-dev.json")
    else:
        path = os.path.join(LAB, "runup-final.json")
        if os.path.exists(path):
            sys.exit("De eindtoets is al gedaan. Eén keer = één keer.")
        if json.load(open(os.path.join(LAB, "runup-dev.json"))).get("verdict") != "PASS":
            sys.exit("Dev-fase niet gehaald: geen eindtoets (lab/RUNUP.md).")
        frm, to, p_end = HOLDOUT_START, date.today(), date.today()

    ev = [e for e in approvals() + crls() if frm <= e["date"] <= to]
    exact, first2 = tickers(ua)
    hit, miss = match(ev, exact, first2)
    hit.sort(key=lambda e: (e["sym"], e["date"]))
    dedup, last = [], {}
    for e in hit:
        if e["sym"] in last and (e["date"] - last[e["sym"]]).days < R["cooldown_days"]:
            continue
        dedup.append(e)
        last[e["sym"]] = e["date"]
    px = prices([e["sym"] for e in dedup], p_end)
    trades, skipped = [], defaultdict(int)
    for e in sorted(dedup, key=lambda e: e["date"]):
        t, why = trade(e, px)
        if t:
            trades.append(t)
        else:
            skipped[why] += 1
    res = {"mode": a.mode, "rules": R, "events": len(ev), "matched": len(hit),
           "match_rate_pct": round(len(hit) / max(1, len(ev)) * 100, 1),
           "after_cooldown": len(dedup), "skipped": dict(skipped),
           "by_kind": {k: sum(1 for t in trades if t["kind"] == k) for k in ("approval", "crl")},
           "net": stats(trades, "net"), "excess_vs_xbi": stats(trades, "ex_xbi"),
           "excess_vs_spy": stats(trades, "ex_spy"),
           "crl_only_excess_vs_xbi": stats([t for t in trades if t["kind"] == "crl"], "ex_xbi"),
           "top_unmatched_sponsors": sorted(miss.items(), key=lambda x: -x[1])[:25]}
    n, x = res["net"], res["excess_vs_xbi"]
    if a.mode == "dev":
        ok = n.get("mean_pct", 0) > 0 and x.get("mean_pct", 0) > 0 and (x.get("t_stat") or 0) >= 2
    else:
        ok = n.get("mean_pct", 0) > 0 and x.get("mean_pct", 0) > 0
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
