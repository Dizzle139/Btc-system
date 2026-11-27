"""
Step 8: which ENTRY gives the best chance of success? (user: "you decide what's best after testing")

Definitions fixed before running (bottoms / long; tops / short are the mirror image). Daily closes, Bitstamp.
  TURN      the turn-watch alert: new 10-day closing extreme + 2 of 4 items (first day of each episode)
  CHOCH     daily change of character in the new direction (close beyond the last confirmed swing, 2 bars each side)
  BREAK     close beyond the highest (lowest) close of the previous 20 days
  HL        higher low (lower high): a confirmed swing low that is above the previous swing low, where that previous
            low was the lowest close of the prior 60 days; entry when the new low is confirmed (2 days after it)
  Combos    CHOCH / BREAK / HL that come within 20 days AFTER a TURN alert on the same side
Signals of one method on one side are taken at most once per 10 days (the first one).
Outcome from the entry close, daily closes, up to 120 days:
  win_10_5   price closes 10% in favour before it closes 5% against
  win_20_10  price closes 20% in favour before it closes 10% against
Baseline: every day as an entry, same side (what you would get by entering at random).
Verdict: a method is better than random only if it beats the baseline in BOTH 2011-18 and 2019-26.
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(ROOT / "bot"))
from btcdata import load  # noqa: E402
import turnlib  # noqa: E402
from structure import trend_state, swings  # noqa: E402

d = load(utc=True)
C = d.close.values
n = len(C)
dates = d.time.dt.strftime("%Y-%m-%d").values
X = turnlib.compute(d)
_, _, dev = trend_state(d, 2)
GAP, COMBO, HORIZON = 10, 20, 120


def outcome(i, s, up, down):
    """s=+1 long, -1 short. First of: +up% in favour (win) or -down% against (loss), on closes, within HORIZON."""
    e = C[i]
    for j in range(i + 1, min(n, i + 1 + HORIZON)):
        r = (C[j] / e - 1) * s
        if r >= up / 100:
            return 1, j - i
        if r <= -down / 100:
            return 0, j - i
    return None, None          # neither within the horizon (or not enough data yet)


def thin(idx):
    out, last = [], -10**9
    for i in sorted(idx):
        if i - last >= GAP:
            out.append(i); last = i
    return out


def turn_signals(s):
    col = "alert_b" if s > 0 else "alert_t"
    ext = (X.new_low10 if s > 0 else X.new_high10).values
    a = X[col].values
    first, cur_last = [], -999
    in_ep, last_ext = False, -999
    for i in range(30, n):
        if ext[i]:
            if in_ep and i - last_ext > 10:
                in_ep = False
            last_ext = i
            if a[i] and not in_ep:
                first.append(i); in_ep = True
        elif in_ep and i - last_ext > 10:
            in_ep = False
    return first


def choch_signals(s):
    return thin([e["idx"] for e in dev if e["kind"] == "CHoCH" and e["dir"] == ("up" if s > 0 else "down") and e["idx"] >= 30])


def break_signals(s):
    hi20 = pd.Series(C).shift(1).rolling(20).max().values
    lo20 = pd.Series(C).shift(1).rolling(20).min().values
    return thin([i for i in range(30, n) if (C[i] > hi20[i] if s > 0 else C[i] < lo20[i])])


def hl_signals(s):
    """Swing lows (s=+1) or highs (s=-1) on closes, 2 bars each side, confirmed 2 bars later."""
    k = 2
    piv = []
    for p in range(k, n - k):
        w = C[p - k:p + k + 1]
        if (s > 0 and C[p] == w.min()) or (s < 0 and C[p] == w.max()):
            piv.append(p)
    lo60 = pd.Series(C).rolling(60).min().values
    hi60 = pd.Series(C).rolling(60).max().values
    out = []
    for a, b in zip(piv[:-1], piv[1:]):
        if b - a > 40 or b + k >= n:
            continue
        real = (C[a] <= lo60[a]) if s > 0 else (C[a] >= hi60[a])
        better = (C[b] > C[a]) if s > 0 else (C[b] < C[a])
        if real and better:
            out.append(b + k)       # known when the new swing is confirmed
    return thin(out)


def after_turn(sig, turns):
    return [i for i in sig if any(0 < i - t <= COMBO for t in turns)]


HALF = lambda i: "2011-18" if dates[i] < "2019-01-01" else "2019-26"
rows, sigs = [], {}
for s, side in ((1, "long (bottoms)"), (-1, "short (tops)")):
    T = turn_signals(s)
    methods = {"TURN alert": T, "CHOCH": choch_signals(s), "BREAK 20-day": break_signals(s), "HIGHER LOW" if s > 0 else "LOWER HIGH": hl_signals(s)}
    for k in list(methods):
        if k != "TURN alert":
            methods[f"{k} after a TURN alert"] = after_turn(methods[k], T)
    methods["random day (baseline)"] = list(range(30, n))
    sigs[s] = methods
    for name, idx in methods.items():
        for half in ("2011-18", "2019-26", "all"):
            ii = [i for i in idx if half == "all" or HALF(i) == half]
            res = {}
            for up, dn in ((10, 5), (20, 10)):
                o = [outcome(i, s, up, dn) for i in ii]
                done = [x for x, _ in o if x is not None]
                res[f"{up}/{dn}"] = (round(100 * np.mean(done), 1) if done else None, len(done),
                                     float(np.median([dd for x, dd in o if x == 1])) if any(x == 1 for x, _ in o) else None)
            rows.append(dict(side=side, method=name, half=half, signals=len(ii),
                             win_10_5=res["10/5"][0], n_10_5=res["10/5"][1], days_win_10_5=res["10/5"][2],
                             win_20_10=res["20/10"][0], n_20_10=res["20/10"][1], days_win_20_10=res["20/10"][2]))
R = pd.DataFrame(rows)
R.to_csv(HERE / "entry_test.csv", index=False)

# verdicts
lines = ["# Step 8: entry methods", "", __doc__.strip(), ""]
for side in R.side.unique():
    g = R[R.side == side]
    base = g[g.method == "random day (baseline)"].set_index("half")
    lines += [f"## {side}", "", "| Method | Signals | Win 10/5 2011-18 | Win 10/5 2019-26 | Win 20/10 2011-18 | Win 20/10 2019-26 | Beats random in both halves |",
              "|---|---|---|---|---|---|---|"]
    for m in g.method.unique():
        x = g[g.method == m].set_index("half")
        ok = []
        for col in ("win_10_5", "win_20_10"):
            a, b = x.loc["2011-18", col], x.loc["2019-26", col]
            ok.append(a is not None and b is not None and not np.isnan(a) and not np.isnan(b)
                      and a > base.loc["2011-18", col] and b > base.loc["2019-26", col]
                      and x.loc["2011-18", "n_10_5"] >= 10 and x.loc["2019-26", "n_10_5"] >= 10)
        f = lambda h, c: f"{x.loc[h, c]}% ({int(x.loc[h, 'n_' + c[4:]])})"
        lines.append(f"| {m} | {int(x.loc['all', 'signals'])} | {f('2011-18', 'win_10_5')} | {f('2019-26', 'win_10_5')} | "
                     f"{f('2011-18', 'win_20_10')} | {f('2019-26', 'win_20_10')} | {'10/5: ' + ('yes' if ok[0] else 'no') + ', 20/10: ' + ('yes' if ok[1] else 'no') if m != 'random day (baseline)' else '–'} |")
    lines.append("")

# the user's 9 marks: which methods gave an entry inside the move, and at what price
marks = [("2026-01-14", "2026-02-05", -1, "Jan 2026 top"), ("2024-09-08", "2024-11-24", 1, "Sep 2024 low"),
         ("2025-10-06", "2025-11-20", -1, "Oct 2025 top"), ("2025-04-08", "2025-05-22", 1, "Apr 2025 low (trade 1)"),
         ("2025-04-08", "2025-07-11", 1, "Apr 2025 low (trade 2)"), ("2026-06-30", "2026-08-21", 1, "Jun 2026 low"),
         ("2026-10-05", "2026-11-15", -1, "Oct 2026 lower high"), ("2023-09-13", "2024-03-13", 1, "Sep 2023 low"),
         ("2020-03-22", "2021-01-08", 1, "Mar 2020 low")]
pos = {x: k for k, x in enumerate(dates)}
lines += ["## Your marked moves: first entry each method gave (from 10 days before your start to your end)", "",
          "| Move | " + " | ".join(m for m in sigs[1] if m != "random day (baseline)") + " |", "|---" * (len(sigs[1])) + "|"]
for a, b, s, name in marks:
    i0, i1 = pos[a] - 10, pos[b]
    total = (C[pos[b]] / C[pos[a]] - 1) * s
    cells = []
    for m, idx in sigs[s].items():
        if m == "random day (baseline)":
            continue
        hit = [i for i in idx if i0 <= i <= i1]
        if hit:
            i = hit[0]
            got = (C[pos[b]] / C[i] - 1) * s
            cells.append(f"{dates[i]} ({got / total * 100:.0f}% of your move left)" if total else dates[i])
        else:
            cells.append("none")
    lines.append(f"| {name} | " + " | ".join(cells) + " |")
(HERE / "entry_results.md").write_text("\n".join(lines) + "\n")
print("\n".join(lines))
