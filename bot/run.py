#!/usr/bin/env python3
"""
BTC alert bot v4 (daily close).
  python bot/run.py                       live: fetch Bitstamp daily, alert on the last closed day
  python bot/run.py --dry-run             print instead of sending
  python bot/run.py --status              send status
  python bot/run.py --replay data/btc_1D.csv --from 2026-10-01   replay history from a CSV
Env: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID. Not financial advice.
"""
import argparse, json, os, sys
from pathlib import Path
import pandas as pd
import requests
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent / "data_agent"))
from engine import Engine, D1


def send(text, dry):
    tok, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if dry or not tok or not chat:
        print(("---- ALERT (Telegram not set up, printed only) ----\n" if not dry else "---- ALERT ----\n") + text + "\n"); return
    requests.post(f"https://api.telegram.org/bot{tok}/sendMessage",
                  json={"chat_id": chat, "text": text}, timeout=20).raise_for_status()


def load_csv(p):
    d = pd.read_csv(p).rename(columns={"Volume": "volume"})
    t = d["time"]
    d["time"] = pd.to_datetime(t.astype("int64"), unit="s", utc=True) if pd.api.types.is_numeric_dtype(t) else pd.to_datetime(t, utc=True)
    return d[["time", "open", "high", "low", "close", "volume"]].sort_values("time").reset_index(drop=True)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true"); p.add_argument("--status", action="store_true")
    p.add_argument("--replay"); p.add_argument("--from", dest="start", default="2026-10-01")
    a = p.parse_args()
    cfg = json.load(open(HERE / "config.json"))
    if a.replay:
        d = load_csv(a.replay)
        eng = Engine(d, cfg, now=d.time.iloc[-1])          # last row = still-open day
        idx = eng.D.index[eng.D.time >= pd.Timestamp(a.start, tz="UTC")]
        n = 0
        for i in idx:
            for al in eng.alerts_for_day(i):
                print(f"{al['t']:%Y-%m-%d} [{al['kind']}] {al['text']}\n"); n += 1
        print(f"{n} alerts since {a.start}\n\nSTATUS:\n{eng.status()}"); return
    import bitstamp
    d = bitstamp.daily_history("2011-08-01")
    eng = Engine(d, cfg)
    i = len(eng.D) - 1
    for al in eng.alerts_for_day(i):
        send(f"[{al['kind']}] {al['text']}", a.dry_run)
    if a.status or eng.D.time[i].weekday() == 6:           # weekly status after Sunday's close
        send("[STATUS]\n" + eng.status(), a.dry_run)
    print(f"checked daily close {eng.D.time[i] + D1:%Y-%m-%d}")
    # turn watch (research/moves): alerts for possible 10%+ turns, daily log and journal
    import turnwatch
    closed = d[d.time + D1 <= pd.Timestamp.now(tz="UTC")].reset_index(drop=True)
    mac, asof = turnwatch.market_live()
    day = closed.time.iloc[-1].tz_convert(None).strftime("%Y-%m-%d")
    msgs, _ = turnwatch.process(closed, mac, asof, [day], "live", send=lambda m: send(m, a.dry_run))
    print(f"turn watch {day}: {len(msgs)} alert(s); journal updated")


if __name__ == "__main__":
    main()
