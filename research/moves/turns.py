"""
Step 3: reverse-engineer the turning points.

For every confirmed move on DAILY CLOSES (10/20/30/50%), take a snapshot of the chart at the move's start
(the turning point) with a fixed checklist. Compare how often each item is present at turning points vs on
ordinary days, by era, and group the turns whose snapshots match.

Every item uses only data known at the close of the turn day, except daily CHoCH (it comes after the turn;
its own date is recorded). The turn itself is only known on the move's confirmation date (see moves.csv).

Variants asked for: zones with the 2x displacement filter (X=2) and without it (X=0);
volume from Bitstamp and from Binance spot (Binance starts Aug 2017).
"""
import sys, json
from pathlib import Path
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT / "bot"))
from zones import find_fvgs, find_obs, dedupe  # noqa: E402
from structure import trend_state  # noqa: E402

D1, W1 = pd.Timedelta(days=1), pd.Timedelta(days=7)
ERAS = [("2011-16", "2011-01-01", "2016-07-01"), ("2016-21", "2016-07-01", "2021-07-01"), ("2021-26", "2021-07-01", "2030-01-01")]

# ---------------- data ----------------
d = pd.read_csv(ROOT / "data/btc_1D.csv").rename(columns={"Volume": "volume"})
d["time"] = pd.to_datetime(d.time, unit="s", utc=True)
n = len(d)
O, H, L, C, V = (d[k].values for k in ("open", "high", "low", "close", "volume"))
pc = np.r_[C[0], C[:-1]]
atrp = pd.Series(np.maximum(H - L, np.maximum(abs(H - pc), abs(L - pc)))).ewm(alpha=1 / 14, adjust=False).mean().values / C * 100


def ema(x, k):
    return x.ewm(span=k, adjust=False).mean()


W = (d.set_index("time").resample("W-MON", label="left", closed="left")
     .agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}).dropna().reset_index())
W["e50"], W["e200"] = ema(W.close, 50), ema(W.close, 200)
wstate, _, _ = trend_state(W, 2)
dstate, _, devents = trend_state(d, 2)
wclose = (W.time + W1).values          # weekly candle close time
dclose = (d.time + D1).values          # daily candle close time
wk_at = np.searchsorted(wclose, dclose, side="right") - 1   # last weekly candle closed by each daily close

# Binance spot volume / taker-buy share, and derivatives (aligned to Bitstamp days)
def by_day(path, cols):
    x = pd.read_csv(ROOT / path)
    x["time"] = pd.to_datetime(x.time, utc=True, format="mixed").dt.floor("D")
    return x.groupby("time")[cols].last() if cols else x


bs = by_day("data/binance_spot_1D.csv", ["volume", "taker_buy_volume"])
bp = by_day("data/binance_perp_1D.csv", ["volume", "taker_buy_volume"])
oi = by_day("data/binance_oi_1D.csv", ["sum_open_interest"]).replace(0, np.nan)
fu = pd.read_csv(ROOT / "data/binance_funding.csv")
fu["time"] = pd.to_datetime(fu.time, utc=True, format="mixed").dt.floor("D")
fu = fu.groupby("time").last_funding_rate.sum().to_frame("fund")   # sum of the day's fundings
ext = pd.DataFrame(index=d.time)
ext["bvol"] = bs.volume
ext["bshare"] = bs.taker_buy_volume / bs.volume
ext["pshare"] = bp.taker_buy_volume / bp.volume
ext["oi"] = oi.sum_open_interest
ext["fund"] = fu.fund
ext = ext.reset_index(drop=True)


# ---------------- zones ----------------
def zone_table(frame, X, bar):
    zs = dedupe(find_fvgs(frame, X) + find_obs(frame, X))
    out = []
    for z in zs:
        kt = frame.time[z["known_idx"]] + bar                        # known at this candle's close
        inv = pd.Timestamp("2100-01-01", tz="UTC")
        for t in range(z["known_idx"] + 1, len(frame)):
            if (z["side"] == "bull" and frame.close[t] < z["bottom"]) or (z["side"] == "bear" and frame.close[t] > z["top"]):
                inv = frame.time[t] + bar
                break
        out.append((z["side"], z["bottom"], z["top"], kt, inv))
    return out


def prep(zt):
    """Arrays per zone, plus the first daily candle that touched it after it became known."""
    side = np.array([z[0] == "bull" for z in zt]); bot = np.array([z[1] for z in zt]); top = np.array([z[2] for z in zt])
    kt = np.array([np.datetime64(z[3].tz_convert(None)) for z in zt]); inv = np.array([np.datetime64(z[4].tz_convert(None)) for z in zt])
    j0 = np.searchsorted(dclose, kt, side="left")          # first daily candle closing at/after known time
    first = np.full(len(zt), n)
    for q in range(len(zt)):
        seg = slice(j0[q], n)
        hit = (L[seg] <= top[q]) if side[q] else (H[seg] >= bot[q])
        w = np.flatnonzero(hit)
        if len(w):
            first[q] = j0[q] + w[0]
    return dict(side=side, bot=bot, top=top, kt=kt, inv=inv, first=first)


DOPEN = d.time.dt.tz_convert(None).values


def zone_hits(z, i, side):
    """At day i: does the turn day's extreme reach an active zone of the supporting side?
    any = an active zone (known before the day opened, not closed through). new = it is the first touch."""
    t_open = DOPEN[i]
    bull = side == "bull"
    act = (z["side"] == bull) & (z["kt"] <= t_open) & (z["inv"] > t_open)
    hit = act & ((L[i] <= z["top"]) & (C[i] >= z["bot"]) if bull else (H[i] >= z["bot"]) & (C[i] <= z["top"]))
    return bool(hit.any()), bool((hit & (z["first"] >= i)).any())


ZT = {("W", X): prep(zone_table(W, X, W1)) for X in (2.0, 0.0)}
ZT.update({("D", X): prep(zone_table(d, X, D1)) for X in (2.0, 0.0)})
print({k: len(v["bot"]) for k, v in ZT.items()})

choch = {+1: sorted(e["idx"] for e in devents if e["kind"] == "CHoCH" and e["dir"] == "up"),
         -1: sorted(e["idx"] for e in devents if e["kind"] == "CHoCH" and e["dir"] == "down")}


def snapshot(i, s):
    """s=+1: candidate bottom (an up move starts here). s=-1: candidate top."""
    side = "bull" if s > 0 else "bear"
    k = wk_at[i]
    r = dict(i=i, s=s)
    if k >= 0:
        r["ema_with"] = (W.e50[k] > W.e200[k]) == (s > 0)
        r["struct_with"] = wstate[k] == side
        r["struct_set"] = wstate[k] != ""
        r["d50"] = (C[i] / W.e50[k] - 1) * 100
        r["d200"] = (C[i] / W.e200[k] - 1) * 100
    r["dstruct_with"] = dstate[i] == side
    for tf in ("W", "D"):
        for X in (2.0, 0.0):
            a, u = zone_hits(ZT[(tf, X)], i, side)
            tag = f"{tf}{int(X)}"
            r[f"z{tag}_any"], r[f"z{tag}_new"] = a, u
    r["prior7"] = (C[i] / C[i - 7] - 1) * 100 * s if i >= 7 else np.nan      # negative = moved against the new move
    r["prior30"] = (C[i] / C[i - 30] - 1) * 100 * s if i >= 30 else np.nan
    r["prior7_atr"] = r["prior7"] / atrp[i]
    rng = H[i] - L[i]
    r["wick"] = ((min(O[i], C[i]) - L[i]) if s > 0 else (H[i] - max(O[i], C[i]))) / rng if rng > 0 else np.nan
    r["vol_bs"] = V[i] / V[max(0, i - 20):i].mean() if i >= 20 else np.nan
    bv = ext.bvol.values
    r["vol_bn"] = bv[i] / np.nanmean(bv[i - 20:i]) if i >= 20 and not np.isnan(bv[i]) else np.nan
    sh = ext.bshare.values
    r["buy_dev_bn"] = (sh[i] - np.nanmean(sh[i - 20:i])) * 100 * s if i >= 20 and not np.isnan(sh[i]) else np.nan
    o = ext.oi.values
    r["oi7"] = (o[i] / o[i - 7] - 1) * 100 if i >= 7 and not np.isnan(o[i]) and not np.isnan(o[i - 7]) else np.nan
    f = ext.fund.values
    r["fund7"] = np.nansum(f[i - 6:i + 1]) * 100 if i >= 6 and not np.isnan(f[i]) else np.nan   # % paid over 7 days
    return r


# ---------------- turning points ----------------
mv = pd.read_csv(HERE / "moves.csv")
mv = mv[(mv.basis == "close")].copy()
EX = {  # the user's example moves (start date, level)
    ("2021-11-08", 50): "Nov 2021 top", ("2022-11-21", 30): "Nov 2022 bottom", ("2020-03-12", 20): "Mar 2020 bottom",
    ("2023-09-11", 20): "Sep 2023 bottom", ("2024-12-17", 20): "Dec 2024 top", ("2026-03-29", 10): "Mar 2026 bottom",
    ("2026-06-30", 10): "Jun 2026 bottom",
}
EX_ANY = {k[0]: v for k, v in EX.items()}


def era_of(i):
    t = d.time[i].tz_convert(None)
    for name, a, b in ERAS:
        if pd.Timestamp(a) <= t < pd.Timestamp(b):
            return name


rows = []
for m in mv.itertuples():
    i, s = int(m.start), (1 if m.dir == "up" else -1)
    if i < 30:
        continue
    r = snapshot(i, s)
    nxt = [j for j in choch[s] if j >= i]
    j = nxt[0] if nxt else None
    r.update(level=int(m.level), start_date=str(m.start_date)[:10], end_date=str(m.end_date)[:10], pct=m.pct, days=m.days,
             open=bool(m.open), confirmed_date=None if pd.isna(m.confirmed_date) else str(m.confirmed_date)[:10],
             era=era_of(i), example=EX.get((str(m.start_date)[:10], int(m.level))),
             choch_days=(j - i) if j is not None else np.nan,
             choch_in_move=bool(j is not None and j <= m.end),
             choch_date=str(d.time[j].date() + pd.Timedelta(days=1)) if j is not None else None,
             choch_gain=((C[j] / C[i] - 1) * 100 * s) if j is not None else np.nan,
             move_left_after_choch=((m.pe / C[j] - 1) * 100 * s) if j is not None and j <= m.end else np.nan)
    rows.append(r)
T = pd.DataFrame(rows)
T.to_csv(HERE / "turns.csv", index=False)

# ordinary days: every day from day 30, as a candidate bottom and as a candidate top
base = pd.DataFrame([snapshot(i, s) for i in range(30, n) for s in (1, -1)])
base["era"] = [era_of(i) for i in base.i]
base.to_csv(HERE / "days.csv", index=False)
print("turns", len(T), "day-sides", len(base))
