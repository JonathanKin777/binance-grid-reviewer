# Binance Spot Grid Trade Reviewer

A tiny, zero-dependency Python tool that turns Binance's exported **trading-bot trade history CSV** into a readable grid P&L report.

Binance's official grid bot shows you live P&L in the app, but gives you no easy way to answer: *how many pairs did I close, at what profit each, and how often?* This script answers that from a CSV export — no API key needed.

## Why CSV, not API?

Many Binance accounts (e.g. region-restricted ones) can't create API keys at all. A CSV export works for everyone: App → Assets → Statements → Trading Bot → Trade History → Export CSV.

## Usage

```bash
python grid_review.py statement.csv --since "2026-10-03 10:04:55" --out report.md
```

- `statement.csv`: the file you exported from the Binance App
- `--since`: (recommended) only count trades after your grid was created, so an old terminated grid doesn't pollute the pairing
- `--out`: where to write the Markdown report (default `report.md`)

Python 3.8+, no third-party packages.

## How pairing works

Grid sells are matched against earlier unmatched buys using a **nearest-lower-buy** rule: each sell pairs with the highest-priced buy below it. This mirrors how a grid actually works (each grid level is independent) — plain FIFO mis-pairs trades in a downtrend.

Fee handling: fees are summed from the statement. Note the statement records the nominal 0.1% fee; if you use BNB discount, actual fees are lower — treat the "net" figure as an estimate and the App's grid P&L as ground truth.

## Example output

```
========== Grid Review ==========
Pair: BTCUSDT  |  2026-10-03 ~ 2026-10-13 (10 days)
38 trades (22 buys / 16 sells), 16 pairs closed
Gross pair profit +1.01U, fees ≈ -0.33U, net ≈ +0.68U
Avg per pair +0.0631U, 1.6 pairs/day
==============================
```

## Disclaimer

For record-keeping only. Not investment advice. I run this on my own small grid and post the reports — wins and losses alike.
