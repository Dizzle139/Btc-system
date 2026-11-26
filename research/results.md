# Research results (2026-11-26 17:51 UTC)

## 0. Data
- BTC daily: 5493 candles, 2011-11-01 to 2026-11-25, gaps 8, impossible candles 0
- BTC weekly (built from daily): 786 candles, 2011-10-31 to 2026-11-16, gaps 0, impossible candles 0
- BTC 4H: 28276 candles, 2014-01-01 to 2026-11-26, gaps 0, impossible candles 0

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
BTC forward return after each derivatives condition (Binance BTCUSDT perpetual; all days with data as baseline):
- Open interest fell >=15% in 7 days (leverage flush): Dec21-Apr24: 30d +1.3% vs all days +2.3% (n=68) | May24-Nov26: 30d -2.9% vs all days +1.1% (n=43)
- OI fell >=15% AND price fell >=10% in 7 days (long liquidation flush): Dec21-Apr24: 30d +1.6% vs all days +2.3% (n=40) | May24-Nov26: 30d -2.6% vs all days +1.1% (n=22)
- Open interest rose >=15% in 7 days (leverage building): Dec21-Apr24: 30d +1.3% vs all days +2.3% (n=100) | May24-Nov26: 30d +2.4% vs all days +1.1% (n=54)
- 7-day funding negative (shorts paying): Dec21-Apr24: 30d +15.8% vs all days +2.3% (n=124) | May24-Nov26: 30d +1.0% vs all days +1.1% (n=116)
- 7-day funding in top 10% (longs crowded): Dec21-Apr24: 30d +0.5% vs all days +2.3% (n=249) | May24-Nov26: 30d +nan% vs all days +1.1% (n=0)
- 7-day taker-buy share > 52% (aggressive buyers): Dec21-Apr24: 30d +24.3% vs all days +2.3% (n=28) | May24-Nov26: 30d -25.1% vs all days +1.1% (n=1)
- 7-day taker-buy share < 48% (aggressive sellers): Dec21-Apr24: 30d +5.1% vs all days +2.3% (n=47) | May24-Nov26: 30d -9.7% vs all days +1.1% (n=3)

Daily triggers with derivatives data: 39 (Dec 2021 onward)
- OI fell >=10% in prior 7 days: with +nanR (n=0) vs without +0.12R (n=39)
- 7-day funding negative: with +0.47R (n=3) vs without +0.09R (n=36)
- 7-day taker-buy share > 50%: with -0.04R (n=26) vs without +0.42R (n=13)

_Runtime 58s. Weekly rules were built on 2016-2026; 2012-2016 is unseen data for them._
