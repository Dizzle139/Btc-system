# Research results (2026-11-26 17:12 UTC)

## 0. Data
- BTC daily: 5493 candles, 2011-11-01 to 2026-11-25, gaps 8, impossible candles 0
- BTC weekly (built from daily): 786 candles, 2011-10-31 to 2026-11-16, gaps 0, impossible candles 0
- BTC 4H: 12945 candles, 2020-12-29 to 2026-11-26, gaps 0, impossible candles 0

## 1. Weekly zones held vs random (era-matched)
| filter | 2012-2016 | 2016-2021 | 2021-2026 |
|---|---|---|---|
| EMA agrees | 71% vs 47% (n=14) | 64% vs 45% (n=22) | 73% vs 46% (n=22) |
| EMA + structure agree | 71% vs 49% (n=14) | 64% vs 54% (n=22) | 76% vs 49% (n=21) |
| EMA against | 29% vs 25% (n=7) | 33% vs 18% (n=12) | 48% vs 41% (n=21) |

Conviction (EMA + structure) : 0/2 held 27% (n=11) | 1/2 held 43% (n=30) | 2/2 held 70% (n=57)

## 2. Daily trigger (daily CHoCH up, stop below 10-day low, 3R, 90 days, 0.2% costs)
- Grade A (EMA + structure bull): n=52, win 38%, avg +0.94R | 2012-2016: +0.66R vs random +0.74R (n=15) | 2016-2021: +1.74R vs random +1.05R (n=17) | 2021-2026: +0.48R vs random +0.15R (n=20)
- Grade B (EMA bull, structure not): n=54, win 28%, avg +0.39R | 2012-2016: +1.21R vs random +0.51R (n=11) | 2016-2021: +0.48R vs random +0.56R (n=17) | 2021-2026: +0.03R vs random +0.18R (n=25)
- Any regime: n=109, win 33%, avg +0.66R | 2012-2016: +0.89R vs random +0.67R (n=26) | 2016-2021: +1.11R vs random +0.86R (n=34) | 2021-2026: +0.21R vs random +0.16R (n=47)

## 3. Withdrawn rules, re-checked
- Weekly flush long (20%/8w/40% wick): 2012-2016: +1.67R vs random +1.20R (n=9) | 2016-2021: +0.00R vs random +1.14R (n=4) | 2021-2026: +0.71R vs random +0.40R (n=14)
- Daily OB held vs random: 2012-2016 49% vs 37% (n=93) | 2016-2021 45% vs 34% (n=111) | 2021-2026 41% vs 42% (n=143)
- Daily FVG held vs random: 2012-2016 60% vs 42% (n=134) | 2016-2021 52% vs 43% (n=155) | 2021-2026 45% vs 52% (n=171)

## 4. Extra data (runs when the file exists)
- USDT.D vs BTC weekly change correlation -0.85; with BTC one week later -0.07 (no lead if ~0)
Daily triggers split by derivatives state at the trigger day (only days where the data exists):
- open interest fell >=10% in 7 days (leverage flushed): with +0.45R (n=22) vs without +0.24R (n=39)
- 7-day funding negative (shorts paying): with +nanR (n=0) vs without +0.32R (n=61)
- 7-day taker-buy share > 50% (buyers aggressive): with +0.85R (n=32) vs without -0.26R (n=29)
  (weekly zone tests with OI are added once 2+ years of OI data exist)

_Runtime 59s. Weekly rules were built on 2016-2026; 2012-2016 is unseen data for them._
