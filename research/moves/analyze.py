"""Compare turning-point snapshots with ordinary days; group matching setups. Writes results.md + summary.json."""
import json
from pathlib import Path
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
T = pd.read_csv(HERE / "turns.csv")
B = pd.read_csv(HERE / "days.csv")

# ordinary days: not within 3 days of any 10% close turn on the same side (the strictest answer key)
t10 = T[T.level == 10]
near = set()
for i, s in zip(t10.i, t10.s):
    for k in range(i - 3, i + 4):
        near.add((k, s))
B = B[[(i, s) not in near for i, s in zip(B.i, B.s)]].copy()
# harder comparison: "extreme days" = ordinary days that were also a new 10-day closing low (candidate bottom) or high
# (candidate top). Every turn is such a day, so this removes the built-in advantage of "price just moved a lot".
Cc = pd.read_csv(HERE.parent.parent / "data/btc_1D.csv").close.values
lo10 = pd.Series(Cc).rolling(10).min().values; hi10 = pd.Series(Cc).rolling(10).max().values
B["extreme"] = [(Cc[i] <= lo10[i]) if s > 0 else (Cc[i] >= hi10[i]) for i, s in zip(B.i, B.s)]
T["extreme"] = [(Cc[i] <= lo10[i]) if s > 0 else (Cc[i] >= hi10[i]) for i, s in zip(T.i, T.s)]
print("turns that are 10-day extremes:", round(T.extreme.mean() * 100, 1), "%; extreme ordinary day-sides:", int(B.extreme.sum()))

# daily CHoCH in the new direction within 10 days, also for ordinary days (comparison only, it is after the day)
d_events = {}
T["C10"] = T.choch_days.le(10) & T.choch_in_move


def flags(x):
    f = pd.DataFrame(index=x.index)
    f["Weekly EMA agrees"] = x.ema_with.astype(bool)
    f["Weekly structure agrees"] = x.struct_with.astype(bool)
    f["Daily structure agrees"] = x.dstruct_with.astype(bool)
    f["Weekly zone, 2x filter"] = x.zW2_any.astype(bool)
    f["Weekly zone, 2x, first touch"] = x.zW2_new.astype(bool)
    f["Weekly zone, no filter"] = x.zW0_any.astype(bool)
    f["Weekly zone, no filter, first touch"] = x.zW0_new.astype(bool)
    f["Daily zone, 2x filter"] = x.zD2_any.astype(bool)
    f["Daily zone, 2x, first touch"] = x.zD2_new.astype(bool)
    f["Daily zone, no filter"] = x.zD0_any.astype(bool)
    f["Daily zone, no filter, first touch"] = x.zD0_new.astype(bool)
    f["Sharp move into the turn: 10%+ in 7 days"] = x.prior7.le(-10)
    f["Sharp move into the turn: 3+ daily ranges in 7 days"] = x.prior7_atr.le(-3)
    f["Extended into the turn: 20%+ in 30 days"] = x.prior30.le(-20)
    f["Stretched: 20%+ past weekly EMA50"] = (x.d50 * x.s).le(-20)
    f["Past weekly EMA200"] = (x.d200 * x.s).lt(0)
    f["Wick 40%+ of range (rejection)"] = x.wick.ge(0.4)
    f["Volume 1.5x+ (Bitstamp)"] = x.vol_bs.ge(1.5)
    f["Volume 1.5x+ (Binance, 2017+)"] = x.vol_bn.ge(1.5).where(x.vol_bn.notna())
    f["Buy/sell share already favours the new move (Binance)"] = x.buy_dev_bn.gt(0).where(x.buy_dev_bn.notna())
    f["Open interest down 10%+ in 7 days (2021+)"] = x.oi7.le(-10).where(x.oi7.notna())
    f["Funding against the new move over 7 days (2020+)"] = (x.fund7 * x.s).lt(0).where(x.fund7.notna())
    return f


FT, FB = flags(T), flags(B)
ERAS = ["2011-16", "2016-21", "2021-26"]


def rate(f, mask):
    col = f[mask]
    col = col.dropna()
    return (col.astype(bool).mean() if len(col) else np.nan), len(col)


out = {"lift": {}, "combos": {}, "examples": [], "counts": {}}
lines = ["# Step 3: what was on the chart at each turning point", "",
         "Daily closes, Bitstamp. A turning point = the start of a confirmed move. Lift = how often the item was present "
         "at turning points divided by how often on ordinary days (same side: bottoms compared with all days as candidate "
         "bottoms, tops with candidate tops). Lift above 1 = shows up more at turns than on ordinary days. "
         "Ordinary days exclude the 3 days either side of any 10% turn. The era columns are lift vs extreme days.", ""]
for lvl in (10, 20, 30, 50):
    tm = T.level == lvl
    out["counts"][lvl] = {e: int((tm & (T.era == e)).sum()) for e in ERAS}
    rows = []
    for c in FT.columns:
        row = {"item": c}
        for e in ["all"] + ERAS:
            mt = tm & ((T.era == e) if e != "all" else True)
            mb = (B.era == e) if e != "all" else pd.Series(True, index=B.index)
            rt, nt = rate(FT[c], mt)
            rb, nb = rate(FB[c], mb)
            rx, nx = rate(FB[c], mb & B.extreme)
            row[e] = dict(turn=None if np.isnan(rt) else round(rt * 100, 1), base=None if np.isnan(rb) else round(rb * 100, 1),
                          lift=None if (np.isnan(rt) or not rb) else round(rt / rb, 2), n=nt,
                          ext=None if np.isnan(rx) else round(rx * 100, 1), lift_ext=None if (np.isnan(rt) or not rx) else round(rt / rx, 2))
        rows.append(row)
    out["lift"][lvl] = rows
    lines += [f"## {lvl}% moves: {int(tm.sum())} turning points ({', '.join(f'{e}: {out['counts'][lvl][e]}' for e in ERAS)})", "",
              "| Item | At turns | Ordinary days | Lift | New 10-day extreme days | Lift vs extremes | 2011-16 | 2016-21 | 2021-26 |", "|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        a = r["all"]
        if a["turn"] is None:
            continue
        lines.append(f"| {r['item']} | {a['turn']}% (n={a['n']}) | {a['base']}% | {a['lift']} | {a['ext']}% | {a['lift_ext']} | "
                     + " | ".join(f"{r[e]['lift_ext']}" if r[e]['lift_ext'] is not None else "–" for e in ERAS) + " |")
    lines.append("")

# setups: group turns by a fixed core checklist
CORE = ["Weekly EMA agrees", "Weekly structure agrees", "Weekly zone, 2x filter", "Daily zone, 2x filter",
        "Sharp move into the turn: 10%+ in 7 days", "Wick 40%+ of range (rejection)", "Volume 1.5x+ (Bitstamp)"]
SHORT = ["EMA", "Structure", "Weekly zone", "Daily zone", "Sharp move", "Wick", "Volume"]


def sig(f):
    return f[CORE].fillna(False).astype(bool).apply(lambda r: " + ".join(s for s, v in zip(SHORT, r) if v) or "(none)", axis=1)


ST, SB = sig(FT), sig(FB)
for lvl in (10, 20, 30, 50):
    tm = T.level == lvl
    vc = ST[tm].value_counts()
    rows = []
    for k, cnt in vc.items():
        nb = int(((SB == k) & B.extreme).sum())
        eras = {e: int(((ST == k) & tm & (T.era == e)).sum()) for e in ERAS}
        rows.append(dict(setup=k, turns=int(cnt), share=round(100 * cnt / tm.sum(), 1), ordinary_days=nb,
                         turns_per_100_days=round(100 * cnt / max(nb + cnt, 1), 1), eras=eras))
    out["combos"][lvl] = rows
    lines += [f"## Matching setups, {lvl}% moves", "", "| Setup at the turn | Turns | Share | Non-turn extreme days with it | Turns per 100 such days | 2011-16 / 2016-21 / 2021-26 |",
              "|---|---|---|---|---|---|"]
    for r in rows[:12]:
        lines.append(f"| {r['setup']} | {r['turns']} | {r['share']}% | {r['ordinary_days']} | {r['turns_per_100_days']} | "
                     f"{r['eras']['2011-16']} / {r['eras']['2016-21']} / {r['eras']['2021-26']} |")
    lines.append("")

# how many core items stack up: turns per 100 days with that many items (turns + non-turn extreme days)
GOOD = ["Sharp move into the turn: 10%+ in 7 days", "Volume 1.5x+ (Bitstamp)", "Weekly zone, 2x filter", "Extended into the turn: 20%+ in 30 days"]
nt = FT[GOOD].fillna(False).astype(bool).sum(axis=1); nb = FB[GOOD].fillna(False).astype(bool).sum(axis=1)
out["stack"] = {}
lines += ["## Stacking the four items that held up (sharp move 7d, extended 30d, volume 1.5x, weekly zone 2x)", "",
          "| Size | Items present | Turns | Share of turns | Non-turn extreme days | Turns per 100 such days | 2021-26 turns / extreme days |", "|---|---|---|---|---|---|---|"]
for lvl in (10, 20, 30, 50):
    tm = T.level == lvl; out["stack"][lvl] = []
    for kk in range(5):
        a = int(((nt == kk) & tm).sum()); b = int(((nb == kk) & B.extreme).sum())
        a3 = int(((nt == kk) & tm & (T.era == "2021-26")).sum()); b3 = int(((nb == kk) & B.extreme & (B.era == "2021-26")).sum())
        out["stack"][lvl].append(dict(k=kk, turns=a, share=round(100 * a / tm.sum(), 1), days=b, per100=round(100 * a / max(a + b, 1), 1), t3=a3, d3=b3))
        lines.append(f"| {lvl}% | {kk} | {a} | {100 * a / tm.sum():.0f}% | {b} | {100 * a / max(a + b, 1):.1f} | {a3} / {b3} |")
lines.append("")

# daily CHoCH after the turn
lines += ["## Daily CHoCH after the turn (comes after the turn, so it is a confirmation, not a warning)", "",
          "| Size | Turns | CHoCH within 10 days, inside the move | Median days to CHoCH | Median % already moved at CHoCH | Median % left in the move after CHoCH |", "|---|---|---|---|---|---|"]
for lvl in (10, 20, 30, 50):
    x = T[T.level == lvl]
    lines.append(f"| {lvl}% | {len(x)} | {100 * x.C10.mean():.0f}% | {x.choch_days.median():.0f} | {x.choch_gain.median():.1f}% | {x.move_left_after_choch.median():.1f}% |")
lines.append("")

# the user's examples
ex = T[T.example.notna()].copy()
fx = FT.loc[ex.index]
lines += ["## Your examples", ""]
for (idx, r) in ex.iterrows():
    on = [c for c in FT.columns if fx.loc[idx, c] is True or fx.loc[idx, c] == 1.0]
    lines.append(f"- **{r.example}** ({r.start_date}, {r.level}% move {r.pct:+.0f}%): " + "; ".join(on)
                 + f". Daily CHoCH {'' if pd.isna(r.choch_days) else f'{int(r.choch_days)} days later'}.")
    out["examples"].append(dict(name=r.example, start=r.start_date, level=int(r.level), pct=r.pct, on=on,
                                choch_days=None if pd.isna(r.choch_days) else int(r.choch_days)))
snap = {f"{r.level}|{r.start_date}": [c for c in FT.columns if FT.loc[k, c] is True or FT.loc[k, c] == 1.0] + ([f"Daily CHoCH {int(r.choch_days)} days later ({r.choch_date})"] if not pd.isna(r.choch_days) and r.choch_in_move else ["No daily CHoCH inside the move"]) for k, r in T.iterrows()}
json.dump(snap, open(HERE / "snapshots.json", "w"))
(HERE / "results.md").write_text("\n".join(lines))
json.dump(out, open(HERE / "summary.json", "w"), indent=1, default=lambda o: None if o is None else (bool(o) if isinstance(o, np.bool_) else int(o)))
print("\n".join(lines))
