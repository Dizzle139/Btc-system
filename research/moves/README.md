# Moves: the answer key and the turning-point study

Run in order from this folder: `python mark_moves.py` → `python turns.py` → `python analyze.py`.

- `mark_moves.py` marks every BTC move of 10/20/30/50%+ on Bitstamp daily wicks and closes (zigzag). Output `moves.csv`.
- `turns.py` takes a snapshot of the chart at each turning point (start of a move, closes only) with a fixed checklist,
  using only data known at that day's close, plus the same snapshot for every ordinary day (`days.csv`, not committed: regenerate).
- `analyze.py` compares turns with ordinary days and with look-alike days (new 10-day closing extremes that did not turn),
  by era, and groups matching setups. Output `results.md`, `summary.json`, `snapshots.json`.

The page in `site/move-map/` shows it all (open `index.html` through a local web server).
Status: research only. Nothing here changes the alert bot.
