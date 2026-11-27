"""
Step 4: out-of-sample test of the stacking rule (fixed before running, approved Nov 27, 2026).

Trigger day (bottoms; tops mirrored): close = lowest close of the last 10 days.
Items, known at that day's close:
  sharp    close <= 0.90 x close 7 days earlier
  extended close <= 0.80 x close 30 days earlier
  volume   Bitstamp volume >= 1.5 x average of previous 20 days
  zone     day's low reaches an active bull weekly FVG/OB (2x filter), close not below it
Alert levels: 0 (benchmark: every new 10-day extreme), 2+, 3+, 4.
Episode: starts at the first qualifying day; while new 10-day extremes keep coming it is the same alert; ends after
10 days without a new 10-day extreme.
Caught: a turn of the size happened on a qualifying alert day or within W days after one (W = 0, 3, 5, 10 tested).
Hit episode: contains a caught turn. False alarm: no turn of that size.
Pass (per level, window, size): hit rate beats the benchmark in BOTH halves (2011-18, 2019-26), more items -> higher
hit rate in both halves, and at least 10 alerts in each half (else "not enough data").
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
import sys
sys.path.insert(0, str(HERE))
from btcdata import load  # noqa: E402
px = load()
t = px.time
C = px.close.values
n = len(C)
B = pd.read_csv(HERE / "days.csv")            # per-day snapshot from turns.py (every day >= 30, both sides)
T = pd.read_csv(HERE / "turns.csv")
M = pd.read_csv(HERE / "moves.csv")
M = M[M.basis == "close"]

lo10 = pd.Series(C).rolling(10).min().values
hi10 = pd.Series(C).rolling(10).max().values

items = {}
for s in (1, -1):
    b = B[B.s == s].set_index("i")
    it = pd.DataFrame(index=range(n))
    it["sharp"] = b.prior7.le(-10)
    it["extended"] = b.prior30.le(-20)
    it["volume"] = b.vol_bs.ge(1.5)
    it["zone"] = b.zW2_any.astype(bool)
    it = it.fillna(False).astype(bool)
    it["count"] = it[["sharp", "extended", "volume", "zone"]].sum(axis=1)
    ext = np.zeros(n, bool)
    ext[9:] = (C[9:] <= lo10[9:]) if s > 0 else (C[9:] >= hi10[9:])
    ext[:30] = False
    it["extreme"] = ext
    items[s] = it

HALF = lambda i: "2011-18" if t[i] < pd.Timestamp("2019-01-01") else "2019-26"
ERA = lambda i: "2011-16" if t[i] < pd.Timestamp("2016-07-01") else ("2016-21" if t[i] < pd.Timestamp("2021-07-01") else "2021-26")


def turn_confirm(level):
    """turn index -> index of the day it was confirmed (previous move's confirmation)."""
    m = M[M.level == level]
    return {int(r.end): (None if pd.isna(r.confirmed) else int(r.confirmed)) for r in m.itertuples()}


def episodes(s, k):
    it = items[s]
    eps, cur, last_ext = [], None, -999
    for i in range(30, n):
        if it.extreme[i]:
            if cur is not None and i - last_ext > 10:
                eps.append(cur); cur = None
            last_ext = i
            if it["count"][i] >= k:
                if cur is None:
                    cur = dict(first=i, alerts=[i])
                else:
                    cur["alerts"].append(i)
        elif cur is not None and i - last_ext > 10:
            eps.append(cur); cur = None
    if cur is not None:
        eps.append(cur)
    return eps


def run(level, s, k, W):
    turns = T[(T.level == level) & (T.s == s)].i.astype(int).tolist()
    conf = turn_confirm(level)
    last_conf = max(v for v in conf.values() if v is not None)      # after this, turns are not knowable yet
    eps = episodes(s, k)
    res = []
    caught_turns = set()
    for e in eps:
        if e["first"] > last_conf:
            continue        # unresolved: too recent to know whether a turn came
        hit = [tt for tt in turns if any(a <= tt <= a + W for a in e["alerts"])]
        caught_turns.update(hit)
        a0 = e["first"]
        # how far price kept going against the alert: to the turn for hits, over the next 30 days for false alarms
        end = hit[0] if hit else min(n - 1, a0 + 30)
        fwd = C[a0:end + 1]
        adverse = ((fwd.min() / C[a0] - 1) * 100) if s > 0 else ((fwd.max() / C[a0] - 1) * -100)
        res.append(dict(first=a0, hit=bool(hit), turn=hit[0] if hit else None, adverse=round(adverse, 1),
                        days_to_turn=(hit[0] - a0) if hit else None,
                        confirm_days=(conf.get(hit[0]) - hit[0]) if hit and conf.get(hit[0]) is not None else None,
                        half=HALF(a0), era=ERA(a0), n_items=int(items[s]["count"][a0])))
    resolvable = [tt for tt in turns if tt <= last_conf and tt >= 30]
    return res, resolvable, caught_turns


rows = []
for level in (10, 20, 30, 50):
    for s in (1, -1):
        for W in (0, 3, 5, 10):
            for k in (0, 2, 3, 4):
                res, tr, caught = run(level, s, k, W)
                for grp in ("all", "2011-18", "2019-26", "2011-16", "2016-21", "2021-26"):
                    key = "half" if grp in ("2011-18", "2019-26") else "era"
                    rr = [r for r in res if grp == "all" or r[key] == grp]
                    tt = [x for x in tr if grp == "all" or (HALF(x) if key == "half" else ERA(x)) == grp]
                    cc = [x for x in tt if x in caught]
                    h = [r for r in rr if r["hit"]]; f = [r for r in rr if not r["hit"]]
                    rows.append(dict(level=level, side="bottom" if s > 0 else "top", W=W, k=k, grp=grp,
                                     alerts=len(rr), hits=len(h), hit_rate=round(100 * len(h) / len(rr), 1) if rr else None,
                                     turns=len(tt), caught=len(cc), catch_rate=round(100 * len(cc) / len(tt), 1) if tt else None,
                                     adverse_hit=float(np.median([r["adverse"] for r in h])) if h else None,
                                     adverse_false=float(np.median([r["adverse"] for r in f])) if f else None,
                                     days_to_turn=float(np.median([r["days_to_turn"] for r in h])) if h else None,
                                     confirm_days=float(np.median([r["confirm_days"] for r in h if r["confirm_days"] is not None])) if h else None))
R = pd.DataFrame(rows)
R.to_csv(HERE / "stack_test.csv", index=False)


# pass criteria
def verdict(level, side, W):
    out = {}
    g = R[(R.level == level) & (R.side == side) & (R.W == W)]
    for k in (2, 3, 4):
        v = []
        for half in ("2011-18", "2019-26"):
            x = g[(g.k == k) & (g.grp == half)].iloc[0]; b0 = g[(g.k == 0) & (g.grp == half)].iloc[0]
            if x.alerts < 10:
                v.append("not enough data"); continue
            ok = x.hit_rate > b0.hit_rate
            if k > 2:
                prev = g[(g.k == k - 1) & (g.grp == half)].iloc[0]
                ok = ok and (prev.alerts < 10 or x.hit_rate > prev.hit_rate)
            v.append("pass" if ok else "fail")
        out[k] = "not enough data" if "not enough data" in v else ("PASS" if v == ["pass", "pass"] else "fail")
    return out


V = {f"{lvl}|{side}|{W}": verdict(lvl, side, W) for lvl in (10, 20, 30, 50) for side in ("bottom", "top") for W in (0, 3, 5, 10)}
json.dump(V, open(HERE / "stack_verdicts.json", "w"), indent=1)

# today's reading
today = {}
for s, name in ((1, "bottom"), (-1, "top")):
    it = items[s]; i = n - 1
    today[name] = dict(date=str(t[i].date()), new_10d_extreme=bool(it.extreme[i]),
                       items=[c for c in ("sharp", "extended", "volume", "zone") if it[c][i]])
json.dump(today, open(HERE / "stack_today.json", "w"), indent=1)

pd.set_option("display.width", 250)
for level in (10, 20, 30, 50):
    for side in ("bottom", "top"):
        g = R[(R.level == level) & (R.side == side) & (R.W == 5)]
        print(f"\n== {level}% {side}s, window 5 ==")
        print(g[g.grp.isin(["all", "2011-18", "2019-26"])].pivot_table(index="k", columns="grp", values=["alerts", "hit_rate", "catch_rate"]).to_string())
        print("verdicts W0/3/5/10:", [V[f"{level}|{side}|{W}"] for W in (0, 3, 5, 10)])
print(today)
