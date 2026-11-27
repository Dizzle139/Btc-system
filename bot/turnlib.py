"""
Turn-watch calculator: the setup that passed out-of-sample testing (research/moves, steps 4-6), plus market context.
One set of definitions, used both to build the history of past alerts and by the live bot.

Input: closed daily Bitstamp candles (time = candle open, UTC) and optional market series (date -> close).
Every value for day i uses only data known at that day's close (00:00 UTC the next day).

Setup (bottoms; tops mirrored):
  trigger  close is the lowest close of the last 10 days
  items    sharp     close <= 0.90 x close 7 days earlier
           extended  close <= 0.80 x close 30 days earlier
           volume    Bitstamp volume >= 1.5 x average of the previous 20 days
           zone      day's low reaches an active bullish weekly FVG/OB (2x filter), close not below it
  alert    trigger + 2 or more items
"""
import numpy as np
import pandas as pd

from zones import find_fvgs, find_obs, dedupe

D1, W1 = pd.Timedelta(days=1), pd.Timedelta(days=7)
HALVINGS = pd.to_datetime(["2012-11-28", "2016-07-09", "2020-05-11", "2024-04-20"])   # next expected ~2028
PHASES = [("0-6 months after halving", 0, 182), ("6-18 months after halving", 182, 548),
          ("18-30 months after halving", 548, 913), ("30+ months after halving", 913, 99999)]


def weekly(d):
    return (d.set_index("time").resample("W-MON", label="left", closed="left")
            .agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}).dropna().reset_index())


def zone_arrays(d, W):
    """Weekly zones (2x filter) as arrays: side, bottom, top, known time, invalidated time (first weekly close through it)."""
    zs = dedupe(find_fvgs(W, 2.0) + find_obs(W, 2.0))
    side, bot, top, kt, inv = [], [], [], [], []
    for z in zs:
        k = W.time[z["known_idx"]] + W1
        iv = pd.Timestamp("2100-01-01", tz="UTC")
        for j in range(z["known_idx"] + 1, len(W)):
            if (z["side"] == "bull" and W.close[j] < z["bottom"]) or (z["side"] == "bear" and W.close[j] > z["top"]):
                iv = W.time[j] + W1
                break
        side.append(z["side"] == "bull"); bot.append(z["bottom"]); top.append(z["top"]); kt.append(k); inv.append(iv)
    return dict(bull=np.array(side), bot=np.array(bot), top=np.array(top),
                kt=pd.DatetimeIndex(kt).tz_convert(None).values if kt else np.array([], "datetime64[ns]"),
                inv=pd.DatetimeIndex(inv).tz_convert(None).values if inv else np.array([], "datetime64[ns]"))


def market(series, dates):
    """Align a date->value series to BTC candle dates (last known value)."""
    if series is None or len(series) == 0:
        return np.full(len(dates), np.nan)
    idx = pd.DatetimeIndex(pd.to_datetime(series.index))
    idx = (idx.tz_convert(None) if idx.tz is not None else idx).normalize()
    s = pd.Series(np.asarray(series.values, float), index=idx)
    s = s[~s.index.duplicated(keep="last")].sort_index().dropna()
    dates = pd.DatetimeIndex(dates)
    full = pd.date_range(min(s.index[0], dates[0]), max(s.index[-1], dates[-1]))
    return s.reindex(full).ffill().reindex(dates).values


def compute(d, mac=None):
    """d: closed daily candles (time tz-aware UTC). mac: dict of date-indexed pd.Series:
    dxy, vix, gold, spx, us10y, usdt_d (any may be missing). Returns one row per day."""
    mac = mac or {}
    d = d.reset_index(drop=True)
    n = len(d)
    O, H, L, C, V = (d[k].values.astype(float) for k in ("open", "high", "low", "close", "volume"))
    dates = d.time.dt.tz_convert(None).dt.normalize()
    out = pd.DataFrame({"date": dates.dt.strftime("%Y-%m-%d"), "close": C})
    lo10 = pd.Series(C).rolling(10).min().values
    hi10 = pd.Series(C).rolling(10).max().values
    out["new_low10"] = C <= lo10
    out["new_high10"] = C >= hi10
    c7, c30 = pd.Series(C).shift(7).values, pd.Series(C).shift(30).values
    out["chg7"] = (C / c7 - 1) * 100
    out["chg30"] = (C / c30 - 1) * 100
    v20 = pd.Series(V).shift(1).rolling(20).mean().values
    out["vol_x"] = V / v20
    out["sharp_b"], out["sharp_t"] = out.chg7 <= -10, out.chg7 >= 10
    out["ext_b"], out["ext_t"] = out.chg30 <= -20, out.chg30 >= 20
    out["volume"] = out.vol_x >= 1.5
    # weekly zones
    W = weekly(d)
    z = zone_arrays(d, W)
    t_open = d.time.dt.tz_convert(None).values
    zb, zt = np.zeros(n, bool), np.zeros(n, bool)
    if len(z["bot"]):
        for i in range(n):
            act = (z["kt"] <= t_open[i]) & (z["inv"] > t_open[i])
            zb[i] = bool((act & z["bull"] & (L[i] <= z["top"]) & (C[i] >= z["bot"])).any())
            zt[i] = bool((act & ~z["bull"] & (H[i] >= z["bot"]) & (C[i] <= z["top"])).any())
    out["zone_b"], out["zone_t"] = zb, zt
    out["items_b"] = out[["sharp_b", "ext_b", "volume", "zone_b"]].sum(axis=1)
    out["items_t"] = out[["sharp_t", "ext_t", "volume", "zone_t"]].sum(axis=1)
    out.loc[:29, ["items_b", "items_t"]] = 0
    out["alert_b"] = out.new_low10 & (out.items_b >= 2)
    out["alert_t"] = out.new_high10 & (out.items_t >= 2)
    # ---- context ----
    days_h = []
    for dt in dates:
        past = HALVINGS[HALVINGS <= dt]
        days_h.append((dt - past[-1]).days if len(past) else np.nan)
    out["days_since_halving"] = days_h
    out["phase"] = [next((p for p, a, b in PHASES if a <= x < b), None) if not np.isnan(x) else None for x in days_h]
    ath = pd.Series(C).cummax().values
    out["below_ath_pct"] = (1 - C / ath) * 100
    last_ath = pd.Series(np.where(C >= ath, np.arange(n), np.nan)).ffill().values
    out["days_since_ath"] = np.arange(n) - last_ath
    pc = np.r_[C[0], C[:-1]]
    tr = np.maximum(H - L, np.maximum(abs(H - pc), abs(L - pc)))
    atrp = pd.Series(tr).ewm(alpha=1 / 14, adjust=False).mean().values / C * 100
    out["range_pct"] = atrp
    out["range_squeezed"] = atrp <= pd.Series(atrp).rolling(180).quantile(0.2).values
    vol20, vol90 = pd.Series(V).rolling(20).mean().shift(1).values, pd.Series(V).rolling(90).mean().shift(1).values
    out["vol20_vs_90"] = vol20 / vol90
    out["volume_drying"] = vol20 < 0.7 * vol90
    p30, p60 = (C / c30 - 1), (c30 / pd.Series(C).shift(60).values - 1)
    out["decel_b"] = (p30 < 0) & (p60 < 0) & (abs(p30) < abs(p60))
    out["decel_t"] = (p30 > 0) & (p60 > 0) & (abs(p30) < abs(p60))
    for k in ("dxy", "vix", "gold", "spx", "us10y", "usdt_d"):
        out[k] = market(mac.get(k), dates)
    for k in ("dxy", "gold", "spx", "usdt_d"):
        a = out[k].values
        out[f"{k}_30d_pct"] = (a / pd.Series(a).shift(30).values - 1) * 100
    out["us10y_30d_chg"] = out.us10y - out.us10y.shift(30)
    e = pd.Series(out.spx.values).ffill().ewm(span=200, adjust=False).mean().values
    out["spx_above_200ema"] = np.where(np.isnan(out.spx.values), np.nan, out.spx.values > e)
    out["vix_30plus"] = np.where(np.isnan(out.vix.values), np.nan, out.vix.values >= 30)
    return out


# ---------------- what each part means (shown in every alert, never just a label) ----------------
ITEM_TEXT = {
    "b": {"sharp_b": "Sharp drop: {chg7:+.1f}% in 7 days (needs -10% or more)",
          "ext_b": "Extended drop: {chg30:+.1f}% in 30 days (needs -20% or more)",
          "volume": "Volume spike: {vol_x:.1f}x the 20-day average (needs 1.5x)",
          "zone_b": "In a bullish weekly FVG/order block (2x filter)"},
    "t": {"sharp_t": "Sharp rise: {chg7:+.1f}% in 7 days (needs +10% or more)",
          "ext_t": "Extended rise: {chg30:+.1f}% in 30 days (needs +20% or more)",
          "volume": "Volume spike: {vol_x:.1f}x the 20-day average (needs 1.5x)",
          "zone_t": "In a bearish weekly FVG/order block (2x filter)"},
}
BASE_KEYS = {"b": ["sharp_b", "ext_b", "volume", "zone_b"], "t": ["sharp_t", "ext_t", "volume", "zone_t"]}
# warnings that held on 2019-26 after being chosen on 2011-18 only (research/moves/grade_test.py)
WARN_KEYS = {"b": ["volume_drying", "dollar_up", "range_squeezed"], "t": ["range_squeezed", "volume_drying"]}


def flags(row, side):
    """Base items present and warnings present, for matching against history."""
    base = tuple(k for k in BASE_KEYS[side] if bool(row[k]))
    warn = []
    if bool(row["volume_drying"]):
        warn.append("volume_drying")
    if bool(row["range_squeezed"]):
        warn.append("range_squeezed")
    if side == "b" and not np.isnan(row["dxy_30d_pct"]) and row["dxy_30d_pct"] > 0:
        warn.append("dollar_up")
    return base, tuple(w for w in WARN_KEYS[side] if w in warn)
