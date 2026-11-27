#!/usr/bin/env python3
"""
Data agent: downloads everything the research and bot need into data/.
Runs on GitHub Actions (its servers can reach these sites; Claude's workspace cannot).

  Bitstamp (same feed as BITSTAMP:BTCUSD on TradingView)
    data/btc_1D.csv            daily candles from 2011
    data/btc_4H.csv            4H candles from 2014
  Binance public archive (data.binance.vision) — verify on first run
    data/binance_spot_1D.csv   spot BTCUSDT daily incl. taker-buy volume (real buy vs sell pressure)
    data/binance_perp_1D.csv   USDT-M perpetual daily incl. taker-buy volume
    data/binance_oi_1D.csv     open interest (last reading of each UTC day) + long/short ratios
    data/binance_funding.csv   funding rate, every funding event
  Macro / other markets (added Nov 27, 2026)
    data/fred_<SERIES>.csv     FRED (St. Louis Fed, free, no key): broad US dollar index, 10-year yield,
                               Fed funds rate, M2 money supply (weekly), VIX
    data/yahoo_<symbol>.csv    Yahoo Finance daily (Stooq refused automated downloads): S&P 500, gold futures,
                               US dollar index (DXY), VIX, 10-year yield
    data/btc_dominance.csv     BGeometrics free API: BTC dominance, daily from Apr 2013
    data/usdt_supply.csv       DefiLlama stablecoins API (free, no key): USDT circulating supply in USD, daily
    data/btc_marketcap.csv     Coin Metrics community API (free, no key): BTC market cap (supply x price), daily
    data/fed_funds.csv         New York Fed markets API (free, no key): effective federal funds rate, daily
    data/fear_greed.csv        alternative.me (free, no key): Crypto Fear & Greed Index, daily from 2018
Every file gets a validation line in data/DATA_REPORT.md (rows, range, gaps).
"""
import io, time, zipfile, sys
from datetime import date, timedelta
from pathlib import Path
import pandas as pd
import requests

OUT = Path(__file__).resolve().parent.parent / "data"
OUT.mkdir(exist_ok=True)
S = requests.Session()
S.headers["User-Agent"] = "btc-system-data-agent"
VISION = "https://data.binance.vision/data"
KCOLS = ["open_time", "open", "high", "low", "close", "volume", "close_time", "quote_volume", "trades",
         "taker_buy_volume", "taker_buy_quote_volume", "ignore"]
report = []


def note(name, df, step=None):
    t = df["time"]
    gaps = int((t.diff().dropna() != step).sum()) if step is not None else "n/a"
    report.append(f"| {name} | {len(df)} | {t.iloc[0]} | {t.iloc[-1]} | {gaps} |")
    print(f"{name}: {len(df)} rows {t.iloc[0]} -> {t.iloc[-1]} gaps={gaps}")


# ---------------- Bitstamp ----------------
def bitstamp(step, since):
    start, parts = pd.Timestamp(since, tz="UTC").timestamp(), []
    while True:
        r = S.get("https://www.bitstamp.net/api/v2/ohlc/btcusd/",
                  params={"step": step, "limit": 1000, "start": int(start)}, timeout=30)
        r.raise_for_status()
        rows = r.json()["data"]["ohlc"]
        if not rows:
            break
        df = pd.DataFrame(rows).astype(float)
        parts.append(df)
        last = df["timestamp"].iloc[-1]
        if last <= start - step or last >= time.time() - 2 * step:   # reached the present (pages can be short in early years)
            break
        start = last + step
        time.sleep(0.25)
    d = pd.concat(parts).drop_duplicates("timestamp").sort_values("timestamp")
    d = d.rename(columns={"timestamp": "time"})[["time", "open", "high", "low", "close", "volume"]]
    d["time"] = pd.to_datetime(d["time"].astype("int64"), unit="s", utc=True)
    return d.reset_index(drop=True)


# ---------------- Binance archive ----------------
def read_zip(url):
    r = S.get(url, timeout=60)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        raw = z.read(z.namelist()[0]).decode()
    first = raw.splitlines()[0]
    has_header = any(ch.isalpha() for ch in first.split(",")[0])
    return pd.read_csv(io.StringIO(raw), header=0 if has_header else None)


def months(start, end):
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        yield f"{y}-{m:02d}"
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)


def klines(market, symbol, start):
    base = f"{VISION}/spot/monthly/klines" if market == "spot" else f"{VISION}/futures/um/monthly/klines"
    parts = []
    for ym in months(start, date.today() - timedelta(days=32)):
        df = read_zip(f"{base}/{symbol}/1d/{symbol}-1d-{ym}.zip")
        if df is None:
            continue
        df = df.iloc[:, :12]
        df.columns = KCOLS
        parts.append(df)
        time.sleep(0.1)
    d = pd.concat(parts)
    ot = d["open_time"].astype("int64")
    ot = ot.where(ot < 10**14, ot // 1000)            # spot files from 2025 use microseconds; convert row by row
    d["time"] = pd.to_datetime(ot, unit="ms", utc=True)
    d = d.drop_duplicates("time").sort_values("time")
    keep = ["time", "open", "high", "low", "close", "volume", "quote_volume", "taker_buy_volume", "taker_buy_quote_volume"]
    return d[keep].reset_index(drop=True)


def open_interest(symbol, start):
    parts, day = [], start
    while day <= date.today() - timedelta(days=2):
        df = read_zip(f"{VISION}/futures/um/daily/metrics/{symbol}/{symbol}-metrics-{day:%Y-%m-%d}.zip")
        if df is not None and len(df):
            df["create_time"] = pd.to_datetime(df["create_time"], utc=True)
            parts.append(df.sort_values("create_time").tail(1))   # last 5-minute reading of the day
        day += timedelta(days=1)
        time.sleep(0.05)
    d = pd.concat(parts)
    d["time"] = d["create_time"].dt.normalize()
    return d.drop(columns=["create_time"]).reset_index(drop=True)


def funding(symbol, start):
    parts = []
    for ym in months(start, date.today() - timedelta(days=32)):
        df = read_zip(f"{VISION}/futures/um/monthly/fundingRate/{symbol}/{symbol}-fundingRate-{ym}.zip")
        if df is not None:
            parts.append(df)
    d = pd.concat(parts)
    d["time"] = pd.to_datetime(d.iloc[:, 0].astype("int64"), unit="ms", utc=True)
    return d.sort_values("time").reset_index(drop=True)


# ---------------- macro / other markets ----------------
FRED = {"DTWEXBGS": "broad US dollar index", "DGS10": "US 10-year yield", "DFF": "Fed funds rate",
        "WM2NS": "M2 money supply (weekly)", "VIXCLS": "VIX"}
YAHOO = {"^GSPC": "S&P 500", "GC=F": "gold futures", "DX-Y.NYB": "US dollar index (DXY)", "^VIX": "VIX", "^TNX": "US 10-year yield x10"}


def get(url, tries=3, **kw):
    """GET with retries and a long timeout (FRED timed out at 60 s from GitHub's servers)."""
    for k in range(tries):
        try:
            r = S.get(url, timeout=180, **kw)
            r.raise_for_status()
            return r
        except Exception:
            if k == tries - 1:
                raise
            time.sleep(10 * (k + 1))


def fred(series):
    r = get("https://fred.stlouisfed.org/graph/fredgraph.csv", params={"id": series})
    d = pd.read_csv(io.StringIO(r.text))
    d.columns = ["time", "value"]
    d["time"] = pd.to_datetime(d.time)
    d["value"] = pd.to_numeric(d.value, errors="coerce")       # FRED marks holidays with "."
    d = d.dropna()
    if len(d) < 100:
        raise RuntimeError(f"only {len(d)} rows")
    return d


def yahoo(symbol):
    r = get(f"https://query2.finance.yahoo.com/v8/finance/chart/{symbol}",
            params={"period1": 1262304000, "period2": int(time.time()), "interval": "1d"},
            headers={"User-Agent": "Mozilla/5.0"})
    j = r.json()["chart"]["result"][0]
    q = j["indicators"]["quote"][0]
    d = pd.DataFrame({"time": pd.to_datetime(j["timestamp"], unit="s").normalize(), "open": q["open"], "high": q["high"],
                      "low": q["low"], "close": q["close"], "volume": q.get("volume")}).dropna(subset=["close"])
    d = d.drop_duplicates("time", keep="last")
    if len(d) < 100:
        raise RuntimeError(f"only {len(d)} rows")
    return d


def dominance():
    r = get("https://bitcoin-data.com/v1/bitcoin-dominance/csv")
    d = pd.read_csv(io.StringIO(r.text))
    tcol = [c for c in d.columns if c.lower() in ("d", "date", "day", "time", "unixts")][0]
    d = d.rename(columns={tcol: "time"})
    d["time"] = pd.to_datetime(d.time, errors="coerce")
    d = d.dropna(subset=["time"]).sort_values("time")
    if len(d) < 100:
        raise RuntimeError(f"only {len(d)} rows; columns {list(d.columns)}")
    return d


def usdt_supply():
    r = get("https://stablecoins.llama.fi/stablecoincharts/all", params={"stablecoin": 1})   # id 1 = Tether (USDT)
    rows = r.json()
    d = pd.DataFrame({"time": pd.to_datetime([int(x["date"]) for x in rows], unit="s"),
                      "usdt_usd": [(x.get("totalCirculatingUSD") or {}).get("peggedUSD") for x in rows]}).dropna()
    if len(d) < 100:
        raise RuntimeError(f"only {len(d)} rows")
    return d


def btc_marketcap():
    url = "https://community-api.coinmetrics.io/v4/timeseries/asset-metrics"
    params = {"assets": "btc", "metrics": "CapMrktCurUSD,SplyCur,PriceUSD", "frequency": "1d", "page_size": 10000,
              "start_time": "2010-07-18"}
    rows, nxt = [], None
    while True:
        r = get(nxt) if nxt else get(url, params=params)
        j = r.json()
        rows += j.get("data", [])
        nxt = j.get("next_page_url")
        if not nxt:
            break
        time.sleep(1)
    d = pd.DataFrame(rows)
    d = d.rename(columns={"CapMrktCurUSD": "btc_mcap_usd", "SplyCur": "btc_supply", "PriceUSD": "price_usd"})
    d["time"] = pd.to_datetime(d.time).dt.tz_localize(None)
    for c in ("btc_mcap_usd", "btc_supply", "price_usd"):
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d = d[["time", "btc_mcap_usd", "btc_supply", "price_usd"]].dropna()
    if len(d) < 100:
        raise RuntimeError(f"only {len(d)} rows")
    return d


def fed_funds():
    parts = []
    for y in range(2010, pd.Timestamp.now().year + 1):           # one request per year keeps replies small
        r = get("https://markets.newyorkfed.org/api/rates/unsecured/effr/search.json",
                params={"startDate": f"{y}-01-01", "endDate": f"{y}-12-31"})
        for x in r.json().get("refRates", []):
            parts.append((x["effectiveDate"], x.get("percentRate")))
        time.sleep(0.5)
    d = pd.DataFrame(parts, columns=["time", "rate"]).dropna()
    d["time"] = pd.to_datetime(d.time)
    d = d.drop_duplicates("time").sort_values("time")
    if len(d) < 100:
        raise RuntimeError(f"only {len(d)} rows")
    return d


def fear_greed():
    r = get("https://api.alternative.me/fng/", params={"limit": 0, "format": "json"})
    rows = r.json()["data"]
    d = pd.DataFrame({"time": pd.to_datetime([int(x["timestamp"]) for x in rows], unit="s"),
                      "value": [int(x["value"]) for x in rows], "label": [x["value_classification"] for x in rows]})
    d = d.sort_values("time")
    if len(d) < 100:
        raise RuntimeError(f"only {len(d)} rows")
    return d


def run(name, fn, path, step=None):
    try:
        d = fn()
        if (OUT / path).exists():   # never replace a file with a shorter one
            prev = pd.read_csv(OUT / path)
            if len(d) < len(prev):
                raise RuntimeError(f"new download has {len(d)} rows, existing file has {len(prev)}: kept the existing file")
        d.to_csv(OUT / path, index=False)
        note(path, d, step)
    except Exception as e:  # keep going; the report shows what failed
        report.append(f"| {path} | FAILED: {e} | | | |")
        print(f"{path} FAILED: {e}", file=sys.stderr)


if __name__ == "__main__":
  only = sys.argv[1] if len(sys.argv) > 1 else "all"      # "macro" = only the macro/other-market files
  if only != "macro":
    run("bitstamp 1D", lambda: bitstamp(86400, "2011-08-01"), "btc_1D.csv", pd.Timedelta(days=1))
    run("bitstamp 4H", lambda: bitstamp(14400, "2014-01-01"), "btc_4H.csv", pd.Timedelta(hours=4))
    run("binance spot", lambda: klines("spot", "BTCUSDT", date(2017, 8, 1)), "binance_spot_1D.csv", pd.Timedelta(days=1))
    run("binance perp", lambda: klines("perp", "BTCUSDT", date(2019, 9, 1)), "binance_perp_1D.csv", pd.Timedelta(days=1))
    run("binance OI", lambda: open_interest("BTCUSDT", date(2021, 12, 1)), "binance_oi_1D.csv", pd.Timedelta(days=1))
    run("binance funding", lambda: funding("BTCUSDT", date(2019, 9, 1)), "binance_funding.csv")
  for sid in FRED:
    run(f"FRED {sid}", lambda sid=sid: fred(sid), f"fred_{sid}.csv")
  for sym in YAHOO:
    run(f"Yahoo {sym}", lambda sym=sym: yahoo(sym), f"yahoo_{sym.replace('^', '').replace('=', '_').replace('.', '_').replace('-', '_')}.csv")
  run("BTC dominance", dominance, "btc_dominance.csv")
  run("USDT supply", usdt_supply, "usdt_supply.csv")
  run("BTC market cap", btc_marketcap, "btc_marketcap.csv")
  run("Fed funds", fed_funds, "fed_funds.csv")
  run("Fear & Greed", fear_greed, "fear_greed.csv")
  (OUT / "DATA_REPORT.md").write_text(
      f"# Data report ({pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC)\n\n| file | rows | from | to | gaps |\n|---|---|---|---|---|\n"
      + "\n".join(report) + "\n")
