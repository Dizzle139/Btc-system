"""
Step 9: the five setups found in the user's marked moves, as exact DRAFT rules, plus a first-look backtest.

These rules were written FROM the user's marks, so this backtest is in-sample (it has seen the answers). It shows how
often each rule fired in all of history and what happened, so the rules can be refined. The real verdict comes later:
rules fixed on 2011-18, scored on 2019-26.

Every condition uses only data known at the daily close (00:00 UTC). Weekly values = last CLOSED weekly candle.
Halving clock = days since the last halving (Nov 28 2012, Jul 9 2016, May 11 2020, Apr 20 2024); it is known in
advance, but it rests on only 3-4 past cycles.

  BULL PHASE  halving clock 0-548 days (0-18 months) or 913+ days (30+ months)
  BEAR PHASE  halving clock 548-913 days (18-30 months)

  S1 Bull pullback (long)
     regime    bull phase; weekly EMA50 > weekly EMA200; close > weekly EMA200
     pullback  close at least 10% below the highest close of the last 60 days
     location  day's low reaches an active bullish weekly FVG/OB (2x filter, close not below it)
               AND close within 3% of the weekly EMA50
  S2 Bear rally into resistance (short)
     regime    bear phase; close at least 20% below the all-time-high close
     rally     close at least 10% above the lowest close of the last 60 days
     location  day's high reaches an active bearish weekly FVG/OB (close not above it)
  S3 Bear-market bounce (long, against the bigger trend)
     regime    bear phase; close at least 40% below the all-time-high close
     drop      close at least 15% below the highest close of the last 30 days
     location  day's low reaches an active bullish weekly FVG/OB
  S4 Cycle bottom (long)
     regime    close at least 70% below the all-time-high close; halving clock 24+ months
     stretch   close at least 20% below the weekly EMA50
     location  close is the lowest close of the last 60 days
  S5 Cycle top (short)
     regime    close within 10% of the all-time-high close; halving clock 12-24 months
     stretch   close at least 90% above the weekly EMA200
     location  close is the highest close of the last 20 days

  Episode   the first location day starts it; later location days in the next 15 days belong to it.
  Entries   AGGRESSIVE = close of the first location day
            CONFIRMED  = close of the first daily CHoCH in the setup's direction within 15 days after it
  Stop      long: lowest low from the location day to the entry day; short: highest high (structure stop)
  Outcome   from the entry close, daily closes, up to 120 days: does price reach +10% / +20% in the trade's
            direction before a close beyond the stop? Also the best move before the stop or 120 days.
"""
import json, sys
from pathlib import Path
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(ROOT / "bot"))
from btcdata import load  # noqa: E402
import turnlib  # noqa: E402
from structure import trend_state  # noqa: E402

d = load(utc=True)
n = len(d)
O, H, L, C = (d[k].values for k in ("open", "high", "low", "close"))
dates = np.asarray(d.time.dt.strftime("%Y-%m-%d"), dtype=object)
pos = {x: k for k, x in enumerate(dates)}
X = turnlib.compute(d)
W = turnlib.weekly(d)
W["e50"] = W.close.ewm(span=50, adjust=False).mean()
W["e200"] = W.close.ewm(span=200, adjust=False).mean()
wk = np.searchsorted((W.time + pd.Timedelta(days=7)).values, (d.time + pd.Timedelta(days=1)).values, side="right") - 1
we50 = np.where(wk >= 0, W.e50.values[np.clip(wk, 0, None)], np.nan)
we200 = np.where(wk >= 0, W.e200.values[np.clip(wk, 0, None)], np.nan)
_, _, dev = trend_state(d, 2)
choch = {1: np.array(sorted(e["idx"] for e in dev if e["kind"] == "CHoCH" and e["dir"] == "up")),
         -1: np.array(sorted(e["idx"] for e in dev if e["kind"] == "CHoCH" and e["dir"] == "down"))}
hc = X.days_since_halving.values
below_ath = X.below_ath_pct.values
hi60 = pd.Series(C).rolling(60).max().values
lo60 = pd.Series(C).rolling(60).min().values
hi30 = pd.Series(C).rolling(30).max().values
hi20 = pd.Series(C).rolling(20).max().values
bull_phase = (hc < 548) | (hc >= 913)
bear_phase = (hc >= 548) & (hc < 913)

SETUPS = {
    "S1": dict(name="Bull pullback", side=1, checks=[
        ("Regime", "bull phase of the halving clock; weekly EMA50 above EMA200; close above weekly EMA200",
         lambda i: bull_phase[i] and we50[i] > we200[i] and C[i] > we200[i]),
        ("Pullback", "close 10%+ below the highest close of the last 60 days", lambda i: C[i] <= 0.90 * hi60[i]),
        ("Location", "low in a bullish weekly FVG/OB and close within 3% of the weekly EMA50",
         lambda i: bool(X.zone_b[i]) and abs(C[i] / we50[i] - 1) <= 0.03)]),
    "S2": dict(name="Bear rally into resistance", side=-1, checks=[
        ("Regime", "bear phase of the halving clock; close 20%+ below the all-time high", lambda i: bear_phase[i] and below_ath[i] >= 20),
        ("Rally", "close 10%+ above the lowest close of the last 60 days", lambda i: C[i] >= 1.10 * lo60[i]),
        ("Location", "high in a bearish weekly FVG/OB", lambda i: bool(X.zone_t[i]))]),
    "S3": dict(name="Bear-market bounce", side=1, checks=[
        ("Regime", "bear phase of the halving clock; close 40%+ below the all-time high", lambda i: bear_phase[i] and below_ath[i] >= 40),
        ("Drop", "close 15%+ below the highest close of the last 30 days", lambda i: C[i] <= 0.85 * hi30[i]),
        ("Location", "low in a bullish weekly FVG/OB", lambda i: bool(X.zone_b[i]))]),
    "S4": dict(name="Cycle bottom", side=1, checks=[
        ("Regime", "close 70%+ below the all-time high; 24+ months after the halving", lambda i: below_ath[i] >= 70 and hc[i] >= 730),
        ("Stretch", "close 20%+ below the weekly EMA50", lambda i: C[i] <= 0.80 * we50[i]),
        ("Location", "lowest close of the last 60 days", lambda i: C[i] <= lo60[i])]),
    "S5": dict(name="Cycle top", side=-1, checks=[
        ("Regime", "close within 10% of the all-time high; 12-24 months after the halving", lambda i: below_ath[i] <= 10 and 365 <= hc[i] < 730),
        ("Stretch", "close 90%+ above the weekly EMA200", lambda i: C[i] >= 1.90 * we200[i]),
        ("Location", "highest close of the last 20 days", lambda i: C[i] >= hi20[i])]),
}
EPISODE, HORIZON = 15, 120


def ok(f, i):
    try:
        return bool(f(i))
    except Exception:
        return False


def location_days(key):
    chk = SETUPS[key]["checks"]
    return [i for i in range(60, n) if not np.isnan(hc[i]) and not np.isnan(we200[i]) and all(ok(f, i) for _, _, f in chk)]


def outcome(entry, side, stop):
    e = C[entry]; best = 0.0; res = {10: None, 20: None}
    for j in range(entry + 1, min(n, entry + 1 + HORIZON)):
        if (side > 0 and C[j] < stop) or (side < 0 and C[j] > stop):
            for k in res:
                if res[k] is None:
                    res[k] = (False, j - entry)
            return res, round(best, 1), "stopped", j - entry
        g = (C[j] / e - 1) * 100 * side
        best = max(best, g)
        for k in res:
            if res[k] is None and g >= k:
                res[k] = (True, j - entry)
    status = "open" if entry + HORIZON >= n else "time"
    return res, round(best, 1), status, None


def episodes(key):
    side = SETUPS[key]["side"]
    days = location_days(key)
    eps, last_end = [], -10**9
    for i in days:
        if i <= last_end:
            continue
        loc = [j for j in days if i <= j <= i + EPISODE]
        ch = choch[side]
        later = ch[(ch > i) & (ch <= i + EPISODE)]
        conf = int(later[0]) if len(later) else None
        ep = dict(loc=i, loc_days=loc, conf_i=conf)
        for kind, entry in (("aggr", i), ("conf", conf)):
            if entry is None:
                ep[kind] = None; continue
            stop = (L[i:entry + 1].min() if side > 0 else H[i:entry + 1].max())
            res, best, status, stop_day = outcome(entry, side, stop)
            ep[kind] = dict(entry=entry, stop=float(stop), stop_dist=round(abs(C[entry] / stop - 1) * 100, 1),
                            win10=None if res[10] is None else res[10][0], win20=None if res[20] is None else res[20][0],
                            days10=None if res[10] is None or not res[10][0] else res[10][1],
                            best=best, status=status)
        eps.append(ep)
        last_end = (conf if conf is not None else i) + EPISODE
    return eps


def summary(eps, kind, half=None):
    x = [e[kind] for e in eps if e[kind] is not None and (half is None or (dates[e["loc"]] < "2019-01-01") == (half == "2011-18"))]
    r10 = [e["win10"] for e in x if e["win10"] is not None]
    r20 = [e["win20"] for e in x if e["win20"] is not None]
    return dict(n=len(x), win10=round(100 * np.mean(r10)) if r10 else None, n10=len(r10), win20=round(100 * np.mean(r20)) if r20 else None,
                n20=len(r20), best_med=float(np.median([e["best"] for e in x])) if x else None,
                stop_med=float(np.median([e["stop_dist"] for e in x])) if x else None)


# random-entry baseline with the same stop distances, for comparison: every day, stop = the median stop distance
def baseline(side, stop_pct):
    wins10 = wins20 = t10 = t20 = 0
    for i in range(60, n - 1, 3):
        stop = C[i] * (1 - stop_pct / 100) if side > 0 else C[i] * (1 + stop_pct / 100)
        res, _, _, _ = outcome(i, side, stop)
        if res[10] is not None:
            t10 += 1; wins10 += res[10][0]
        if res[20] is not None:
            t20 += 1; wins20 += res[20][0]
    return dict(win10=round(100 * wins10 / t10) if t10 else None, win20=round(100 * wins20 / t20) if t20 else None)


MARKS = json.load(open(HERE / "marks_snapshot.json"))
FAMILY = {"2019-02-09": "S4", "2020-03-22": "S4", "2021-11-15": "S5", "2022-12-19": "S4", "2023-06-15": "S1", "2023-09-13": "S1",
          "2024-09-08": "S1", "2025-04-08": "S1", "2025-10-06": "S5", "2026-01-14": "S2", "2026-06-30": "S3", "2026-10-05": "S2"}

out = dict(rules={}, trades=[], doc=__doc__.strip())
for key, S in SETUPS.items():
    eps = episodes(key)
    st_a = summary(eps, "aggr")["stop_med"] or 2
    st_c = summary(eps, "conf")["stop_med"] or 10
    base_a, base_c = baseline(S["side"], st_a), baseline(S["side"], st_c)
    out["rules"][key] = dict(name=S["name"], side=S["side"], checks=[(a, b) for a, b, _ in S["checks"]],
                             all=dict(aggr=summary(eps, "aggr"), conf=summary(eps, "conf")),
                             h1=dict(aggr=summary(eps, "aggr", "2011-18"), conf=summary(eps, "conf", "2011-18")),
                             h2=dict(aggr=summary(eps, "aggr", "2019-26"), conf=summary(eps, "conf", "2019-26")),
                             baseline=dict(aggr=dict(stop=st_a, **base_a), conf=dict(stop=st_c, **base_c)),
                             signals=[dict(loc=dates[int(e["loc"])], conf=dates[int(e["conf_i"])] if e["conf_i"] is not None else None,
                                           aggr=e["aggr"], conf_res=e["conf"]) for e in eps])
    for e in out["rules"][key]["signals"]:
        for k in ("aggr", "conf_res"):
            if e[k]:
                e[k] = {kk: (dates[v] if kk == "entry" else v) for kk, v in e[k].items()}

# reverse-engineer each marked trade: every check, each day from 20 days before the start to 5 after
for m in sorted(MARKS, key=lambda x: (x["start"], x["end"])):
    key = FAMILY.get(m["start"])
    S = SETUPS[key]
    s, e = pos[m["start"]], pos[m["end"]]
    win = range(max(60, s - 20), min(n, s + 6))
    first_loc = next((i for i in win if all(ok(f, i) for _, _, f in S["checks"])), None)
    detail = []
    at = first_loc if first_loc is not None else s
    for name, text, f in S["checks"]:
        detail.append(dict(name=name, text=text, ok=ok(f, at),
                           days=[dates[i] for i in win if ok(f, i)][:3]))
    ch = choch[S["side"]]
    conf = None
    if first_loc is not None:
        later = ch[(ch > first_loc) & (ch <= first_loc + EPISODE)]
        conf = int(later[0]) if len(later) else None
    r = X.iloc[at]
    k = wk[at]
    vals = dict(halving_months=round(hc[at] / 30.44, 1), below_ath=round(below_ath[at], 1), close=round(C[at], 2),
                w_e50=round(we50[at], 2), w_e200=round(we200[at], 2), vs_e50=round((C[at] / we50[at] - 1) * 100, 1),
                vs_e200=round((C[at] / we200[at] - 1) * 100, 1), from_hi60=round((C[at] / hi60[at] - 1) * 100, 1),
                from_lo60=round((C[at] / lo60[at] - 1) * 100, 1), vol_x=round(float(r.vol_x), 2), phase=r.phase)
    out["trades"].append(dict(mark=m, setup=key, setup_name=S["name"], first_loc=dates[first_loc] if first_loc is not None else None,
                              conf=dates[conf] if conf is not None else None, checks=detail, values=vals,
                              rule_entry_aggr=dict(date=dates[first_loc], close=round(C[first_loc], 2)) if first_loc is not None else None,
                              rule_entry_conf=dict(date=dates[conf], close=round(C[conf], 2)) if conf is not None else None))
json.dump(out, open(HERE / "setups.json", "w"), indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o))

# print a readable summary
for key, R in out["rules"].items():
    a, c = R["all"]["aggr"], R["all"]["conf"]
    print(f"{key} {R['name']}: {a['n']} signals | aggressive +10 before stop {a['win10']}% (n {a['n10']}), +20 {a['win20']}%, "
          f"median stop {a['stop_med']}% | confirmed {c['n']} entries: +10 {c['win10']}%, +20 {c['win20']}%, stop {c['stop_med']}% "
          f"| random, aggr stop {R['baseline']['aggr']['stop']}%: +10 {R['baseline']['aggr']['win10']}% +20 {R['baseline']['aggr']['win20']}%; conf stop {R['baseline']['conf']['stop']}%: +10 {R['baseline']['conf']['win10']}% +20 {R['baseline']['conf']['win20']}%")
    print("   2011-18 aggr", R["h1"]["aggr"], "\n   2019-26 aggr", R["h2"]["aggr"])
    print("   2011-18 conf", R["h1"]["conf"], "| 2019-26 conf", R["h2"]["conf"])
for t in out["trades"]:
    print(t["mark"]["start"], t["setup"], "rule location", t["first_loc"], "confirmed", t["conf"], [(c["name"], c["ok"]) for c in t["checks"]])
