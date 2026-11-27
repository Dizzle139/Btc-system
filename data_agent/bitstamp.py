"""Public Bitstamp candles (same source as BITSTAMP:BTCUSD on TradingView). No keys, no connectors."""
import time
import pandas as pd
import requests

URL = "https://www.bitstamp.net/api/v2/ohlc/btcusd/"
T = 20


def _get(step, start=None, limit=1000):
    p = {"step": step, "limit": limit}
    if start is not None:
        p["start"] = int(start)
    r = requests.get(URL, params=p, timeout=T)
    r.raise_for_status()
    rows = r.json()["data"]["ohlc"]
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df = df.rename(columns={"timestamp": "time"})
    df["time"] = pd.to_datetime(df["time"].astype("int64"), unit="s", utc=True)
    for c in ["open", "high", "low", "close", "volume"]:
        df[c] = df[c].astype(float)
    return df[["time", "open", "high", "low", "close", "volume"]]


def daily_history(since="2016-01-01"):
    """Pages through Bitstamp daily candles from `since` to now."""
    start = pd.Timestamp(since, tz="UTC").timestamp()
    parts = []
    while True:
        df = _get(86400, start=start)
        if df.empty:
            break
        parts.append(df)
        last = df.time.iloc[-1].timestamp()
        # pages can be short in early years, so a short page does NOT mean the end; stop only at the present
        if last <= start - 86400 or last >= time.time() - 2 * 86400:
            break
        start = last + 86400
        time.sleep(0.3)
    return pd.concat(parts).drop_duplicates("time").sort_values("time").reset_index(drop=True)


def h4_recent():
    return _get(14400, limit=1000).sort_values("time").reset_index(drop=True)


def kraken_last():
    r = requests.get("https://api.kraken.com/0/public/Ticker", params={"pair": "XBTUSD"}, timeout=T)
    return float(next(iter(r.json()["result"].values()))["c"][0])


def from_csv(daily_csv, h4_csv):
    """Offline mode: TradingView exports (time in unix seconds)."""
    out = []
    for p in (daily_csv, h4_csv):
        d = pd.read_csv(p)
        d = d.rename(columns={"Volume": "volume"})
        if not pd.api.types.is_datetime64_any_dtype(d["time"]):
            try:
                d["time"] = pd.to_datetime(d["time"].astype("int64"), unit="s", utc=True)
            except (ValueError, TypeError):
                d["time"] = pd.to_datetime(d["time"], utc=True)
        out.append(d[["time", "open", "high", "low", "close", "volume"]].sort_values("time").reset_index(drop=True))
    return out
