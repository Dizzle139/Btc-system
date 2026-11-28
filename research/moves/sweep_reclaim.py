"""Cycle-bottom investigation -> 'sweep and reclaim' of a bullish weekly FVG/OB (user: "it hit a FVG and then passed
through it, then bounced"). Definition fixed before running:
  break    a weekly close below the bottom of an active bullish weekly zone (2x filter)
  reclaim  within the next 4 weekly candles, a weekly close back above that zone's bottom
  entry    the close of the reclaim week (known at the weekly close); one signal per reclaim week
  stop     the lowest low from the break week to the reclaim week
Variants by how deep below the all-time high the reclaim is: any, 50%+, 70%+.
Outcome as setups.py (+10% / +20% before a close below the stop, 120 days), vs random entries with the same stop."""
import sys, json, contextlib, io
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
with contextlib.redirect_stdout(io.StringIO()):
    import setups as su
from zones import find_fvgs, find_obs, dedupe
d, C, L, n, dates = su.d, su.C, su.L, su.n, su.dates
W = su.W.reset_index(drop=True); Wc, Wl, Wt = W.close.values, W.low.values, W.time
zs = [z for z in dedupe(find_fvgs(W, 2.0) + find_obs(W, 2.0)) if z["side"] == "bull"]
dpos = {t: k for k, t in enumerate(d.time.dt.tz_convert(None).dt.normalize().values)}
def day_of_week_close(k):   # last daily candle inside weekly candle k
    t = (Wt[k] + pd.Timedelta(days=6)).tz_convert(None).normalize().to_datetime64()
    return dpos.get(t)
events = {}
for z in zs:
    j = z["known_idx"] + 1
    while j < len(W):
        if Wc[j] < z["bottom"]:
            rec = next((r for r in range(j + 1, min(len(W), j + 5)) if Wc[r] > z["bottom"]), None)
            if rec is not None:
                di = day_of_week_close(rec)
                if di is not None and rec not in events:
                    lo = float(Wl[j:rec + 1].min())
                    events[rec] = dict(week=str(Wt[rec].date()), entry_day=di, zone=f"{z['kind']} {z['bottom']:,.0f}-{z['top']:,.0f}",
                                       break_week=str(Wt[j].date()), stop=lo)
                j = rec + 1
                continue
            break                      # broke and did not come back within 4 weeks: the zone is gone
        j += 1
rows = []
for k, e in sorted(events.items()):
    i = e["entry_day"]
    res, best, status, _ = su.outcome(i, 1, e["stop"])
    rows.append(dict(e, date=dates[i], close=round(C[i], 2), below_ath=round(su.below_ath[i], 1), stop_dist=round((C[i] / e["stop"] - 1) * 100, 1),
                     win10=None if res[10] is None else res[10][0], win20=None if res[20] is None else res[20][0], best=best))
R = pd.DataFrame(rows)
summ = []
for name, m in (("any depth", R.below_ath >= 0), ("50%+ below ATH", R.below_ath >= 50), ("70%+ below ATH", R.below_ath >= 70)):
    g = R[m]
    for half, hm in (("all", g.date >= ""), ("2011-18", g.date < "2019-01-01"), ("2019-26", g.date >= "2019-01-01")):
        x = g[hm]; w10 = x.win10.dropna(); w20 = x.win20.dropna()
        sd = float(x.stop_dist.median()) if len(x) else 10
        b = su.baseline(1, sd) if half == "all" else {"win10": None, "win20": None}
        summ.append(dict(depth=name, half=half, n=len(x), win10=round(100 * w10.mean()) if len(w10) else None, win20=round(100 * w20.mean()) if len(w20) else None,
                         stop_med=round(sd, 1), base10=b["win10"], base20=b["win20"], best_med=float(x.best.median()) if len(x) else None))
S = pd.DataFrame(summ)
print(S.to_string(index=False))
print(R[R.below_ath >= 50][["date", "zone", "break_week", "close", "below_ath", "stop_dist", "win10", "win20", "best"]].to_string(index=False))
json.dump(dict(summary=summ, events=rows), open(HERE / "sweep_reclaim.json", "w"), indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o))
