"""One loader for data/btc_1D.csv, whatever format it is in (unix seconds or ISO dates; Volume or volume)."""
from pathlib import Path
import pandas as pd

FILE = Path(__file__).resolve().parent.parent.parent / "data" / "btc_1D.csv"


def load(utc=False):
    d = pd.read_csv(FILE).rename(columns={"Volume": "volume"})
    t = d["time"]
    t = pd.to_datetime(t.astype("int64"), unit="s", utc=True) if pd.api.types.is_numeric_dtype(t) else pd.to_datetime(t, utc=True)
    d["time"] = t if utc else t.dt.tz_convert(None)
    d["ts"] = (t.astype("int64") // 10**9).astype("int64")
    closed = t + pd.Timedelta(days=1) <= pd.Timestamp.now(tz="UTC")     # drop a candle that is still forming
    return d[closed.values].reset_index(drop=True)
