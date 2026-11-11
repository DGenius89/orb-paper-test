"""Minimal Alpaca REST client, standard library only.

Keys come from the environment (GitHub Secrets): ALPACA_API_KEY, ALPACA_SECRET_KEY.
The trading base URL is hard-wired to the PAPER endpoint: this code cannot trade live.
"""
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime

from strategy import ET

PAPER = "https://paper-api.alpaca.markets"
DATA = "https://data.alpaca.markets"


def _headers():
    k, s = os.environ.get("ALPACA_API_KEY"), os.environ.get("ALPACA_SECRET_KEY")
    if not k or not s:
        raise SystemExit("ALPACA_API_KEY / ALPACA_SECRET_KEY ontbreken (zet ze als GitHub Secrets).")
    return {"APCA-API-KEY-ID": k, "APCA-API-SECRET-KEY": s, "Accept": "application/json"}


def call(method, base, path, params=None, body=None, tries=4):
    url = base + path + ("?" + urllib.parse.urlencode(params) if params else "")
    data = json.dumps(body).encode() if body is not None else None
    h = _headers()
    if data:
        h["Content-Type"] = "application/json"
    for n in range(tries):
        req = urllib.request.Request(url, data=data, headers=h, method=method)
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                raw = r.read()
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as e:
            msg = e.read().decode("utf-8", "replace")
            if e.code == 429 or e.code >= 500:
                time.sleep(2 ** n)
                continue
            raise RuntimeError(f"{method} {path} -> {e.code}: {msg}")
        except urllib.error.URLError:
            time.sleep(2 ** n)
    raise RuntimeError(f"{method} {path}: gave up after {tries} tries")


def trade(method, path, params=None, body=None):
    return call(method, PAPER, path, params, body)


def bars(symbols, start, end, timeframe="5Min", feed="iex"):
    """{symbol: [bar dicts in ET]} over [start, end), paginated."""
    out = {s: [] for s in symbols}
    token = None
    while True:
        p = {"symbols": ",".join(symbols), "timeframe": timeframe, "start": start, "end": end,
             "feed": feed, "limit": 10000, "adjustment": "raw"}
        if token:
            p["page_token"] = token
        r = call("GET", DATA, "/v2/stocks/bars", p)
        for sym, rows in (r.get("bars") or {}).items():
            for x in rows:
                t = datetime.fromisoformat(x["t"].replace("Z", "+00:00")).astimezone(ET)
                out[sym].append({"t": t, "o": x["o"], "h": x["h"], "l": x["l"], "c": x["c"], "v": x["v"]})
        token = r.get("next_page_token")
        if not token:
            return out
