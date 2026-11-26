# BTC System

Rules-based BTC research and alerts. Every rule has to beat random entries **in the same era, in every era** (2012–16, 2016–21, 2021–26). Not financial advice.

## What's inside

| Folder | What it does | Runs where |
|---|---|---|
| `data_agent/` | Downloads Bitstamp BTC (daily from 2011, 4H from 2014) and the Binance archive (spot + perpetual taker volume, open interest, funding). Writes `data/DATA_REPORT.md` | GitHub Actions, every Monday + on demand |
| `research/` | `run_all.py` reruns every test and writes `research/results.md`. The derivatives tests run automatically once that data exists | GitHub Actions or any computer |
| `bot/` | Daily-close alert engine v4 → Telegram | GitHub Actions, 00:07 UTC daily |
| `tradingview/` | Same rules as a TradingView indicator; alerts run on TradingView's servers | TradingView (works from an iPad) |

## The rules (tested)
1. **Regime:** weekly EMA50 vs EMA200, plus weekly structure (swings 2 weeks each side). Long conviction = 0, 1 or 2.
2. **Map:** weekly FVG / order-block zones. Zones agreeing with EMA and structure held **70%** (random ~45–50%), including on unseen 2012–16 data.
3. **Trigger:** daily close above the last daily swing high (CHoCH up). Stop below the 10-day low. Target 3R.
   - **Grade A** (EMA and structure bullish): +0.94R per trade, 52 trades 2012–26, ahead of random entries in 2016–21 and 2021–26.
   - **Grade B** (EMA bullish only): +0.39R per trade, weak.
4. **Long only:** shorts showed no edge.

## Alerts (bot)
- `REGIME`: weekly BOS/CHoCH or EMA cross.
- `WATCH`: approaching an untested zone.
- `ZONE`: first test of a weekly zone, with conviction.
- `TRIGGER`: grade A/B entry with stop, 1R, 3R, and room to the next opposing zone.

Roughly 19 alerts a year in replay.

## Setup on GitHub (works from an iPad in Safari)
1. Create a free account at github.com → **New repository** → private → name it `btc-system`.
2. **Add file → Upload files** → upload everything in this folder. The `.github/workflows` folder must be included.
3. **Settings → Secrets and variables → Actions** → add `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`. See "Telegram" below.
4. **Actions** tab → enable workflows → **Data agent → Run workflow**. When it finishes, open `data/DATA_REPORT.md` to check every file downloaded.
5. **Actions → Daily alerts → Run workflow** to test the bot.

Uploading a hidden `.github` folder from an iPad can be awkward. If it doesn't work, give Claude access to the repository and Claude adds the files itself.

## Telegram
1. Message **@BotFather** → `/newbot` → copy the token.
2. Send your bot any message.
3. Open `https://api.telegram.org/bot<TOKEN>/getUpdates` and copy the `chat` → `id`.

## TradingView (usable now)
1. In Safari, open tradingview.com, then **aA → Request Desktop Website**.
2. Open a **daily** chart of BITSTAMP:BTCUSD.
3. **Pine Editor** → paste `tradingview/btc_conviction_v1.pine` → **Save** → **Add to chart**.
4. **Alert** → Condition: *BTC Conviction System v1* → **Any alert() function call** → expiration **open-ended**.
5. Notifications: app push (and webhook to Telegram later).

Differences from the Python bot:
- The indicator uses weekly **FVG** zones only (the bot also uses order blocks).
- It may repeat a zone-test alert if price alternates between zones.

## Verify
- `python bot/run.py --replay data/btc_1D.csv --from 2026-09-01` shows the alerts the bot would have sent.
- `python research/run_all.py` regenerates every number above.
