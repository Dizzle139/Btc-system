# Research results (2026-11-26 17:37 UTC)

## 0. Data
- BTC daily: 908 candles, 2011-11-01 to 2014-04-26, gaps 0, impossible candles 0
- BTC weekly (built from daily): 129 candles, 2011-10-31 to 2014-04-14, gaps 0, impossible candles 0
- BTC 4H: 28276 candles, 2014-01-01 to 2026-11-26, gaps 0, impossible candles 0

## 1. Weekly zones held vs random (era-matched)
| filter | 2012-2016 | 2016-2021 | 2021-2026 |
|---|---|---|---|
| EMA agrees | 75% vs 55% (n=8) | nan% vs nan% (n=0) | nan% vs nan% (n=0) |
| EMA + structure agree | 75% vs 53% (n=8) | nan% vs nan% (n=0) | nan% vs nan% (n=0) |
| EMA against | 0% vs 34% (n=2) | nan% vs nan% (n=0) | nan% vs nan% (n=0) |

Conviction (EMA + structure) : 0/2 held 0% (n=2) | 1/2 held nan% (n=0) | 2/2 held 75% (n=8)

## 2. Daily trigger (daily CHoCH up, stop below 10-day low, 3R, 90 days, 0.2% costs)
- Grade A (EMA + structure bull): n=7, win 29%, avg +0.51R | 2012-2016: +0.51R vs random +1.17R (n=7) | 2016-2021: - | 2021-2026: -
- Grade B (EMA bull, structure not): n=5, win 60%, avg +2.37R | 2012-2016: +2.37R vs random +1.38R (n=5) | 2016-2021: - | 2021-2026: -
- Any regime: n=14, win 43%, avg +1.24R | 2012-2016: +1.28R vs random +1.16R (n=12) | 2016-2021: - | 2021-2026: -

## 3. Withdrawn rules, re-checked
- Weekly flush long (20%/8w/40% wick): 2012-2016: +1.75R vs random +2.35R (n=5) | 2016-2021: - | 2021-2026: -
- Daily OB held vs random: 2012-2016 53% vs 35% (n=51) | 2016-2021 nan% vs nan% (n=0) | 2021-2026 nan% vs nan% (n=0)
- Daily FVG held vs random: 2012-2016 58% vs 44% (n=76) | 2016-2021 nan% vs nan% (n=0) | 2021-2026 nan% vs nan% (n=0)

## 4. Extra data (runs when the file exists)
- USDT.D vs BTC weekly change correlation +nan; with BTC one week later +nan (no lead if ~0)
Daily triggers split by derivatives state at the trigger day (only days where the data exists):
- open interest fell >=10% in 7 days (leverage flushed): with +nanR (n=0) vs without +nanR (n=0)
- 7-day funding negative (shorts paying): with +nanR (n=0) vs without +nanR (n=0)
- 7-day taker-buy share > 50% (buyers aggressive): with +nanR (n=0) vs without +nanR (n=0)
  (weekly zone tests with OI are added once 2+ years of OI data exist)

_Runtime 8s. Weekly rules were built on 2016-2026; 2012-2016 is unseen data for them._
