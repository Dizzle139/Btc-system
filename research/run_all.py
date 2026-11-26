#!/usr/bin/env python3
"""
One command reproduces every result in the rules ledger, and runs the derivative tests
when that data exists.   python research/run_all.py   ->  research/results.md

Standard for every rule: beat random IN THE SAME ERA, in every era. Not financial advice.
"""
import sys, os, time
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
from feats import *   # ema, rsi, stochrsi, add, held_rate, zones, structure

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = []
RNG = np.random.default_rng(2026)
ERAS = [("2012-2016", "2012-01-01", "2016-05-01"), ("2016-2021", "2016-05-01", "2021-01-01"), ("2021-2026", "2021-01-01", "2030-01-01")]
T0 = time.time()


def say(s=""):
    print(s)
    OUT.append(s)


def ts(s):
    return pd.Timestamp(s, tz="UTC")


def load_any(p):
    d = pd.read_csv(p).rename(columns={"Volume": "volume"})
    t = d["time"]
    d["time"] = pd.to_datetime(t.astype("int64"), unit="s", utc=True) if pd.api.types.is_numeric_dtype(t) else pd.to_datetime(t, utc=True)
    if "volume" not in d:
        d["volume"] = 0.0
    return d.sort_values("time").drop_duplicates("time").reset_index(drop=True)


def closed(d, bar):
    return d[d.time + bar <= pd.Timestamp.now(tz="UTC")].reset_index(drop=True)


# ---------------------------------------------------------------- data
D = closed(load_any(DATA / "btc_1D.csv"), pd.Timedelta(days=1))
D = D[D.time >= "2011-11-01"].reset_index(drop=True)
W = (D.set_index("time").resample("W-MON", label="left", closed="left")
     .agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}).dropna().reset_index())
W = W[W.time + pd.Timedelta(days=7) <= D.time.iloc[-1] + pd.Timedelta(days=1)].reset_index(drop=True)
W, D = add(W), add(D)
H = add(closed(load_any(DATA / "btc_4H.csv"), pd.Timedelta(hours=4))) if (DATA / "btc_4H.csv").exists() else None
WS, _, _ = trend_state(W, 2)
WCT = (W.time + pd.Timedelta(days=7)).values


def wctx(t):
    k = np.searchsorted(WCT, np.datetime64(t.tz_convert(None)), side="right") - 1
    return (None, None) if k < 0 else (WS[k], "bull" if W.e50[k] > W.e200[k] else "bear")


say(f"# Research results ({pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC)\n")
say("## 0. Data")
for name, d, step in [("BTC daily", D, pd.Timedelta(days=1)), ("BTC weekly (built from daily)", W, pd.Timedelta(days=7)),
                      ("BTC 4H", H, pd.Timedelta(hours=4))]:
    if d is None:
        say(f"- {name}: missing"); continue
    g = d.time.diff().dropna()
    bad = ((d.high < d[["open", "close"]].max(axis=1)) | (d.low > d[["open", "close"]].min(axis=1))).sum()
    say(f"- {name}: {len(d)} candles, {d.time.iloc[0]:%Y-%m-%d} to {d.time.iloc[-1]:%Y-%m-%d}, gaps {(g != step).sum()}, impossible candles {bad}")

# ---------------------------------------------------------------- 1. weekly zones (the map)
say("\n## 1. Weekly zones held vs random (era-matched)")
zsW = dedupe(find_fvgs(W, 2) + find_obs(W, 2))
r = evaluate(W, zsW, W.atr)
b = random_baseline(W, zsW, W.atr, RNG, reps=50)
for x in (r, b):
    x["t"] = [W.time[k] for k in x.known_idx]
    x["ema"] = [(s == "bull") == (W.e50[k] > W.e200[k]) for s, k in zip(x.side, x.known_idx)]
    x["st"] = [WS[k] == s for s, k in zip(x.side, x.known_idx)]
say("| filter | " + " | ".join(e[0] for e in ERAS) + " |")
say("|---|" + "---|" * len(ERAS))
for lab, f in [("EMA agrees", lambda x: x.ema), ("EMA + structure agree", lambda x: x.ema & x.st), ("EMA against", lambda x: ~x.ema)]:
    cells = []
    for _, lo, hi in ERAS:
        m = lambda x: f(x) & (x.t >= ts(lo)) & (x.t < ts(hi))
        h, n = held_rate(r[m(r)]); hb, _ = held_rate(b[m(b)])
        cells.append(f"{h:.0%} vs {hb:.0%} (n={n})")
    say(f"| {lab} | " + " | ".join(cells) + " |")
r["score"] = r.ema.astype(int) + r.st.astype(int)
say("\nConviction (EMA + structure) : " + " | ".join(f"{s}/2 held {held_rate(r[r.score == s])[0]:.0%} (n={held_rate(r[r.score == s])[1]})" for s in [0, 1, 2]))


# ---------------------------------------------------------------- trade simulator
def sim(d, i, e, stop, tgt, hz, side="bull"):
    risk = abs(e - stop)
    for t in range(i + 1, min(len(d), i + 1 + hz)):
        if (side == "bull" and d.low[t] <= stop) or (side == "bear" and d.high[t] >= stop):
            return -1.0
        if (side == "bull" and d.high[t] >= tgt) or (side == "bear" and d.low[t] <= tgt):
            return abs(tgt - e) / risk
    j = min(len(d) - 1, i + hz)
    return (d.close[j] - e) / risk * (1 if side == "bull" else -1)


def triggers(d, piv, lb, hz, cost=0.002):
    _, _, ev = trend_state(d, piv)
    bar = d.time[1] - d.time[0]
    rows = []
    for e_ in ev:
        if e_["kind"] != "CHoCH" or e_["dir"] != "up":
            continue
        i = e_["idx"]
        e = d.close[i]
        lo = d.low[max(0, i - lb):i + 1].min()
        stop = lo - 0.25 * d.atr[i]
        risk = e - stop
        if risk <= 0:
            continue
        s, em = wctx(d.time[i] + bar)
        rows.append(dict(i=i, time=d.time[i], struct=s == "bull", ema=em == "bull", risk=risk / e,
                         r3=sim(d, i, e, stop, e + 3 * risk, hz) - cost / (risk / e)))
    return pd.DataFrame(rows)


def random_same(d, sub, cond, hz, reps=300):
    """random entries, same era, same regime condition, same stop distances, 3R"""
    out = []
    for en, lo, hi in ERAS:
        x = sub[(sub.time >= ts(lo)) & (sub.time < ts(hi))]
        pool = d.index[(d.time >= ts(lo)) & (d.time < ts(hi)) & cond & (d.index < len(d) - hz - 1)]
        if len(x) == 0 or len(pool) == 0:
            out.append(f"{en}: -"); continue
        sims = []
        for _ in range(reps):
            v = []
            for rk in x.risk:
                i = int(RNG.choice(pool)); e = d.close[i]; stop = e * (1 - rk)
                v.append(sim(d, i, e, stop, e + 3 * (e - stop), hz) - 0.002 / rk)
            sims.append(np.mean(v))
        out.append(f"{en}: {x.r3.mean():+.2f}R vs random {np.mean(sims):+.2f}R (n={len(x)})")
    return " | ".join(out)


# ---------------------------------------------------------------- 2. daily trigger
say("\n## 2. Daily trigger (daily CHoCH up, stop below 10-day low, 3R, 90 days, 0.2% costs)")
TD = triggers(D, 2, 10, 90)
D["ws"] = [wctx(t + pd.Timedelta(days=1))[0] for t in D.time]
D["we"] = [wctx(t + pd.Timedelta(days=1))[1] for t in D.time]
for lab, m, cond in [("Grade A (EMA + structure bull)", TD.ema & TD.struct, (D.ws == "bull") & (D.we == "bull")),
                     ("Grade B (EMA bull, structure not)", TD.ema & ~TD.struct, (D.we == "bull") & (D.ws != "bull")),
                     ("Any regime", TD.ema | ~TD.ema, D.index >= 0)]:
    x = TD[m]
    say(f"- {lab}: n={len(x)}, win {np.mean(x.r3 >= 2.9):.0%}, avg {x.r3.mean():+.2f}R | " + random_same(D, x, cond, 90))

# ---------------------------------------------------------------- 3. withdrawn rules (kept to show they still fail)
say("\n## 3. Withdrawn rules, re-checked")
# weekly flush long vs random same era
def weekly_flush(drop=0.20, look=8, wick=0.4):
    rows = []
    last = -99
    for i in range(look, len(W) - 1):
        if i - last < look:
            continue
        hw, lw = W.high[i - look + 1:i + 1], W.low[i - look + 1:i + 1]
        rg = W.high[i] - W.low[i]
        if rg <= 0:
            continue
        bb = min(W.open[i], W.close[i])
        if (hw.max() - W.low[i]) / hw.max() >= drop and W.low[i] == lw.min() and (bb - W.low[i]) / rg >= wick:
            last = i
            e, stop = W.close[i], W.low[i] - 0.25 * W.atr[i]
            rows.append(dict(i=i, time=W.time[i], risk=(e - stop) / e, r3=sim(W, i, e, stop, e + 3 * (e - stop), 52)))
    return pd.DataFrame(rows)
WF = weekly_flush()
say("- Weekly flush long (20%/8w/40% wick): " + random_same(W, WF, W.index >= 0, 52, reps=300))
# daily zones by era
for name, zs in [("Daily OB", dedupe(find_obs(D, 2))), ("Daily FVG", dedupe(find_fvgs(D, 2)))]:
    rr = evaluate(D, zs, D.atr); bb = random_baseline(D, zs, D.atr, RNG, reps=10)
    for x in (rr, bb):
        x["t"] = [D.time[k] for k in x.known_idx]
    cells = []
    for en, lo, hi in ERAS:
        h, n = held_rate(rr[(rr.t >= ts(lo)) & (rr.t < ts(hi))]); hb, _ = held_rate(bb[(bb.t >= ts(lo)) & (bb.t < ts(hi))])
        cells.append(f"{en} {h:.0%} vs {hb:.0%} (n={n})")
    say(f"- {name} held vs random: " + " | ".join(cells))

# ---------------------------------------------------------------- 4. optional data sets
say("\n## 4. Extra data (runs when the file exists)")
p = DATA / "usdtd_1W.csv"
if p.exists():
    U = load_any(p)[["time", "close"]].rename(columns={"close": "u"})
    M = W.merge(U, on="time")
    M = M[M.time >= "2018-01-01"]
    rb, ru = M.close.pct_change(), M.u.pct_change()
    say(f"- USDT.D vs BTC weekly change correlation {rb.corr(ru):+.2f}; with BTC one week later {ru.corr(rb.shift(-1)):+.2f} (no lead if ~0)")

p_oi, p_f, p_perp = DATA / "binance_oi_1D.csv", DATA / "binance_funding.csv", DATA / "binance_perp_1D.csv"
if p_oi.exists() and p_f.exists() and p_perp.exists():
    X = D[["time", "close", "low"]].copy()
    oi = load_any(p_oi)[["time", "sum_open_interest_value"]].rename(columns={"sum_open_interest_value": "oi"})
    oi.loc[oi.oi <= 0, "oi"] = np.nan                       # 2 bad zero readings in the archive
    X = X.merge(oi, on="time", how="left")
    X["oi_chg7"] = X.oi / X.oi.shift(7) - 1
    f = load_any(p_f); f["day"] = f.time.dt.normalize()
    X = X.merge(f.groupby("day").last_funding_rate.sum().rename("fund").reset_index().rename(columns={"day": "time"}), on="time", how="left")
    X["fund7"] = X.fund.rolling(7).sum()
    k = load_any(p_perp); k["buy_share"] = k.taker_buy_volume / k.volume
    X = X.merge(k[["time", "buy_share"]], on="time", how="left")
    X["buy7"] = X.buy_share.rolling(7).mean()
    for h_ in (7, 30):
        X[f"f{h_}"] = X.close.shift(-h_) / X.close - 1
    X["chg7"] = X.close / X.close.shift(7) - 1
    mid = ts("2024-05-01")
    def ev(mask, lab):
        x = X[mask & X.f30.notna()]
        base = X[X.oi.notna() & X.f30.notna()]
        parts = []
        for pn, sel in (("Dec21-Apr24", x.time < mid), ("May24-Nov26", x.time >= mid)):
            xx, bb = x[sel], base[(base.time < mid) if pn.startswith("Dec") else (base.time >= mid)]
            parts.append(f"{pn}: 30d {100 * xx.f30.mean():+.1f}% vs all days {100 * bb.f30.mean():+.1f}% (n={len(xx)})")
        say(f"- {lab}: " + " | ".join(parts))
    say("BTC forward return after each derivatives condition (Binance BTCUSDT perpetual; all days with data as baseline):")
    ev(X.oi_chg7 <= -0.15, "Open interest fell >=15% in 7 days (leverage flush)")
    ev((X.oi_chg7 <= -0.15) & (X.chg7 <= -0.10), "OI fell >=15% AND price fell >=10% in 7 days (long liquidation flush)")
    ev(X.oi_chg7 >= 0.15, "Open interest rose >=15% in 7 days (leverage building)")
    ev(X.fund7 < 0, "7-day funding negative (shorts paying)")
    ev(X.fund7 > X.fund7.quantile(0.9), "7-day funding in top 10% (longs crowded)")
    ev(X.buy7 > 0.52, "7-day taker-buy share > 52% (aggressive buyers)")
    ev(X.buy7 < 0.48, "7-day taker-buy share < 48% (aggressive sellers)")
    tr = TD.merge(X[["time", "oi_chg7", "fund7", "buy7"]], on="time", how="left")
    tr = tr[tr.oi_chg7.notna()]
    say(f"\nDaily triggers with derivatives data: {len(tr)} (Dec 2021 onward)")
    for lab, m in [("OI fell >=10% in prior 7 days", tr.oi_chg7 <= -0.10), ("7-day funding negative", tr.fund7 < 0),
                   ("7-day taker-buy share > 50%", tr.buy7 > 0.50)]:
        a_, b_ = tr[m], tr[~m]
        say(f"- {lab}: with {a_.r3.mean():+.2f}R (n={len(a_)}) vs without {b_.r3.mean():+.2f}R (n={len(b_)})")
    X.to_csv(ROOT / "research" / "derivatives_daily.csv", index=False)
else:
    say("- Binance open interest / funding / taker volume: not downloaded yet (run the Data agent workflow)")

say(f"\n_Runtime {time.time() - T0:.0f}s. Weekly rules were built on 2016-2026; 2012-2016 is unseen data for them._")
(Path(__file__).resolve().parent / "results.md").write_text("\n".join(OUT) + "\n")
