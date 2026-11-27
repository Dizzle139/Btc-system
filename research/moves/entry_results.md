# Step 8: entry methods

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

## long (bottoms)

| Method | Signals | Win 10/5 2011-18 | Win 10/5 2019-26 | Win 20/10 2011-18 | Win 20/10 2019-26 | Beats random in both halves |
|---|---|---|---|---|---|---|
| TURN alert | 91 | 29.5% (44) | 40.4% (47) | 27.3% (44) | 45.5% (44) | 10/5: no, 20/10: no |
| CHOCH | 111 | 56.5% (46) | 44.6% (65) | 60.9% (46) | 45.2% (62) | 10/5: yes, 20/10: yes |
| BREAK 20-day | 214 | 65.0% (103) | 45.9% (111) | 67.0% (103) | 42.6% (108) | 10/5: yes, 20/10: no |
| HIGHER LOW | 51 | 44.4% (18) | 34.4% (32) | 55.6% (18) | 38.7% (31) | 10/5: no, 20/10: no |
| CHOCH after a TURN alert | 45 | 50.0% (20) | 44.0% (25) | 60.0% (20) | 43.5% (23) | 10/5: no, 20/10: yes |
| BREAK 20-day after a TURN alert | 33 | 70.0% (10) | 47.8% (23) | 70.0% (10) | 40.9% (22) | 10/5: yes, 20/10: no |
| HIGHER LOW after a TURN alert | 29 | 36.4% (11) | 33.3% (18) | 54.5% (11) | 44.4% (18) | 10/5: no, 20/10: yes |
| random day (baseline) | 5550 | 52.7% (2663) | 43.6% (2880) | 53.5% (2656) | 42.6% (2759) | – |

## short (tops)

| Method | Signals | Win 10/5 2011-18 | Win 10/5 2019-26 | Win 20/10 2011-18 | Win 20/10 2019-26 | Beats random in both halves |
|---|---|---|---|---|---|---|
| TURN alert | 85 | 23.3% (43) | 40.5% (42) | 16.3% (43) | 35.0% (40) | 10/5: no, 20/10: no |
| CHOCH | 109 | 40.9% (44) | 24.6% (65) | 34.1% (44) | 25.8% (62) | 10/5: no, 20/10: no |
| BREAK 20-day | 154 | 50.0% (66) | 35.6% (87) | 37.9% (66) | 31.8% (85) | 10/5: yes, 20/10: yes |
| LOWER HIGH | 76 | 35.7% (28) | 31.2% (48) | 26.9% (26) | 21.3% (47) | 10/5: yes, 20/10: no |
| CHOCH after a TURN alert | 37 | 37.5% (16) | 28.6% (21) | 31.2% (16) | 33.3% (21) | 10/5: no, 20/10: yes |
| BREAK 20-day after a TURN alert | 23 | 55.6% (9) | 21.4% (14) | 33.3% (9) | 50.0% (14) | 10/5: no, 20/10: no |
| LOWER HIGH after a TURN alert | 34 | 37.5% (16) | 44.4% (18) | 26.7% (15) | 44.4% (18) | 10/5: yes, 20/10: no |
| random day (baseline) | 5550 | 31.6% (2663) | 30.0% (2874) | 29.1% (2629) | 28.3% (2784) | – |

## Your marked moves: first entry each method gave (from 10 days before your start to your end)

| Move | TURN alert | CHOCH | BREAK 20-day | HIGHER LOW | CHOCH after a TURN alert | BREAK 20-day after a TURN alert | HIGHER LOW after a TURN alert |
|---|---|---|---|---|---|---|---|
| Jan 2026 top | 2026-01-13 (97% of your move left) | 2026-01-20 (82% of your move left) | 2026-01-25 (78% of your move left) | 2026-01-25 (78% of your move left) | 2026-01-20 (82% of your move left) | 2026-01-25 (78% of your move left) | 2026-01-25 (78% of your move left) |
| Sep 2024 low | 2024-09-01 (90% of your move left) | 2024-09-12 (87% of your move left) | 2024-09-18 (75% of your move left) | 2024-09-18 (75% of your move left) | 2024-09-12 (87% of your move left) | 2024-09-18 (75% of your move left) | 2024-09-18 (75% of your move left) |
| Oct 2025 top | 2025-10-03 (96% of your move left) | 2025-10-16 (65% of your move left) | 2025-10-16 (65% of your move left) | 2025-10-15 (72% of your move left) | 2025-10-16 (65% of your move left) | 2025-10-16 (65% of your move left) | 2025-10-15 (72% of your move left) |
| Apr 2025 low (trade 1) | 2025-04-06 (92% of your move left) | 2025-04-21 (59% of your move left) | 2025-04-21 (59% of your move left) | 2025-04-17 (68% of your move left) | 2025-04-21 (59% of your move left) | 2025-04-21 (59% of your move left) | 2025-04-17 (68% of your move left) |
| Apr 2025 low (trade 2) | 2025-04-06 (92% of your move left) | 2025-04-21 (63% of your move left) | 2025-04-21 (63% of your move left) | 2025-04-17 (71% of your move left) | 2025-04-21 (63% of your move left) | 2025-04-21 (63% of your move left) | 2025-04-17 (71% of your move left) |
| Jun 2026 low | 2026-06-24 (84% of your move left) | 2026-07-14 (61% of your move left) | 2026-07-14 (61% of your move left) | 2026-07-10 (66% of your move left) | 2026-07-14 (61% of your move left) | 2026-07-14 (61% of your move left) | 2026-07-10 (66% of your move left) |
| Oct 2026 lower high | none | 2026-10-08 (84% of your move left) | 2026-10-14 (84% of your move left) | 2026-09-29 (92% of your move left) | 2026-10-08 (84% of your move left) | none | 2026-09-29 (92% of your move left) |
| Sep 2023 low | 2023-10-11 (96% of your move left) | 2023-09-14 (98% of your move left) | 2023-10-01 (90% of your move left) | 2023-09-19 (94% of your move left) | 2023-10-16 (87% of your move left) | 2023-10-16 (87% of your move left) | none |
| Mar 2020 low | 2020-09-03 (50% of your move left) | 2020-04-06 (76% of your move left) | 2020-04-02 (83% of your move left) | 2020-03-18 (109% of your move left) | 2020-09-14 (47% of your move left) | none | 2020-03-18 (109% of your move left) |
