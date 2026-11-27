"""
History of every past turn-watch alert (2+ items on a new 10-day closing extreme), grouped into episodes, with what
happened next. Used to show how the pieces of a new alert worked together in the past.

Episode: starts at the first qualifying day; while new 10-day extremes keep coming it is the same alert; ends after
10 days without one. Outcome: a real turn of 10/20/30/50% (answer key: research/moves/moves.csv, daily closes) on an
alert day or within 5 days after one. Only episodes whose outcome is already known are used for matching.
"""
import numpy as np
import pandas as pd

from turnlib import flags

WINDOW = 5


def turns_from_moves(moves):
    m = moves[moves.basis == "close"]
    out = {}
    for lvl in (10, 20, 30, 50):
        x = m[m.level == lvl]
        out[lvl] = {"b": [], "t": [], "last_confirm": None}
        for r in x.itertuples():
            # a move's END is a turning point; it is confirmed at r.confirmed
            if pd.isna(r.confirmed):
                continue
            side = "t" if r.dir == "up" else "b"          # an up move ends at a top
            out[lvl][side].append((str(r.end_date)[:10], str(r.confirmed_date)[:10]))
        conf = [c for s in ("b", "t") for _, c in out[lvl][s]]
        out[lvl]["last_confirm"] = max(conf) if conf else None
    return out


def episodes(X, side):
    ext = (X.new_low10 if side == "b" else X.new_high10).values
    alert = (X.alert_b if side == "b" else X.alert_t).values
    eps, cur, last = [], None, -999
    for i in range(30, len(X)):
        if ext[i]:
            if cur is not None and i - last > 10:
                eps.append(cur); cur = None
            last = i
            if alert[i]:
                if cur is None:
                    cur = dict(first=i, alerts=[i])
                else:
                    cur["alerts"].append(i)
        elif cur is not None and i - last > 10:
            eps.append(cur); cur = None
    if cur is not None:
        cur["open"] = True
        eps.append(cur)
    return eps


def build(X, moves):
    T = turns_from_moves(moves)
    dates = X.date.values
    pos = {d: k for k, d in enumerate(dates)}
    C = X.close.values
    rows = []
    for side in ("b", "t"):
        for e in episodes(X, side):
            a0 = e["first"]
            row = X.iloc[a0]
            base, warn = flags(row, side)
            r = dict(side=side, first_date=dates[a0], last_alert_date=dates[e["alerts"][-1]], n_alert_days=len(e["alerts"]),
                     price=C[a0], base="+".join(base), warnings="+".join(warn) or "none", phase=row.phase)
            for lvl in (10, 20, 30, 50):
                tl = {pos[d]: c for d, c in T[lvl][side] if d in pos}
                known = T[lvl]["last_confirm"] is not None and dates[a0] <= T[lvl]["last_confirm"]
                hit = sorted(x for x in tl if any(a <= x <= a + WINDOW for a in e["alerts"]))
                r[f"hit{lvl}"] = (bool(hit) if known else None)
                r[f"hit{lvl}_known"] = tl[hit[0]] if hit else None      # date the turn was confirmed
                if lvl == 10:
                    r["turn_date"] = dates[hit[0]] if hit else None
                    end = hit[0] if hit else min(len(C) - 1, a0 + 30)
                    seg = C[a0:end + 1]
                    r["further_pct"] = round(((seg.min() / C[a0] - 1) if side == "b" else (seg.max() / C[a0] - 1)) * 100, 1)
                    r["days_to_turn"] = (hit[0] - a0) if hit else None
            for k in (7, 14, 30):
                r[f"ret{k}"] = round((C[a0 + k] / C[a0] - 1) * 100, 1) if a0 + k < len(C) else None
            rows.append(r)
    return pd.DataFrame(rows)


RESOLVE_DAYS = 45   # only episodes whose last alert day is 45+ days before the new alert: their outcome was known by then


def similar(H, side, base, warn, phase, before_date):
    """How past alerts with the same pieces turned out, most specific first. Uses only episodes whose outcome was
    already known on `before_date` (no look-ahead)."""
    cutoff = (pd.Timestamp(before_date) - pd.Timedelta(days=RESOLVE_DAYS)).strftime("%Y-%m-%d")
    h = H[(H.side == side) & (H.last_alert_date <= cutoff) & H.hit10.notna()].copy()
    h["hit20"] = h.hit20.astype(object)
    h = h[~(h.hit10.astype(bool) & (h.hit10_known.fillna("9999") > before_date))]     # hit not yet confirmed back then
    late20 = h.hit20.notna() & h.hit20.astype(bool) & (h.hit20_known.fillna("9999") > before_date)
    h.loc[late20, "hit20"] = None
    wtxt = "+".join(warn) or "none"
    tiers = [("same setup items, same warnings, same cycle phase", (h.base == "+".join(base)) & (h.warnings == wtxt) & (h.phase == phase)),
             ("same warnings and cycle phase (any 2+ items)", (h.warnings == wtxt) & (h.phase == phase)),
             ("same warnings (any cycle phase)", h.warnings == wtxt),
             ("same cycle phase (any warnings)", h.phase == phase),
             ("all past alerts on this side", pd.Series(True, index=h.index))]
    out = []
    for name, m in tiers:
        x = h[m]
        if len(x) == 0:
            out.append(dict(tier=name, n=0)); continue
        y = x[x.first_date >= "2019-01-01"]
        out.append(dict(tier=name, n=len(x), hit10=round(100 * x.hit10.astype(bool).mean()),
                        n_2019=len(y), hit10_2019=round(100 * y.hit10.astype(bool).mean()) if len(y) else None,
                        hit20=round(100 * x.hit20.dropna().astype(bool).mean()) if x.hit20.notna().any() else None,
                        further=float(np.median(x.further_pct)), ret14=float(np.nanmedian(x.ret14.astype(float))),
                        recent=list(x.sort_values("first_date").first_date.tail(3))))
    return out
