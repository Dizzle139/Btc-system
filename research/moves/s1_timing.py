"""S1 (bull pullback) entry timing test. Fixed before running (user: "test your theory").
Setup day = S1 conditions (setups.py). For each S1 episode, entries within 20 days after the setup day:
  E0 setup-day close                 E1 next day's close
  E2 higher low: first confirmed swing low (2 bars each side, on lows) after the setup day whose low is above the
     setup day's low; entry when it is confirmed (2 days later)
  E3 first daily CHoCH up            E4 first close back above the weekly EMA50 after a close below it
  E5 first close above the setup day's high
Stops: A = lowest low from the setup day to the entry day (structure); B = bottom of the weekly zone touched on the
setup day (below the zone). Outcome as setups.py (+10% / +20% before a close beyond the stop, 120 days) vs random
entries with the same stop width. Also the % of the eventual move captured."""
import sys, json
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import contextlib, io
with contextlib.redirect_stdout(io.StringIO()):
    import setups as su
C, H, L, n, dates = su.C, su.H, su.L, su.n, su.dates
X, we50 = su.X, su.we50
# weekly zones touched on a day (bull side) with their bottoms
import turnlib
Z = turnlib.zone_arrays(su.d, su.W)
topen = su.d.time.dt.tz_convert(None).values
def zone_bottom(i):
    act = (Z["kt"] <= topen[i]) & (Z["inv"] > topen[i]) & Z["bull"] & (L[i] <= Z["top"]) & (C[i] >= Z["bot"])
    return float(Z["bot"][act].min()) if act.any() else None
eps = su.episodes("S1")
def swing_lows_after(i, until):
    out = []
    for p in range(i + 1, min(until, n - 2)):
        if L[p] == L[p - 2:p + 3].min() and p + 2 < n:
            out.append(p)
    return out
rows = []
for e in eps:
    i = e["loc"]
    ents = {"E0 setup day": i, "E1 next day": i + 1 if i + 1 < n else None}
    hl = [p for p in swing_lows_after(i, i + 21) if L[p] > L[i]]
    ents["E2 higher low"] = hl[0] + 2 if hl else None
    ents["E3 daily CHoCH"] = e["conf_i"]
    below = [j for j in range(i, min(n, i + 21)) if C[j] < we50[j]]
    rec = next((j for j in range(below[0] + 1, min(n, i + 21)) if C[j] > we50[j]), None) if below else None
    ents["E4 reclaim weekly EMA50"] = rec
    ents["E5 close above setup-day high"] = next((j for j in range(i + 1, min(n, i + 21)) if C[j] > H[i]), None)
    zb = zone_bottom(i)
    for name, en in ents.items():
        if en is None or en >= n:
            rows.append(dict(loc=dates[i], entry=name, fired=False)); continue
        for sname, stop in (("A structure low", L[i:en + 1].min()), ("B below the weekly zone", zb if zb is not None else L[i:en + 1].min())):
            res, best, status, _ = su.outcome(en, 1, stop)
            rows.append(dict(loc=dates[i], entry=name, stop_rule=sname, fired=True, entry_date=dates[en], days_after=int(en - i),
                             entry_vs_setup=round((C[en] / C[i] - 1) * 100, 1), stop_dist=round((C[en] / stop - 1) * 100, 1),
                             win10=None if res[10] is None else res[10][0], win20=None if res[20] is None else res[20][0], best=best))
R = pd.DataFrame(rows)
R.to_csv(HERE / "s1_timing.csv", index=False)
F = R[R.fired]
out = []
for (en, sr), g in F.groupby(["entry", "stop_rule"]):
    g10 = g.win10.dropna(); g20 = g.win20.dropna()
    sd = float(g.stop_dist.median())
    base = su.baseline(1, sd)
    h1 = g[g["loc"] < "2019-01-01"].win10.dropna(); h2 = g[g["loc"] >= "2019-01-01"].win10.dropna()
    out.append(dict(entry=en, stop=sr, fired=len(g), of=len(eps), win10=round(100 * g10.mean()) if len(g10) else None,
                    win20=round(100 * g20.mean()) if len(g20) else None, stop_med=round(sd, 1), base10=base["win10"], base20=base["win20"],
                    after_days=float(g.days_after.median()), entry_vs_setup=float(g.entry_vs_setup.median()), best_med=float(g.best.median()),
                    h1=f"{int(h1.sum())}/{len(h1)}", h2=f"{int(h2.sum())}/{len(h2)}"))
O = pd.DataFrame(out).sort_values(["stop", "entry"])
print(O.to_string(index=False))
json.dump(dict(table=out, signals=rows), open(HERE / "s1_timing.json", "w"), indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o))
