"""Chart data for the Move Marker page: 4H, daily and weekly candles with volume, EMA50/200, FVG/OB zones
(2x displacement filter, same rules as the research), swing points and BOS/CHoCH, bull/bear cycles and halvings.
Usage: python marker_data.py OUTDIR"""
import json, sys
from pathlib import Path
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(ROOT / "bot"))
from btcdata import load  # noqa: E402
import turnlib  # noqa: E402
from zones import find_fvgs, find_obs, dedupe  # noqa: E402
from structure import trend_state  # noqa: E402

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
NOW = pd.Timestamp.now(tz="UTC")
KIND = {"FVG": 0, "OB": 1, "FVG+OB": 2, "OB+FVG": 2}
EV = {"BOS": 0, "CHoCH": 1}


def r2(x):
    return float(round(float(x), 2))


def first_touch(f, k0, bull, bot, top):
    """First candle after the zone is known that trades into it (-1 = never)."""
    seg = (f.low.values[k0:] <= top) if bull else (f.high.values[k0:] >= bot)
    w = np.flatnonzero(seg)
    return int(k0 + w[0]) if len(w) else -1


def pack(f, bar, fmt):
    f = f[f.time + bar <= NOW].reset_index(drop=True)          # closed candles only
    C = f.close.values
    e50 = f.close.ewm(span=50, adjust=False).mean().values
    e200 = f.close.ewm(span=200, adjust=False).mean().values
    zs = dedupe(find_fvgs(f, 2.0) + find_obs(f, 2.0))
    z = []
    for q in zs:
        inv = -1
        for j in range(q["known_idx"] + 1, len(f)):
            if (q["side"] == "bull" and C[j] < q["bottom"]) or (q["side"] == "bear" and C[j] > q["top"]):
                inv = j; break
        z.append([1 if q["side"] == "bull" else 0, KIND.get(q["kind"], 0), int(q["form_idx"]), int(q["known_idx"]), inv, r2(q["bottom"]), r2(q["top"]),
                  first_touch(f, int(q["known_idx"]), q["side"] == "bull", q["bottom"], q["top"])])
    _, sw, ev = trend_state(f, 2)
    out = dict(
        c=[[t.strftime(fmt), r2(o), r2(h), r2(l), r2(c), round(float(v), 1)] for t, o, h, l, c, v in
           zip(f.time, f.open, f.high, f.low, f.close, f.volume)],
        e50=[r2(x) for x in e50], e200=[r2(x) for x in e200], z=z,
        ev=[[int(e["idx"]), EV[e["kind"]], 1 if e["dir"] == "up" else -1, r2(e["level"])] for e in ev],
        sw=[[int(s["idx"]), 1 if s["type"] == "H" else 0, r2(s["price"]), s["label"]] for s in sw])
    return f, zs, out


d = load(utc=True)
W = turnlib.weekly(d)
h4 = pd.read_csv(ROOT / "data/btc_4H.csv")
h4["time"] = pd.to_datetime(h4.time, utc=True)
frames = {}
fD, zD, D = pack(d, pd.Timedelta(days=1), "%Y-%m-%d")
fW, zW, Wk = pack(W, pd.Timedelta(days=7), "%Y-%m-%d")
fH, zH, H4 = pack(h4, pd.Timedelta(hours=4), "%Y-%m-%d %H:%M")


def map_zones(zs_src, src, dst, bar_src):
    """Weekly zones drawn on a lower timeframe: positions by time."""
    t_dst = dst.time.values
    out = []
    Cs = src.close.values
    for q in zs_src:
        inv_t = None
        for j in range(q["known_idx"] + 1, len(src)):
            if (q["side"] == "bull" and Cs[j] < q["bottom"]) or (q["side"] == "bear" and Cs[j] > q["top"]):
                inv_t = src.time[j] + bar_src; break
        f0 = int(np.searchsorted(t_dst, src.time[q["form_idx"]].to_datetime64()))
        k0 = int(np.searchsorted(t_dst, (src.time[q["known_idx"]] + bar_src).to_datetime64()))
        iv = int(np.searchsorted(t_dst, inv_t.to_datetime64())) if inv_t is not None else -1
        out.append([1 if q["side"] == "bull" else 0, KIND.get(q["kind"], 0), f0, k0, iv, r2(q["bottom"]), r2(q["top"]),
                    first_touch(dst, min(k0, len(dst) - 1), q["side"] == "bull", q["bottom"], q["top"]) if k0 < len(dst) else -1])
    return out


D["wz"] = map_zones(zW, fW, fD, pd.Timedelta(days=7))
H4["wz"] = map_zones(zW, fW, fH, pd.Timedelta(days=7))
H4["dz"] = map_zones(zD, fD, fH, pd.Timedelta(days=1))

# cycles on daily closes: ATH close followed by a 50%+ fall; bottom = lowest close before the next ATH
C = fD.close.values; ds = fD.time.dt.strftime("%Y-%m-%d").values; n = len(C)
cyc, start = [], 0
while start < n:
    ai, hit = start, None
    for j in range(start, n):
        if C[j] >= C[ai]:
            ai = j
        if C[j] <= C[ai] * 0.5:
            hit = j; break
    if hit is None:
        break
    nxt = next((q for q in range(hit, n) if C[q] > C[ai]), n)
    bi = hit + int(np.argmin(C[hit:nxt]))
    cyc.append(dict(top=ds[ai], top_px=r2(C[ai]), bottom=ds[bi], bottom_px=r2(C[bi]), drop=r2((C[bi] / C[ai] - 1) * 100),
                    major=bool(C[bi] <= C[ai] * 0.3), confirmed=bool(nxt < n), next_ath=ds[nxt] if nxt < n else None))
    start = nxt
meta = dict(asof=ds[-1], cycles=cyc, halvings=["2012-11-28", "2016-07-09", "2020-05-11", "2024-04-20"])
moves = pd.read_csv(HERE / "moves.csv")
moves = moves[(moves.basis == "close") & (~moves.open)]
pos = {x: k for k, x in enumerate(ds)}
meta["m"] = [[int(r.level), pos.get(str(r.start_date)[:10], -1), pos.get(str(r.end_date)[:10], -1), r2(r.pct)] for r in moves.itertuples()]
OUT.mkdir(parents=True, exist_ok=True)
for name, obj in (("d1.json", D), ("w1.json", Wk), ("h4.json", H4), ("meta.json", meta)):
    (OUT / name).write_text(json.dumps(obj, separators=(",", ":")))
    print(name, round((OUT / name).stat().st_size / 1e6, 2), "MB", len(obj.get("c", [])), "candles")
