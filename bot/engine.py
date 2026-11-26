"""
BTC alert engine v4 — runs once per DAILY close. Built only on rules that survived the
full-history tests (2011-2026, see research/results.md). Long-only: shorts showed no edge.

ALERTS
  REGIME   weekly close changes weekly structure (BOS/CHoCH) or the weekly EMA50/200 cross
  WATCH    price comes within 1 weekly ATR of an untested weekly zone that agrees with the regime
  ZONE     first touch of a weekly FVG/OB zone, graded by conviction (EMA + structure)
  TRIGGER  daily close above the last confirmed daily swing high (daily CHoCH up),
           graded A (weekly EMA + structure bullish) / B (EMA only); stop, 3R, room to next zone
Every alert states the tested record of its grade.
"""
import numpy as np
import pandas as pd
from zones import find_fvgs, find_obs, dedupe, atr
from structure import trend_state

D1, W1 = pd.Timedelta(days=1), pd.Timedelta(days=7)
FAR = pd.Timestamp("2100-01-01", tz="UTC")

RECORD = {
    "ZONE_2": "Weekly zone with weekly EMA AND structure agreeing: held 70% in tests (random ~45-50%), "
              "stable 2012-18 and 2019-26.",
    "ZONE_1": "Weekly zone with only one of EMA/structure agreeing: held ~45-57% in tests. Medium conviction.",
    "ZONE_0": "Weekly zone against both EMA and structure: held ~25-40% in tests. Low conviction.",
    "TRIG_A": "Grade A (daily CHoCH + weekly EMA + structure bullish): +0.90R per trade at 3R in tests "
              "(win ~37%, 51 trades 2012-26); beat random entries in the same regime in 2 of 3 eras.",
    "TRIG_B": "Grade B (daily CHoCH + weekly EMA bullish, structure NOT bullish): +0.38R per trade at 3R in tests "
              "(win 29%, 51 trades 2012-26; 2021-26 only +0.14R). Low conviction.",
}


def ema(x, n):
    return x.ewm(span=n, adjust=False).mean()


def to_weekly(d):
    return (d.set_index("time").resample("W-MON", label="left", closed="left")
            .agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
            .dropna().reset_index())


def life(d, zs, bar, tf):
    out, n = [], len(d)
    for z in zs:
        inv = FAR
        for t in range(z["known_idx"] + 1, n):
            if (z["side"] == "bull" and d.close[t] < z["bottom"]) or (z["side"] == "bear" and d.close[t] > z["top"]):
                inv = d.time[t] + bar
                break
        out.append({**z, "tf": tf, "known_time": d.time[z["known_idx"]] + bar, "invalid_time": inv,
                    "formed": d.time[z["form_idx"]]})
    return out


class Engine:
    def __init__(self, daily, cfg, now=None):
        now = now or pd.Timestamp.now(tz="UTC")
        self.cfg = cfg
        D = daily[daily.time + D1 <= now].reset_index(drop=True)
        W = to_weekly(D)
        W = W[W.time + W1 <= now].reset_index(drop=True)
        W["e50"], W["e200"], W["atr"] = ema(W.close, 50), ema(W.close, 200), atr(W)
        D["atr"] = atr(D)
        self.D, self.W = D, W
        self.wstate, _, self.wevents = trend_state(W, cfg["pivot_weeks"])
        self.dstate, _, self.devents = trend_state(D, cfg["pivot_days"])
        self.wct = (W.time + W1).values
        self.zones = life(W, dedupe(find_fvgs(W, cfg["X"]) + find_obs(W, cfg["X"])), W1, "W")
        self.choch_up = {e["idx"]: e for e in self.devents if e["kind"] == "CHoCH" and e["dir"] == "up"}

    # ---- weekly context known at time t (only closed weekly candles) ----
    def wk(self, t):
        k = np.searchsorted(self.wct, np.datetime64(t.tz_convert(None)), side="right") - 1
        if k < 0:
            return None
        W = self.W
        return dict(k=k, struct=self.wstate[k], ema="bull" if W.e50[k] > W.e200[k] else "bear",
                    e50=W.e50[k], e200=W.e200[k], atr=W.atr[k])

    def active(self, t):
        return [z for z in self.zones if z["known_time"] <= t < z["invalid_time"]]

    def conviction(self, side, ctx):
        return int(ctx["ema"] == side) + int(ctx["struct"] == side)

    def _touched_before(self, z, i):
        D = self.D
        m = (D.time >= z["known_time"]) & (D.index < i)
        return bool((D.low[m] <= z["top"]).any()) if z["side"] == "bull" else bool((D.high[m] >= z["bottom"]).any())

    def _watched_before(self, z, i, band):
        D = self.D
        m = (D.time >= z["known_time"]) & (D.index < i)
        return bool((D.low[m] <= z["top"] + band).any()) if z["side"] == "bull" else bool((D.high[m] >= z["bottom"] - band).any())

    def alerts_for_day(self, i):
        D, cfg = self.D, self.cfg
        t = D.time[i] + D1                      # this daily candle's close
        ctx = self.wk(t)
        if ctx is None:
            return []
        out = []
        # REGIME: a weekly candle closed at this daily close
        prev = self.wk(t - D1)
        if prev is not None and prev["k"] != ctx["k"]:
            for e in self.wevents:
                if e["idx"] == ctx["k"]:
                    out.append(dict(kind="REGIME", t=t, text=(
                        f"Weekly {e['kind']} {'UP' if e['dir'] == 'up' else 'DOWN'} at {e['level']:,.0f}: weekly structure now "
                        f"{'BULLISH' if e['dir'] == 'up' else 'BEARISH'}. Weekly EMA50 {ctx['e50']:,.0f} vs EMA200 {ctx['e200']:,.0f} "
                        f"({ctx['ema'].upper()}).")))
            if prev["ema"] != ctx["ema"]:
                out.append(dict(kind="REGIME", t=t, text=(
                    f"Weekly EMA50 crossed {'ABOVE' if ctx['ema'] == 'bull' else 'BELOW'} EMA200 "
                    f"({ctx['e50']:,.0f} vs {ctx['e200']:,.0f}). This is the strongest regime factor in tests.")))
        # WATCH + ZONE (bull zones; bear zones only if enabled)
        for z in self.active(D.time[i]):
            if z["side"] == "bear" and not cfg["bear_zone_alerts"]:
                continue
            bull = z["side"] == "bull"
            conv = self.conviction(z["side"], ctx)
            band = cfg["watch_atr"] * ctx["atr"]
            touch = D.low[i] <= z["top"] if bull else D.high[i] >= z["bottom"]
            near = D.low[i] <= z["top"] + band if bull else D.high[i] >= z["bottom"] - band
            desc = (f"weekly {'BULLISH (support)' if bull else 'BEARISH (resistance)'} {z['kind']} zone "
                    f"{z['bottom']:,.0f}-{z['top']:,.0f} (formed week of {z['formed']:%b %d, %Y})")
            regime = f"Weekly structure {ctx['struct'].upper() or 'unset'}, weekly EMA {ctx['ema'].upper()}."
            if touch and not self._touched_before(z, i):
                out.append(dict(kind="ZONE", t=t, conv=conv, text=(
                    f"FIRST TEST of {desc}. Daily close {D.close[i]:,.0f}. {regime} Conviction {conv}/2. "
                    + RECORD[f"ZONE_{conv}"] + " The zone is a map: wait for a daily TRIGGER to time an entry.")))
            elif near and not touch and conv >= cfg["watch_min_conv"] and not self._watched_before(z, i, band):
                out.append(dict(kind="WATCH", t=t, conv=conv, text=(
                    f"Price {D.close[i]:,.0f} is within {cfg['watch_atr']:.0f} weekly ATR of the untested {desc}. "
                    f"{regime} Conviction {conv}/2. Opportunity forming, no action yet.")))
        # TRIGGER: daily CHoCH up on this candle
        if i in self.choch_up and ctx["ema"] == "bull":
            e = self.choch_up[i]
            lo = D.low[max(0, i - cfg["stop_lookback_days"]):i + 1].min()
            entry = D.close[i]
            stop = lo - 0.25 * D.atr[i]
            risk = entry - stop
            if risk > 0:
                grade = "A" if ctx["struct"] == "bull" else "B"
                above = [z for z in self.active(D.time[i]) if z["side"] == "bear" and z["bottom"] > entry]
                room = min(z["bottom"] for z in above) if above else None
                room_txt = (f"Next opposing weekly zone at {room:,.0f} = {(room - entry) / risk:.1f}R away"
                            + (" (LESS than 3R: room gate says skip)" if (room - entry) / risk < 3 else "") + "."
                            if room else "No opposing weekly zone above.")
                inside = [z for z in self.active(D.time[i]) if z["side"] == "bull" and z["bottom"] <= lo <= z["top"]]
                out.append(dict(kind="TRIGGER", t=t, grade=grade, text=(
                    f"GRADE {grade} long trigger: daily close {entry:,.0f} above the last daily swing high {e['level']:,.0f} "
                    f"(daily CHoCH up). Stop {stop:,.0f} ({100 * risk / entry:.1f}%, below the {cfg['stop_lookback_days']}-day low) | "
                    f"1R {entry + risk:,.0f} | 3R {entry + 3 * risk:,.0f}. {room_txt} "
                    + (f"Swing low sits inside weekly zone {inside[0]['bottom']:,.0f}-{inside[0]['top']:,.0f}. " if inside else "")
                    + RECORD[f"TRIG_{grade}"])))
        return out

    def status(self):
        D, i = self.D, len(self.D) - 1
        t = D.time[i] + D1
        ctx = self.wk(t)
        px = D.close[i]
        act = [z for z in self.active(D.time[i])]
        below = sorted([z for z in act if z["top"] < px], key=lambda z: -z["top"])[:2]
        above = sorted([z for z in act if z["bottom"] > px], key=lambda z: z["bottom"])[:2]
        f = lambda z: f"{z['side']} {z['kind']} {z['bottom']:,.0f}-{z['top']:,.0f}"
        last_sh = self.devents[-1] if self.devents else None
        return "\n".join([
            f"BTC daily close {px:,.0f} (candle of {D.time[i]:%b %d, %Y})",
            f"Regime: weekly structure {ctx['struct'].upper()}, weekly EMA50 {ctx['e50']:,.0f} vs EMA200 {ctx['e200']:,.0f} "
            f"({ctx['ema'].upper()}) -> long conviction {self.conviction('bull', ctx)}/2",
            f"Daily structure: {self.dstate[i].upper()}" + (f" (last {last_sh['kind']} {last_sh['dir']} at {last_sh['level']:,.0f})" if last_sh else ""),
            "Weekly zones above: " + ("; ".join(map(f, above)) or "none"),
            "Weekly zones below: " + ("; ".join(map(f, below)) or "none"),
        ])
