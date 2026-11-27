"""
Turn watch: alerts for possible 10%+ turns (tops and bottoms), a daily log, and a journal that records what happened next.

Every alert spells out each piece behind it: the setup items with their values, the warnings that held up in testing,
the market context, and how past alerts with the same pieces turned out. Research, not financial advice.

Files (committed by the Daily alerts workflow):
  journal/daily_log.csv   one row per daily close: price, setup items, context
  journal/alerts.csv      one row per alert day, with outcomes filled in over the next 30 days
  journal/JOURNAL.md      readable journal, newest first
"""
from pathlib import Path
import numpy as np
import pandas as pd

import turnlib
import history

ROOT = Path(__file__).resolve().parent.parent
JDIR = ROOT / "journal"
SIDE_NAME = {"b": "BOTTOM", "t": "TOP"}
WARN_TEXT = {  # tested numbers: research/moves/grade_test.py (chosen on 2011-18, checked on 2019-26, 10% moves)
    ("b", "volume_drying"): "Volume drying up (20-day avg {vol20_vs_90:.2f}x the 90-day). Since 2019, bottom alerts with this: 30% became a 10% turn vs 78% without (10 alerts).",
    ("b", "dollar_up"): "US dollar up {dxy_30d_pct:+.1f}% in 30 days. Since 2019, bottom alerts with this: 59% vs 82% without.",
    ("b", "range_squeezed"): "Daily range squeezed ({range_pct:.1f}%, bottom 20% of the last 180 days). At new lows this is rarely the real turn (only 2 alerts since 2019).",
    ("t", "range_squeezed"): "Daily range squeezed ({range_pct:.1f}%, bottom 20% of the last 180 days). Since 2019, top alerts with this: 50% vs 66% without.",
    ("t", "volume_drying"): "Volume drying up (20-day avg {vol20_vs_90:.2f}x the 90-day). Since 2019, top alerts with this: 38% vs 63% without (8 alerts).",
}
OUTCOME_DAYS = (1, 3, 7, 14, 30)
NICE = {"sharp_b": "sharp drop", "sharp_t": "sharp rise", "ext_b": "extended drop", "ext_t": "extended rise", "volume": "volume spike",
        "zone_b": "weekly zone", "zone_t": "weekly zone", "volume_drying": "volume drying up", "dollar_up": "dollar up",
        "range_squeezed": "range squeezed", "none": "none"}


# ---------------- market data ----------------
def market_live():
    """Yahoo Finance daily closes (fetched live); falls back to the copies the data agent saved. Returns series + as-of dates."""
    import sys
    sys.path.insert(0, str(ROOT / "data_agent"))
    files = {"dxy": "yahoo_DX_Y_NYB", "vix": "yahoo_VIX", "gold": "yahoo_GC_F", "spx": "yahoo_GSPC", "us10y": "yahoo_TNX"}
    syms = {"dxy": "DX-Y.NYB", "vix": "^VIX", "gold": "GC=F", "spx": "^GSPC", "us10y": "^TNX"}
    mac, asof = {}, {}
    try:
        import fetch_all
    except Exception:
        fetch_all = None
    for k, f in files.items():
        s = None
        if fetch_all is not None:
            try:
                x = fetch_all.yahoo(syms[k])
                s = pd.Series(x.close.values, index=pd.to_datetime(x.time))
            except Exception:
                s = None
        if s is None and (ROOT / "data" / f"{f}.csv").exists():
            x = pd.read_csv(ROOT / "data" / f"{f}.csv")
            s = pd.Series(x.close.values, index=pd.to_datetime(x.time))
        if s is not None:
            mac[k], asof[k] = s, str(pd.to_datetime(s.index[-1]).date())
    uf = ROOT / "data" / "usdtd_1D.csv"
    if uf.exists():
        x = pd.read_csv(uf)
        t = pd.to_datetime(x.time, unit="s") if pd.api.types.is_numeric_dtype(x.time) else pd.to_datetime(x.time)
        mac["usdt_d"], asof["usdt_d"] = pd.Series(x.close.values, index=t), str(t.iloc[-1].date())
    return mac, asof


def market_files(until=None):
    files = {"dxy": "yahoo_DX_Y_NYB", "vix": "yahoo_VIX", "gold": "yahoo_GC_F", "spx": "yahoo_GSPC", "us10y": "yahoo_TNX"}
    mac, asof = {}, {}
    for k, f in files.items():
        p = ROOT / "data" / f"{f}.csv"
        if p.exists():
            x = pd.read_csv(p)
            s = pd.Series(x.close.values, index=pd.to_datetime(x.time))
            if until is not None:
                s = s[s.index <= pd.Timestamp(until)]
            mac[k], asof[k] = s, str(pd.to_datetime(s.index[-1]).date())
    return mac, asof


# ---------------- message ----------------
def fmt_price(x):
    return f"{x:,.0f}"


def message(X, i, side, kind, ep_first, sim, asof):
    r = X.iloc[i]
    nm = SIDE_NAME[side]
    lines = [f"BTC TURN WATCH: possible {nm} ({'new alert' if kind == 'NEW' else 'update, same alert as ' + ep_first})",
             f"Daily close {r.date}: {fmt_price(r.close)}", "",
             f"Setup: new 10-day closing {'low' if side == 'b' else 'high'} + {int(r['items_' + side])} of 4 items (needs 2)"]
    for k in turnlib.BASE_KEYS[side]:
        txt = turnlib.ITEM_TEXT[side][k].format(**{c: r[c] for c in ("chg7", "chg30", "vol_x")})
        lines.append(f"  {'YES' if bool(r[k]) else 'no '}  {txt}")
    base, warn = turnlib.flags(r, side)
    lines += ["", "Warnings (held up when tested on 2019-26 after being chosen on 2011-18):"]
    if warn:
        for w in warn:
            lines.append("  ! " + WARN_TEXT[(side, w)].format(**{c: r[c] for c in ("vol20_vs_90", "dxy_30d_pct", "range_pct")}))
    else:
        lines.append("  none")
    ctx = [f"{r.phase or 'unknown'} ({int(r.days_since_halving)} days)" if not np.isnan(r.days_since_halving) else "halving cycle unknown",
           f"{r.below_ath_pct:.0f}% below the all-time high"]
    if not np.isnan(r.vix):
        ctx.append(f"VIX {r.vix:.1f}")
    if not np.isnan(r.dxy_30d_pct):
        ctx.append(f"dollar {r.dxy_30d_pct:+.1f}% / 30d")
    if not np.isnan(r.gold_30d_pct):
        ctx.append(f"gold {r.gold_30d_pct:+.1f}% / 30d")
    if not np.isnan(r.spx_above_200ema):
        ctx.append(f"S&P 500 {'above' if r.spx_above_200ema else 'below'} its 200-day EMA")
    mk = asof.get("spx_by_day", {}).get(r.date) or asof.get("spx", "n/a")
    lines += ["", "Context: " + "; ".join(ctx) + f" (US markets: last close {mk})"]
    lines += ["", "How past alerts with the same pieces turned out (only alerts whose outcome was known by now):",
              "  10% turn within 5 days | 20% turn | median move further first | median 14 days later"]
    for t in sim:
        if t["n"] < 5:
            lines.append(f"  - {t['tier']}: {t['n']} past alerts, too few to judge")
            continue
        recent = f"; since 2019: {t['hit10_2019']}% of {t['n_2019']}" if t.get("n_2019") else ""
        lines.append(f"  - {t['tier']}: {t['n']} alerts: {t['hit10']}% | {t['hit20']}% | {t['further']:+.1f}% | {t['ret14']:+.1f}%{recent}")
    lines += ["", "What it means: in testing, this setup flags a likely 10% bounce/pullback soon. It does not say a big turn "
              "is in: since 2019 only about a third of alerts led to a 20% move. Research, not financial advice."]
    return "\n".join(lines)


# ---------------- journal ----------------
LOG_COLS = ["date", "close", "chg7", "chg30", "vol_x", "new_low10", "new_high10", "items_b", "items_t", "zone_b", "zone_t",
            "alert_b", "alert_t", "phase", "days_since_halving", "below_ath_pct", "days_since_ath", "range_pct", "range_squeezed",
            "vol20_vs_90", "volume_drying", "vix", "dxy_30d_pct", "gold_30d_pct", "spx_above_200ema", "us10y_30d_chg", "usdt_d_30d_pct"]
ALERT_COLS = ["date", "side", "kind", "episode", "price", "items", "base", "warnings", "phase", "below_ath_pct", "vix",
              "dxy_30d_pct", "gold_30d_pct", "best_match", "best_match_n", "best_match_hit10", "source"] + \
             [f"close_d{k}" for k in OUTCOME_DAYS] + [f"chg_d{k}_pct" for k in OUTCOME_DAYS] + \
             ["extreme_since", "extreme_since_date", "turn10_date", "turn20_date", "status"]


def load_csv(p, cols):
    return pd.read_csv(p, dtype=str) if p.exists() else pd.DataFrame(columns=cols)


def episode_state(X, i, side):
    """New alert, or an update of an open one? Exactly the research rule (history.episodes) applied to data up to day i."""
    eps = history.episodes(X.iloc[:i + 1].reset_index(drop=True), side)
    e = next(e for e in reversed(eps) if i in e["alerts"])
    first = X.date.values[e["first"]]
    return ("NEW" if e["first"] == i else "UPDATE"), f"{side}:{first}"


def update_outcomes(A, X):
    pos = {d: k for k, d in enumerate(X.date.values)}
    C = X.close.values
    for k, r in A.iterrows():
        if r.get("status") == "closed" or r.date not in pos:
            continue
        i = pos[r.date]
        last = len(C) - 1
        for dd in OUTCOME_DAYS:
            if i + dd <= last:
                A.at[k, f"close_d{dd}"] = f"{C[i + dd]:.2f}"
                A.at[k, f"chg_d{dd}_pct"] = f"{(C[i + dd] / C[i] - 1) * 100:.1f}"
        seg_end = min(last, i + 30)
        seg = C[i:seg_end + 1]
        if r.side == "b":
            j = int(np.argmin(seg)); A.at[k, "extreme_since"] = f"{seg[j]:.2f}"
        else:
            j = int(np.argmax(seg)); A.at[k, "extreme_since"] = f"{seg[j]:.2f}"
        A.at[k, "extreme_since_date"] = X.date.values[i + j]
        for lvl in (10, 20):
            hit = None
            run_ext = C[i]
            for q in range(i, seg_end + 1):
                run_ext = min(run_ext, C[q]) if r.side == "b" else max(run_ext, C[q])
                if (r.side == "b" and C[q] >= run_ext * (1 + lvl / 100)) or (r.side == "t" and C[q] <= run_ext * (1 - lvl / 100)):
                    hit = X.date.values[q]; break
            A.at[k, f"turn{lvl}_date"] = hit or ""
        A.at[k, "status"] = "closed" if last - i >= 30 else "open"
    return A


def write_markdown(A, L):
    lines = ["# BTC turn-watch journal", "",
             "Every alert, what was behind it, and what happened next. Turn = close moved 10% (or 20%) off the most extreme "
             "close since the alert, within 30 days. Research, not financial advice.", ""]
    if len(L):
        last = L.iloc[-1]
        lines += [f"Last daily close logged: {last.date}, {float(last.close):,.0f}. Setup items today: bottom side {last.items_b} of 4"
                  f" (new 10-day low: {last.new_low10}), top side {last.items_t} of 4 (new 10-day high: {last.new_high10}).", ""]
    if not len(A):
        lines.append("No alerts yet.")
    else:
        lines += ["| Date | Side | Alert | Close | Items | Warnings | Phase | +7d | +14d | +30d | 10% turn | 20% turn | Source |",
                  "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for r in A.iloc[::-1].itertuples():
            g = lambda v: (v if isinstance(v, str) and v not in ("", "nan") else "–")
            pc = lambda v: (f"{float(v):+.1f}%" if isinstance(v, str) and v not in ("", "nan") else "–")
            nice = lambda x: ", ".join(NICE.get(k, k) for k in str(x).split("+"))
            lines.append(f"| {r.date} | {SIDE_NAME[r.side].title()} | {r.kind.title()} | {float(r.price):,.0f} | {nice(r.base)} | {nice(r.warnings)} | {r.phase} | "
                         f"{pc(r.chg_d7_pct)} | {pc(r.chg_d14_pct)} | {pc(r.chg_d30_pct)} | {g(r.turn10_date)} | {g(r.turn20_date)} | {r.source} |")
    (JDIR / "JOURNAL.md").write_text("\n".join(lines) + "\n")


def process(d, mac, asof, days, source, send=None, moves=None):
    """Run the turn watch for the given candle dates (normally just the last closed day). Updates the journal files."""
    JDIR.mkdir(exist_ok=True)
    X = turnlib.compute(d, mac)
    if "spx" in mac:
        sd = pd.DatetimeIndex(pd.to_datetime(mac["spx"].index)).tz_localize(None).normalize().sort_values()
        pos_ = np.searchsorted(sd.values, pd.to_datetime(X.date).values, side="right") - 1
        asof = dict(asof, spx_by_day={dt: (str(sd[p].date()) if p >= 0 else None) for dt, p in zip(X.date, pos_)})
    moves = moves if moves is not None else pd.read_csv(ROOT / "research/moves/moves.csv")
    H = history.build(X, moves)
    L = load_csv(JDIR / "daily_log.csv", LOG_COLS + ["source"])
    A = load_csv(JDIR / "alerts.csv", ALERT_COLS)
    msgs = []
    for day in days:
        hits = np.flatnonzero(X.date.values == day)
        if not len(hits):
            continue
        i = int(hits[0])
        r = X.iloc[i]
        if day not in set(L.date):
            row = {c: r[c] for c in LOG_COLS if c in r.index}
            row["source"] = source
            L = pd.concat([L, pd.DataFrame([row]).astype(str)], ignore_index=True)
        for side in ("b", "t"):
            if not bool(r[f"alert_{side}"]) or ((A.date == day) & (A.side == side)).any():
                continue
            kind, ep = episode_state(X, i, side)
            base, warn = turnlib.flags(r, side)
            sim = history.similar(H, side, base, warn, r.phase, day)
            best = next((t for t in sim if t["n"] >= 5), sim[-1])
            A = pd.concat([A, pd.DataFrame([dict(
                date=day, side=side, kind=kind, episode=ep, price=f"{r.close:.2f}", items=int(r[f"items_{side}"]),
                base="+".join(base), warnings="+".join(warn) or "none", phase=r.phase, below_ath_pct=f"{r.below_ath_pct:.1f}",
                vix=f"{r.vix:.1f}", dxy_30d_pct=f"{r.dxy_30d_pct:.1f}", gold_30d_pct=f"{r.gold_30d_pct:.1f}",
                best_match=best["tier"], best_match_n=best["n"], best_match_hit10=best.get("hit10"), source=source)]).astype(str)],
                ignore_index=True)
            msgs.append(message(X, i, side, kind, ep.split(":")[1], sim, asof))
    A = update_outcomes(A, X)
    L = L.sort_values("date").drop_duplicates("date", keep="first")
    A = A.sort_values(["date", "side"])
    L.to_csv(JDIR / "daily_log.csv", index=False)
    A.to_csv(JDIR / "alerts.csv", index=False)
    write_markdown(A, L)
    if send:
        for m in msgs:
            send(m)
    return msgs, X
