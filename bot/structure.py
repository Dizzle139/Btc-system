"""
Market structure — swing pivots, HH/HL/LH/LL labels, BOS / CHoCH, trend state.
A swing is a pivot with `piv` bars on each side. It is only KNOWN `piv` bars later (no look-ahead).
Trend state flips on a CLOSE beyond the last confirmed swing on the other side:
  bullish -> close below last swing low  = CHoCH down (state becomes bearish)
  bearish -> close above last swing high = CHoCH up   (state becomes bullish)
A close beyond the last swing in the SAME direction = BOS (continuation).
"""
import numpy as np
import pandas as pd


def swings(d, piv=2):
    out = []  # (pivot_idx, known_idx, type, price)
    for p in range(piv, len(d) - piv):
        wh = d.high[p - piv:p + piv + 1]
        wl = d.low[p - piv:p + piv + 1]
        if d.high[p] == wh.max():
            out.append((p, p + piv, "H", d.high[p]))
        if d.low[p] == wl.min():
            out.append((p, p + piv, "L", d.low[p]))
    # label HH/LH and HL/LL vs previous swing of same type
    lab, last = [], {"H": None, "L": None}
    for p, k, t, px in out:
        prev = last[t]
        if prev is None:
            l = t
        elif t == "H":
            l = "HH" if px > prev else "LH"
        else:
            l = "HL" if px > prev else "LL"
        last[t] = px
        lab.append(dict(idx=p, known_idx=k, type=t, price=px, label=l))
    return lab


def trend_state(d, piv=2):
    """Per bar: structure state known at that bar's close, plus BOS/CHoCH events."""
    sw = swings(d, piv)
    n = len(d)
    state = np.array([""] * n, dtype=object)
    events = []
    last_h = last_l = None
    cur = ""
    si = 0
    sw_sorted = sorted(sw, key=lambda s: s["known_idx"])
    broken_h = broken_l = None
    for i in range(n):
        while si < len(sw_sorted) and sw_sorted[si]["known_idx"] <= i:
            s = sw_sorted[si]
            if s["type"] == "H":
                last_h = s["price"]
            else:
                last_l = s["price"]
            si += 1
        c = d.close[i]
        if last_h is not None and c > last_h and broken_h != last_h:
            events.append(dict(idx=i, kind="BOS" if cur == "bull" else "CHoCH", dir="up", level=last_h))
            cur, broken_h = "bull", last_h
        elif last_l is not None and c < last_l and broken_l != last_l:
            events.append(dict(idx=i, kind="BOS" if cur == "bear" else "CHoCH", dir="down", level=last_l))
            cur, broken_l = "bear", last_l
        state[i] = cur
    return state, sw, events


def map_state(lower, higher, higher_state, higher_bar):
    """State of the higher TF known at each lower-TF bar close (uses only closed higher bars)."""
    ht = pd.DataFrame({"close_time": (higher.time + higher_bar).astype("datetime64[ns, UTC]"), "state": higher_state})
    lt = pd.DataFrame({"t": (lower.time + lower.time.diff().median()).astype("datetime64[ns, UTC]")})
    m = pd.merge_asof(lt.sort_values("t"), ht.sort_values("close_time"), left_on="t", right_on="close_time",
                      direction="backward")
    return m["state"].fillna("").values
