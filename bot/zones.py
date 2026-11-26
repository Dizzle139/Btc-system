"""
Zone detector — spec v0.1 (agreed with user 2026-11-25)

FVG  : 3-candle gap. Bullish: low[i+1] > high[i-1]  -> zone [high[i-1], low[i+1]]
       Bearish: high[i+1] < low[i-1]                -> zone [high[i+1], low[i-1]]
       Big-move filter: body of middle candle i >= X * avg body of previous 20 candles.
       Known (usable) at close of candle i+1.
OB   : Last opposite-colour candle (within 5 bars) before a displacement candle j.
       Displacement = body >= X * avg body AND (breaks structure OR leaves an FVG).
       Break of structure = close beyond the last confirmed swing high/low
       (swing = pivot with 2 bars each side; confirmed only after those 2 bars close).
       Zone = BODY of the OB candle (user choice Q5).
       Known at close of j (BOS) or j+1 (FVG).
No look-ahead anywhere: every zone carries `known_idx`, the first bar it can be used.
"""
import numpy as np
import pandas as pd

AVG_BODY_LEN = 20
OB_LOOKBACK = 5
PIVOT = 2


def load(path, drop_last=True):
    d = pd.read_csv(path)
    d = d.rename(columns={"Volume": "volume"})
    d["time"] = pd.to_datetime(d["time"], unit="s", utc=True)
    d = d[["time", "open", "high", "low", "close", "volume"]].reset_index(drop=True)
    if drop_last:  # last row is the still-open candle
        d = d.iloc[:-1].reset_index(drop=True)
    return d


def atr(d, n=14):
    pc = d["close"].shift()
    tr = pd.concat([d.high - d.low, (d.high - pc).abs(), (d.low - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean()


def find_fvgs(d, X):
    body = (d.close - d.open).abs()
    avg = body.shift(1).rolling(AVG_BODY_LEN).mean()
    out = []
    for i in range(1, len(d) - 1):
        if np.isnan(avg[i]) or body[i] < X * avg[i]:
            continue
        if d.low[i + 1] > d.high[i - 1] and d.close[i] > d.open[i]:
            out.append(dict(kind="FVG", side="bull", bottom=d.high[i - 1], top=d.low[i + 1],
                            form_idx=i, known_idx=i + 1))
        elif d.high[i + 1] < d.low[i - 1] and d.close[i] < d.open[i]:
            out.append(dict(kind="FVG", side="bear", bottom=d.high[i + 1], top=d.low[i - 1],
                            form_idx=i, known_idx=i + 1))
    return out


def confirmed_pivots(d):
    """pivot_hi[k] = price of last swing high confirmed by close of bar k (else NaN carried)."""
    n = len(d)
    last_hi = np.full(n, np.nan)
    last_lo = np.full(n, np.nan)
    cur_hi = cur_lo = np.nan
    for k in range(n):
        p = k - PIVOT  # candidate pivot confirmed at bar k
        if p >= PIVOT:
            win_h = d.high[p - PIVOT:p + PIVOT + 1]
            win_l = d.low[p - PIVOT:p + PIVOT + 1]
            if d.high[p] == win_h.max():
                cur_hi = d.high[p]
            if d.low[p] == win_l.min():
                cur_lo = d.low[p]
        last_hi[k], last_lo[k] = cur_hi, cur_lo
    return last_hi, last_lo


def find_obs(d, X):
    body = (d.close - d.open).abs()
    avg = body.shift(1).rolling(AVG_BODY_LEN).mean()
    piv_hi, piv_lo = confirmed_pivots(d)
    out = []
    for j in range(1, len(d) - 1):
        if np.isnan(avg[j]) or body[j] < X * avg[j]:
            continue
        bull = d.close[j] > d.open[j]
        prev_hi, prev_lo = piv_hi[j - 1], piv_lo[j - 1]  # structure known before j
        if bull:
            bos = not np.isnan(prev_hi) and d.close[j] > prev_hi
            fvg = d.low[j + 1] > d.high[j - 1]
        else:
            bos = not np.isnan(prev_lo) and d.close[j] < prev_lo
            fvg = d.high[j + 1] < d.low[j - 1]
        if not (bos or fvg):
            continue
        # last opposite-colour candle before j
        for k in range(j - 1, max(j - 1 - OB_LOOKBACK, -1), -1):
            opp = d.close[k] < d.open[k] if bull else d.close[k] > d.open[k]
            if opp:
                lo, hi = sorted([d.open[k], d.close[k]])
                out.append(dict(kind="OB", side="bull" if bull else "bear", bottom=lo, top=hi,
                                form_idx=k, known_idx=j if bos else j + 1,
                                trigger="BOS" if bos else "FVG"))
                break
    return out


def evaluate(d, zones, atr_s, horizon=50, hold_atr=1.0):
    """
    For each zone, from known_idx+1 onward:
      touched  : bull zone -> low <= top ; bear zone -> high >= bottom
      held     : after touch, price moves hold_atr * ATR beyond the near edge (away from zone)
                 BEFORE any candle CLOSES through the far edge.
      failed   : a close through the far edge comes first.
    Same-candle ambiguity -> counted as failed (conservative).
    """
    res = []
    n = len(d)
    for z in zones:
        s = z["known_idx"] + 1
        a = atr_s[z["known_idx"]]
        touch = None
        for t in range(s, min(n, s + horizon)):
            if (z["side"] == "bull" and d.low[t] <= z["top"]) or (z["side"] == "bear" and d.high[t] >= z["bottom"]):
                touch = t
                break
        outcome = "untouched" if touch is None else "open"
        if touch is not None:
            for t in range(touch, n):
                if z["side"] == "bull":
                    fail = d.close[t] < z["bottom"]
                    win = t > touch and d.high[t] >= z["top"] + hold_atr * a
                else:
                    fail = d.close[t] > z["top"]
                    win = t > touch and d.low[t] <= z["bottom"] - hold_atr * a
                if fail:
                    outcome = "failed"
                    break
                if win:
                    outcome = "held"
                    break
        res.append({**z, "touch_idx": touch, "bars_to_touch": None if touch is None else touch - z["known_idx"],
                    "outcome": outcome})
    return pd.DataFrame(res)


def random_baseline(d, zones, atr_s, rng, reps=20, horizon=50, hold_atr=1.0):
    """Same zones (same side, same % distance from price, same % width) dropped at random bars."""
    fakes = []
    n = len(d)
    for z in zones:
        ref = d.close[z["known_idx"]]
        top_off = z["top"] / ref - 1
        bot_off = z["bottom"] / ref - 1
        for _ in range(reps):
            k = int(rng.integers(AVG_BODY_LEN + 2, n - 2))
            c = d.close[k]
            fakes.append(dict(kind="RANDOM", side=z["side"], top=c * (1 + top_off), bottom=c * (1 + bot_off),
                              form_idx=k, known_idx=k))
    return evaluate(d, fakes, atr_s, horizon, hold_atr)


def summarize(df):
    n = len(df)
    if n == 0:
        return dict(n=0)
    touched = df[df.outcome != "untouched"]
    resolved = touched[touched.outcome.isin(["held", "failed"])]
    return dict(
        n=n,
        touched_pct=round(100 * len(touched) / n, 1),
        held_pct_of_resolved=round(100 * (resolved.outcome == "held").mean(), 1) if len(resolved) else None,
        resolved=len(resolved),
        median_bars_to_touch=None if touched.empty else float(touched.bars_to_touch.median()),
    )


# ---------------- Volume profile ----------------
def volume_profile(d, start_idx, end_idx, bins=60):
    """Spread each candle's volume evenly across its high-low range. Returns bin centers & volume."""
    w = d.iloc[start_idx:end_idx + 1]
    lo, hi = w.low.min(), w.high.max()
    edges = np.linspace(lo, hi, bins + 1)
    vol = np.zeros(bins)
    for _, r in w.iterrows():
        rng_ = max(r.high - r.low, 1e-9)
        ov = np.clip(np.minimum(edges[1:], r.high) - np.maximum(edges[:-1], r.low), 0, None)
        vol += r.volume * ov / rng_
    centers = (edges[:-1] + edges[1:]) / 2
    return centers, vol, edges


def hvn_zones(d, start_idx, end_idx, bins=60, top_pct=0.15):
    centers, vol, edges = volume_profile(d, start_idx, end_idx, bins)
    poc = centers[vol.argmax()]
    thr = np.quantile(vol, 1 - top_pct)
    zones, cur = [], None
    for i in range(bins):
        if vol[i] >= thr:
            cur = [edges[i], edges[i + 1]] if cur is None else [cur[0], edges[i + 1]]
        elif cur is not None:
            zones.append(cur)
            cur = None
    if cur is not None:
        zones.append(cur)
    return poc, zones


def dedupe(zs, bars=3):
    """Merge same-side zones whose price ranges overlap and became known within `bars` bars
    (an FVG and an OB from the same move). Keeps the first; records the merged kinds."""
    zs = sorted(zs, key=lambda z: z["known_idx"])
    keep = []
    for z in zs:
        dup = next((k for k in keep if k["side"] == z["side"] and abs(k["known_idx"] - z["known_idx"]) <= bars
                    and k["bottom"] <= z["top"] and z["bottom"] <= k["top"]), None)
        if dup is not None:
            if z["kind"] not in dup["kind"]:
                dup["kind"] = dup["kind"] + "+" + z["kind"]
            continue
        keep.append(dict(z))
    return keep
