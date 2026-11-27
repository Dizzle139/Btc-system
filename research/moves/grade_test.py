"""
Step 6: conviction grades on top of the 2+ item alert. Fixed and approved before running (Nov 27, 2026).

Base alert (step 4): new 10-day closing extreme with 2+ of: sharp 10%/7d, extended 20%/30d, Bitstamp volume 1.5x, weekly zone 2x.
Context points: +1 / -1 per context item (equal), or weighted by strength (ln(lift) / ln(1.5), from the selection period only).
Grades: A = score >= 2, B = 0..1, C = <= -1.

STRICT TEST (the verdict): context items are selected using ONLY 2011-18 (keep rule from step 5 applied to the two
sub-periods 2011-08..2015-06 and 2015-07..2018-12), then alerts are graded and scored ONLY on 2019-26.
FULL CHECK (comparison only): the step-5 items selected on all data, scored on both halves.
Variants: equal vs weighted; dollar + gold items in vs out.
Scoring as step 4: episodes, 5-day window, sizes 10/20/30/50, tops and bottoms.
Pass (strict, 2019-26): hit rate A > B > C, A at least 5 points above the plain 2+ alert, A has 10+ alerts.
Weighted is kept only if its grade A beats equal's grade A by 5+ points.
"""
import contextlib, io, json, sys
from pathlib import Path
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
with contextlib.redirect_stdout(io.StringIO()):
    import context as cx          # context items, turns, look-alike days (step 5)

px, C, n = cx.px, cx.C, cx.n
t = px.time
T, LA, FT, FL = cx.T, cx.LA, cx.FT, cx.FL
M = pd.read_csv(HERE / "moves.csv")
M = M[M.basis == "close"]
DIV = ("Slow: RSI divergence (lower low in price, higher low in RSI)", "Slow: RSI divergence (higher high in price, lower high in RSI)")
DOLLAR_GOLD = {"US dollar (DXY) up over 30 days", "US dollar (DXY) above its 200-day EMA", "Gold up over 30 days"}
W, SIZES = 5, (10, 20, 30, 50)

# ---------------- context selection ----------------
def period(idx, a, b):
    tt = t.values[idx]
    return (tt >= np.datetime64(a)) & (tt < np.datetime64(b))


def lift(F, Fm, L, Lm, c):
    a = F.loc[Fm, c].dropna(); b = L.loc[Lm, c].dropna()
    if len(a) == 0 or len(b) == 0 or b.astype(float).mean() == 0:
        return np.nan, len(a), 0, 0
    ra, rb = a.astype(float).mean(), b.astype(float).mean()
    return ra / rb, len(a), ra * len(a), rb * len(a)


def select(p1, p2, whole):
    """Keep rule of step 5 on two sub-periods. Returns {side: {item: (sign, lift over `whole`)}}."""
    out = {}
    for sv in (1, -1):
        chosen = {}
        for c in FT.columns:
            votes = []
            for lvl in (10, 20):
                tm = (T.level == lvl) & (T.s == sv); lm = LA.s == sv
                ls = []
                ok = True
                for a, b in (p1, p2):
                    l, nt, present, expected = lift(FT, tm & period(T.i.values.astype(int), a, b), FL, lm & period(LA.i.values.astype(int), a, b), c)
                    if np.isnan(l) or nt < 8:
                        ok = False; break
                    ls.append((l, present, expected))
                if not ok:
                    continue
                if all(l >= 1.2 and pr >= 5 for l, pr, ex in ls):
                    votes.append(+1)
                elif all(l <= 0.83 and ex >= 5 for l, pr, ex in ls):
                    votes.append(-1)
            if votes and len(set(votes)) == 1:
                tm = (T.level.isin([10, 20])) & (T.s == sv); lm = LA.s == sv
                lw, *_ = lift(FT, tm & period(T.i.values.astype(int), *whole), FL, lm & period(LA.i.values.astype(int), *whole), c)
                chosen[c] = (votes[0], float(lw))
        out[sv] = chosen
    return out


SEL = {"strict": select(("2011-01-01", "2015-07-01"), ("2015-07-01", "2019-01-01"), ("2011-01-01", "2019-01-01")),
       "full": select(("2011-01-01", "2019-01-01"), ("2019-01-01", "2030-01-01"), ("2011-01-01", "2030-01-01"))}

# ---------------- base alert items for every day ----------------
lo10 = pd.Series(C).rolling(10).min().values
hi10 = pd.Series(C).rolling(10).max().values
base, ctx = {}, {}
for sv in (1, -1):
    b = cx.B[cx.B.s == sv].set_index("i")
    cnt = (b.prior7.le(-10).astype(int) + b.prior30.le(-20).astype(int) + b.vol_bs.ge(1.5).astype(int) + b.zW2_any.astype(int)).reindex(range(n)).fillna(0)
    ext = np.zeros(n, bool)
    ext[30:] = (C[30:] <= lo10[30:]) if sv > 0 else (C[30:] >= hi10[30:])
    base[sv] = dict(count=cnt.values, extreme=ext)
    rows = {}
    for i in np.flatnonzero(ext & (cnt.values >= 2)):
        r = cx.items(int(i), sv)
        for k in DIV:
            if k in r:
                r["Slow: RSI divergence"] = r.pop(k)
        rows[int(i)] = r
    ctx[sv] = rows


def score(sv, i, sel, weighted, dollar_gold):
    s, parts = 0.0, []
    for c, (sign, lw) in sel[sv].items():
        if not dollar_gold and c in DOLLAR_GOLD:
            continue
        v = ctx[sv][i].get(c)
        if v is True or v == 1.0:
            w = (np.log(lw) / np.log(1.5)) if weighted and lw and lw > 0 else float(sign)
            if weighted:
                w = float(np.clip(w, -2, 2))
            s += w; parts.append((c, round(w, 2)))
    return s, parts


def grade(sc):
    return "A" if sc >= 2 else ("B" if sc >= 0 else "C")


# ---------------- scoring (same episode logic as step 4) ----------------
def turn_confirm(level):
    m = M[M.level == level]
    return {int(r.end): (None if pd.isna(r.confirmed) else int(r.confirmed)) for r in m.itertuples()}


def episodes(sv, keep):
    """keep(i) -> True if alert day i belongs to this group."""
    ext = base[sv]["extreme"]
    eps, cur, last = [], None, -999
    for i in range(30, n):
        if ext[i]:
            if cur is not None and i - last > 10:
                eps.append(cur); cur = None
            last = i
            if base[sv]["count"][i] >= 2 and keep(i):
                if cur is None:
                    cur = dict(first=i, alerts=[i])
                else:
                    cur["alerts"].append(i)
        elif cur is not None and i - last > 10:
            eps.append(cur); cur = None
    if cur is not None:
        eps.append(cur)
    return eps


def evaluate(sv, level, keep, start):
    turns = T[(T.level == level) & (T.s == sv)].i.astype(int).tolist()
    conf = turn_confirm(level)
    last_conf = max(v for v in conf.values() if v is not None)
    eps = [e for e in episodes(sv, keep) if e["first"] <= last_conf and t[e["first"]] >= start]
    hits, adv = 0, []
    caught = set()
    for e in eps:
        h = [tt for tt in turns if any(a <= tt <= a + W for a in e["alerts"])]
        caught.update(h); hits += bool(h)
        end = h[0] if h else min(n - 1, e["first"] + 30)
        seg = C[e["first"]:end + 1]
        adv.append(((seg.min() / C[e["first"]] - 1) * 100) if sv > 0 else ((seg.max() / C[e["first"]] - 1) * -100))
    tt = [x for x in turns if x <= last_conf and t[x] >= start]
    return dict(alerts=len(eps), hits=hits, hit_rate=round(100 * hits / len(eps), 1) if eps else None,
                turns=len(tt), caught=len([x for x in tt if x in caught]),
                catch_rate=round(100 * len([x for x in tt if x in caught]) / len(tt), 1) if tt else None,
                adverse=round(float(np.median(adv)), 1) if adv else None)


START = {"2019-26": pd.Timestamp("2019-01-01"), "2011-18": pd.Timestamp("2011-01-01")}
END_1118 = pd.Timestamp("2019-01-01")
results, verdicts = [], {}
for test in ("strict", "full"):
    for weighted in (False, True):
        for dg in (True, False):
            for sv in (1, -1):
                side = "bottom" if sv > 0 else "top"
                for lvl in SIZES:
                    for half in (("2019-26",) if test == "strict" else ("2011-18", "2019-26")):
                        start = START[half]
                        inhalf = (lambda i: t[i] >= START["2019-26"]) if half == "2019-26" else (lambda i: t[i] < END_1118)
                        row = dict(test=test, weights="weighted" if weighted else "equal", dollar_gold="in" if dg else "out",
                                   side=side, size=lvl, half=half)
                        row["plain"] = evaluate(sv, lvl, lambda i: inhalf(i), start)
                        for g in "ABC":
                            row[g] = evaluate(sv, lvl, lambda i, g=g: inhalf(i) and grade(score(sv, i, SEL[test], weighted, dg)[0]) == g, start)
                        a, b, c, p = (row[k]["hit_rate"] for k in ("A", "B", "C", "plain"))
                        if row["A"]["alerts"] < 10:
                            v = "not enough data"
                        elif None in (a, b, c):
                            v = "fail"
                        else:
                            v = "PASS" if (a > b > c and a >= p + 5) else "fail"
                        row["verdict"] = v
                        results.append(row)

# weighted vs equal (strict, per side/size/dollar-gold)
cmp = []
for r in results:
    if r["test"] != "strict" or r["weights"] != "weighted":
        continue
    e = next(x for x in results if x["test"] == "strict" and x["weights"] == "equal" and x["dollar_gold"] == r["dollar_gold"]
             and x["side"] == r["side"] and x["size"] == r["size"])
    wa, ea = r["A"]["hit_rate"], e["A"]["hit_rate"]
    cmp.append(dict(side=r["side"], size=r["size"], dollar_gold=r["dollar_gold"], equal_A=ea, weighted_A=wa,
                    equal_A_n=e["A"]["alerts"], weighted_A_n=r["A"]["alerts"],
                    keep_weighted=bool(wa is not None and ea is not None and r["A"]["alerts"] >= 10 and wa >= ea + 5)))

json.dump(dict(selection={k: {("bottom" if s > 0 else "top"): v for s, v in d.items()} for k, d in SEL.items()},
               results=results, weighted_vs_equal=cmp), open(HERE / "grade_test.json", "w"), indent=1, default=str)

# example breakdowns for the user's turns (strict selection, equal weights, dollar/gold in)
EX = [("2020-03-12", 1), ("2026-06-30", 1), ("2021-11-08", -1), ("2022-11-21", 1), ("2023-09-11", 1), ("2026-03-29", 1), ("2024-12-17", -1)]
lines = []
for d, sv in EX:
    i = int(np.flatnonzero(t.dt.strftime("%Y-%m-%d").values == d)[0])
    near = [a for a in ctx[sv] if a <= i <= a + W]
    if not near:
        lines.append(f"{d}: no 2+ alert within 5 days before the turn"); continue
    a = near[-1]
    sc, parts = score(sv, a, SEL["strict"], False, True)
    lines.append(f"{d}: alert {t[a].date()}, grade {grade(sc)} ({sc:+.0f}): " + ("; ".join(f"{c} {w:+.0f}" for c, w in parts) or "no context items"))
(HERE / "grade_examples.txt").write_text("\n".join(lines))

# print summary
print("STRICT selection (2011-18 only):")
for s, d in SEL["strict"].items():
    print(" ", "bottoms" if s > 0 else "tops", {k: (v[0], round(v[1], 2)) for k, v in d.items()})
print("FULL selection:")
for s, d in SEL["full"].items():
    print(" ", "bottoms" if s > 0 else "tops", {k: v[0] for k, v in d.items()})
for r in results:
    if r["test"] == "strict":
        f = lambda k: f"{r[k]['hit_rate']}%/{r[k]['alerts']}"
        print(f"{r['weights']:8} dg={r['dollar_gold']:3} {r['side']:6} {r['size']:2}%  plain {f('plain')}  A {f('A')}  B {f('B')}  C {f('C')}  -> {r['verdict']}")
print("\n".join(lines))
