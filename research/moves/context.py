"""
Step 5: market context and slow turns. Items fixed and approved before testing (Nov 27, 2026).

Compared, as before, with look-alike days (new 10-day closing low/high that did not turn).
Run on all turns and on SLOW turns (fewer than 2 of the 4 stacking items), each against look-alike days with the same
property. Keep rule: lift moves the same way in BOTH halves (2011-18, 2019-26): >= 1.2 in both (shows up more at turns)
or <= 0.83 in both (shows up less at turns), with at least 8 turns per half. Direction is not assumed for
macro items; a consistent "less often" is as informative as "more often".

Timing: every item uses values known at the BTC daily close (00:00 UTC). US market closes are earlier the same day.
M2 is shifted 14 days (published with a lag), Fed funds 1 day.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
DATA = ROOT / "data"
import sys
sys.path.insert(0, str(HERE))
from btcdata import load  # noqa: E402
px = load()
day = px.time.dt.normalize()      # candle date (UTC)
C, H, L, V = px.close.values, px.high.values, px.low.values, px.volume.values
n = len(C)
T = pd.read_csv(HERE / "turns.csv")
B = pd.read_csv(HERE / "days.csv")

# ---------------- BTC-only series ----------------
pc = np.r_[C[0], C[:-1]]
tr = np.maximum(H - L, np.maximum(abs(H - pc), abs(L - pc)))
atrp = pd.Series(tr).ewm(alpha=1 / 14, adjust=False).mean() / C * 100
d = pd.Series(C).diff()
up, dn = d.clip(lower=0), (-d).clip(lower=0)
rsi = 100 - 100 / (1 + up.ewm(alpha=1 / 14, adjust=False).mean() / dn.ewm(alpha=1 / 14, adjust=False).mean())
ath = pd.Series(C).cummax().values
last_ath = pd.Series(np.where(C >= ath, np.arange(n), np.nan)).ffill().values
HALVINGS = pd.to_datetime(["2012-11-28", "2016-07-09", "2020-05-11", "2024-04-20"])
vol20 = pd.Series(V).rolling(20).mean().shift(1).values
vol90 = pd.Series(V).rolling(90).mean().shift(1).values
atr_p20 = atrp.rolling(180).quantile(0.2).values


def since_halving(i):
    past = HALVINGS[HALVINGS <= day[i]]
    return (day[i] - past[-1]).days if len(past) else np.nan


# ---------------- macro series (if the data agent has fetched them) ----------------
def series(name, col="value", shift_days=0, file=None):
    f = DATA / (file or f"{name}.csv")
    if not f.exists():
        return None
    x = pd.read_csv(f)
    t = pd.to_datetime(x.time).dt.tz_localize(None).dt.normalize() + pd.Timedelta(days=shift_days)
    s = pd.Series(pd.to_numeric(x[col], errors="coerce").values, index=t).dropna().sort_index()
    s = s[~s.index.duplicated(keep="last")]
    return s.reindex(pd.date_range(s.index[0], day.iloc[-1])).ffill().reindex(day.values).values   # last known value


MAC = {   # Yahoo Finance daily closes (US session ends before the BTC daily close at 00:00 UTC)
    "dollar": series("yahoo_DX_Y_NYB", col="close"), "us10y": series("yahoo_TNX", col="close"),
    "vix": series("yahoo_VIX", col="close"), "spx": series("yahoo_GSPC", col="close"), "gold": series("yahoo_GC_F", col="close"),
    # FRED refused GitHub's servers: Fed funds and M2 need a free FRED API key (not available yet)
    "fed": series("fred_DFF", shift_days=1), "m2": series("fred_WM2NS", shift_days=14),
    "btc_d": series("btc_dominance", col="bitcoinDominance"),
}
uf = DATA / "usdtd_1D.csv"   # TradingView export from the user (CRYPTOCAP:USDT.D, daily)
if uf.exists():
    x = pd.read_csv(uf)
    t = pd.to_datetime(x.time, unit="s") + pd.Timedelta(days=1)     # a daily bar is known at its close
    s = pd.Series(x["close"].values, index=t).sort_index()
    MAC["usdt_d"] = s.reindex(pd.date_range(s.index[0], day.iloc[-1])).ffill().reindex(day.values).values


def chg(a, i, k):
    if a is None or i - k < 0 or np.isnan(a[i]) or np.isnan(a[i - k]):
        return np.nan
    return a[i] / a[i - k] - 1


_E = {}


def ema_above(a, i, span=200):
    if a is None:
        return np.nan
    k = id(a)
    if k not in _E:
        _E[k] = pd.Series(a).ffill().ewm(span=span, adjust=False).mean().values
    return float(a[i] > _E[k][i]) if not np.isnan(a[i]) else np.nan




def items(i, s):
    r = {}
    hs = since_halving(i)
    # A. market cycle (4-year / halving cycle). Phases set in advance from the halving date, no hindsight.
    for name, a, b in (("0-6 months after halving", 0, 182), ("6-18 months after halving", 182, 548),
                       ("18-30 months after halving", 548, 913), ("30+ months after halving", 913, 9999)):
        r[f"Cycle: {name}"] = (a <= hs < b) if not np.isnan(hs) else np.nan
    dd = (C[i] / ath[i] - 1) * 100
    r["Cycle: 50%+ below all-time high"] = dd <= -50
    r["Cycle: 70%+ below all-time high"] = dd <= -70
    r["Cycle: within 10% of all-time high"] = dd >= -10
    r["Cycle: last all-time high over a year ago"] = (i - last_ath[i]) > 365
    r["Cycle: new all-time high in the last 30 days"] = (i - last_ath[i]) <= 30
    # B. slow-turn signs
    if i >= 60:
        p30, p60 = (C[i] / C[i - 30] - 1) * s, (C[i - 30] / C[i - 60] - 1) * s
        r["Slow: last 30 days moved less than the 30 before (same direction)"] = (p30 < 0) and (p60 < 0) and (abs(p30) < abs(p60))
    r["Slow: daily range squeezed (bottom 20% of last 180 days)"] = atrp[i] <= atr_p20[i] if not np.isnan(atr_p20[i]) else np.nan
    r["Slow: volume drying up (20-day avg < 0.7x 90-day avg)"] = vol20[i] < 0.7 * vol90[i] if not np.isnan(vol90[i]) else np.nan
    if i >= 40:
        w = slice(i - 40, i - 9)                       # an earlier extreme 10-40 days ago
        if s > 0:
            j = i - 40 + int(np.argmin(C[w]))
            r["Slow: RSI divergence (lower low in price, higher low in RSI)"] = (C[i] < C[j]) and (rsi[i] > rsi[j])
        else:
            j = i - 40 + int(np.argmax(C[w]))
            r["Slow: RSI divergence (higher high in price, lower high in RSI)"] = (C[i] > C[j]) and (rsi[i] < rsi[j])
    k90 = max(0, i - 90)
    ext_i = k90 + (int(np.argmax(C[k90:i + 1])) if s > 0 else int(np.argmin(C[k90:i + 1])))
    r["Slow: move into the turn lasted 30+ days"] = (i - ext_i) >= 30
    # C. other markets (neutral wording: direction is not assumed)
    r["US dollar (DXY) up over 30 days"] = (chg(MAC["dollar"], i, 30) > 0) if not np.isnan(chg(MAC["dollar"], i, 30)) else np.nan
    r["US dollar (DXY) above its 200-day EMA"] = ema_above(MAC["dollar"], i)
    if MAC["us10y"] is not None and i >= 30 and not np.isnan(MAC["us10y"][i - 30]):
        r["US 10-year yield up over 30 days"] = MAC["us10y"][i] - MAC["us10y"][i - 30] > 0
    if MAC["fed"] is not None and i >= 90 and not np.isnan(MAC["fed"][i - 90]):
        f = MAC["fed"][i] - MAC["fed"][i - 90]
        r["Fed raising (rate up 0.1+ over 90 days)"] = f >= 0.1
        r["Fed cutting (rate down 0.1+ over 90 days)"] = f <= -0.1
    if MAC["m2"] is not None and i >= 365 + 90:
        g_now, g_3m = chg(MAC["m2"], i, 365), chg(MAC["m2"], i - 90, 365)
        if not (np.isnan(g_now) or np.isnan(g_3m)):
            r["M2 growing year over year"] = g_now > 0
            r["M2 growth speeding up (vs 3 months ago)"] = g_now > g_3m
    if MAC["vix"] is not None and not np.isnan(MAC["vix"][i]):
        r["VIX 30+ (fear)"] = MAC["vix"][i] >= 30
        r["VIX up 30%+ in 5 days (spike)"] = chg(MAC["vix"], i, 5) >= 0.3 if not np.isnan(chg(MAC["vix"], i, 5)) else np.nan
    r["S&P 500 above its 200-day EMA"] = ema_above(MAC["spx"], i)
    r["S&P 500 up over 30 days"] = (chg(MAC["spx"], i, 30) > 0) if not np.isnan(chg(MAC["spx"], i, 30)) else np.nan
    r["Gold up over 30 days"] = (chg(MAC["gold"], i, 30) > 0) if not np.isnan(chg(MAC["gold"], i, 30)) else np.nan
    if "usdt_d" in MAC:
        c = chg(MAC["usdt_d"], i, 30)
        r["USDT dominance up over 30 days"] = (c > 0) if not np.isnan(c) else np.nan
    if MAC["btc_d"] is not None:
        c = chg(MAC["btc_d"], i, 30)
        r["BTC dominance up over 30 days"] = (c > 0) if not np.isnan(c) else np.nan
    return r


# ---------------- assemble ----------------
lo10 = pd.Series(C).rolling(10).min().values
hi10 = pd.Series(C).rolling(10).max().values
is_ext = lambda i, s: (C[i] <= lo10[i]) if s > 0 else (C[i] >= hi10[i])
four = lambda x: (x.prior7.le(-10).astype(int) + x.prior30.le(-20).astype(int) + x.vol_bs.ge(1.5).astype(int) + x.zW2_any.astype(int))

t10 = T[T.level == 10]
near = {(k, s) for i, s in zip(t10.i, t10.s) for k in range(i - 3, i + 4)}
LA = B[[(i, s) not in near and is_ext(i, s) for i, s in zip(B.i, B.s)]].copy()   # look-alike days
LA["four"] = four(LA)
T["four"] = four(T)

FT = pd.DataFrame([items(int(i), int(s)) for i, s in zip(T.i, T.s)], index=T.index)
FL = pd.DataFrame([items(int(i), int(s)) for i, s in zip(LA.i, LA.s)], index=LA.index)
# rename side-specific divergence labels to one item
for F in (FT, FL):
    a, b = "Slow: RSI divergence (lower low in price, higher low in RSI)", "Slow: RSI divergence (higher high in price, lower high in RSI)"
    F["Slow: RSI divergence"] = F[a].where(F[a].notna(), F.get(b))
    F.drop(columns=[c for c in (a, b) if c in F.columns], inplace=True)
cols = [c for c in FT.columns]
half = lambda idx: np.where(px.time.values[idx] < pd.Timestamp("2019-01-01"), "2011-18", "2019-26")
T["half"], LA["half"] = half(T.i.astype(int).values), half(LA.i.astype(int).values)


def rate(F, mask, c):
    x = F.loc[mask, c].dropna()
    return (x.astype(float).mean(), len(x)) if len(x) else (np.nan, 0)


out = {}
lines = ["# Step 5: market context and slow turns", "",
         "Lift = how often the item was present at real turns / at look-alike days (new 10-day closing extremes that did "
         "not turn). Keep rule: >= 1.2 in both halves or <= 0.83 in both halves, 8+ turns per half, and the item common enough "
         "to judge (present at 5+ turns per half, or expected at 5+ turns per half for 'less at turns').", ""]
for subset in ("all", "slow"):
    for lvl in (10, 20):
        for side, sv in (("bottoms", 1), ("tops", -1)):
            tm = (T.level == lvl) & (T.s == sv) & ((T.four < 2) if subset == "slow" else True)
            lm = (LA.s == sv) & ((LA.four < 2) if subset == "slow" else True)
            key = f"{subset}|{lvl}|{side}"
            rows = []
            for c in cols:
                rr = {"item": c}
                for h in ("all", "2011-18", "2019-26"):
                    a, na = rate(FT, tm & ((T.half == h) if h != "all" else True), c)
                    b, nb = rate(FL, lm & ((LA.half == h) if h != "all" else True), c)
                    rr[h] = dict(turn=None if np.isnan(a) else round(100 * a, 1), la=None if np.isnan(b) else round(100 * b, 1),
                                 lift=None if (np.isnan(a) or np.isnan(b) or b == 0) else round(a / b, 2), n=na)
                l1, l2 = rr["2011-18"]["lift"], rr["2019-26"]["lift"]
                # enough data: 8+ turns per half, and the item must be common enough to judge: present at 5+ turns
                # per half (for "more at turns") or expected at 5+ turns per half from the look-alike rate ("less")
                cnt = lambda h, k: (rr[h][k] or 0) / 100 * rr[h]["n"]
                enough = rr["2011-18"]["n"] >= 8 and rr["2019-26"]["n"] >= 8
                more_ok = cnt("2011-18", "turn") >= 5 and cnt("2019-26", "turn") >= 5
                less_ok = cnt("2011-18", "la") >= 5 and cnt("2019-26", "la") >= 5
                rr["verdict"] = ("not enough data" if not enough or l1 is None or l2 is None else
                                 ("KEEP (more at turns)" if more_ok else "too rare to judge") if (l1 >= 1.2 and l2 >= 1.2) else
                                 ("KEEP (less at turns)" if less_ok else "too rare to judge") if (l1 <= 0.83 and l2 <= 0.83) else "drop")
                rows.append(rr)
            out[key] = rows
            nt = int(tm.sum())
            lines += [f"## {'Slow turns' if subset == 'slow' else 'All turns'}: {lvl}% {side} ({nt} turns)", "",
                      "| Item | At turns | Look-alike days | Lift 2011-18 | Lift 2019-26 | Verdict |", "|---|---|---|---|---|---|"]
            for rr in rows:
                a = rr["all"]
                if a["turn"] is None:
                    continue
                lines.append(f"| {rr['item']} | {a['turn']}% (n={a['n']}) | {a['la']}% | {rr['2011-18']['lift']} | {rr['2019-26']['lift']} | {rr['verdict']} |")
            lines.append("")

avail = {k: (None if v is None else int(np.isfinite(v).sum())) for k, v in MAC.items()}
lines += ["## Data used", "", "Days with a value, per series (None = not fetched yet): " + json.dumps(avail), ""]
(HERE / "context_results.md").write_text("\n".join(lines))
json.dump(out, open(HERE / "context_summary.json", "w"), indent=1)
# per-turn context for the page
snap = {}
for k, r in T.iterrows():
    on = [c for c in cols if FT.loc[k, c] is True or FT.loc[k, c] == 1.0]
    snap[f"{int(r.level)}|{r.start_date}"] = on
json.dump(snap, open(HERE / "context_snapshots.json", "w"))
print("\n".join(lines))
