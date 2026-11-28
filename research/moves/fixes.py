"""Errors and fixes, setup by setup (v1 = setups.py rules; v2 = one fix each, chosen from the S1 timing test and
the cycle-bottom investigation, fixed before this run).
  S1 v2  enter on the setup day; stop below the bottom of the weekly zone touched (instead of that day's low)
  S2 v2  enter on the setup day; stop above the top of the bearish weekly zone touched
  S3 v2  enter on the setup day; stop below the bottom of the weekly zone touched
  S4 v2  replaced by 'sweep and reclaim' (sweep_reclaim.py): weekly close back above a bullish weekly zone within
         4 weeks of closing below it, 50%+ below the all-time high; stop = lowest low since the break
  S5 v2  enter on the setup day; stop above the highest high of the last 20 days
Each failure is labelled: STOP TOO CLOSE = stopped, then price reached +10% in the trade's direction within the next
30 days anyway; WRONG = stopped and never reached +10% within 30 days; NO MOVE = neither +10% nor the stop in 120 days."""
import sys, json, contextlib, io
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
with contextlib.redirect_stdout(io.StringIO()):
    import setups as su
import turnlib
C, H, L, n, dates = su.C, su.H, su.L, su.n, su.dates
Z = turnlib.zone_arrays(su.d, su.W)
topen = su.d.time.dt.tz_convert(None).values
def zone_edge(i, side):
    if side > 0:
        act = (Z["kt"] <= topen[i]) & (Z["inv"] > topen[i]) & Z["bull"] & (L[i] <= Z["top"]) & (C[i] >= Z["bot"])
        return float(Z["bot"][act].min()) if act.any() else None
    act = (Z["kt"] <= topen[i]) & (Z["inv"] > topen[i]) & ~Z["bull"] & (H[i] >= Z["bot"]) & (C[i] <= Z["top"])
    return float(Z["top"][act].max()) if act.any() else None
def label(entry, side, stop, res):
    if res[10] is None:
        return "open"
    if res[10][0]:
        return "WIN"
    # stopped: did it reach +10% within 30 days after the stop day?
    sd = entry + res[10][1]
    seg = C[sd:min(n, sd + 31)]
    reach = ((seg / C[entry] - 1) * side >= 0.10).any()
    return "STOP TOO CLOSE" if reach else "WRONG"
out = {}
for key in ("S1", "S2", "S3", "S5"):
    side = su.SETUPS[key]["side"]
    rows = []
    for e in su.episodes(key):
        i = e["loc"]
        v1stop = L[i] if side > 0 else H[i]
        v2stop = zone_edge(i, side) if key != "S5" else H[max(0, i - 19):i + 1].max()
        if v2stop is None:
            v2stop = v1stop
        r = dict(loc=dates[i], close=round(C[i], 2))
        for ver, stop in (("v1", v1stop), ("v2", v2stop)):
            res, best, status, _ = su.outcome(i, side, stop)
            r[ver] = dict(stop=round(float(stop), 2), stop_dist=round(abs(C[i] / stop - 1) * 100, 1), result=label(i, side, stop, res),
                          win20=None if res[20] is None else res[20][0], best=best,
                          end_day=dates[min(n - 1, i + (res[10][1] if res[10] is not None else 0))])
        rows.append(r)
    out[key] = rows
# S4 v2 from the sweep-and-reclaim study
sr = json.load(open(HERE / "sweep_reclaim.json"))
out["S4"] = [dict(loc=e["date"], close=e["close"], zone=e["zone"], break_week=e["break_week"],
                  v2=dict(stop=e["stop"], stop_dist=e["stop_dist"], result="WIN" if e["win10"] else ("open" if e["win10"] is None else "STOPPED"),
                          win20=e["win20"], best=e["best"])) for e in sr["events"] if e["below_ath"] >= 50]
summ = {}
for key, rows in out.items():
    s = {}
    for ver in ("v1", "v2"):
        xs = [r[ver] for r in rows if ver in r]
        if not xs:
            continue
        done = [x for x in xs if x["result"] != "open"]
        wins = sum(x["result"] == "WIN" for x in done)
        stopd = float(np.median([x["stop_dist"] for x in xs]))
        base = su.baseline(su.SETUPS[key]["side"] if key in su.SETUPS else 1, stopd)
        s[ver] = dict(n=len(done), wins=wins, win=round(100 * wins / len(done)) if done else None,
                      win20=round(100 * np.mean([x["win20"] for x in done if x["win20"] is not None])) if done else None,
                      too_close=sum(x["result"] == "STOP TOO CLOSE" for x in done), wrong=sum(x["result"] in ("WRONG", "STOPPED") for x in done),
                      stop_med=round(stopd, 1), base=base["win10"], base20=base["win20"],
                      h1=f"{sum(x['result']=='WIN' for r,x in zip(rows,xs) if r['loc']<'2019' and x['result']!='open')}/{sum(1 for r,x in zip(rows,xs) if r['loc']<'2019' and x['result']!='open')}",
                      h2=f"{sum(x['result']=='WIN' for r,x in zip(rows,xs) if r['loc']>='2019' and x['result']!='open')}/{sum(1 for r,x in zip(rows,xs) if r['loc']>='2019' and x['result']!='open')}")
    summ[key] = s
    print(key, s)
json.dump(dict(summary=summ, signals=out, doc=__doc__.strip()), open(HERE / "fixes.json", "w"), indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o))
