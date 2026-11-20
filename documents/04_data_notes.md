# 04: Data notes (checked 2026-11-19)

All data is in `C:\ClaudeSandbox\shared-data\` and is read-only: read in place, never modified, no files written
there. Each folder has its own README.

## Option chain: `option-chain/option_chain_hourly.parquet`

- 39.2M rows, hourly snapshots 2019-11-25 01:00 → 2026-10-25 23:00 UTC, 23 missing hours. About 250 instruments
  per hour in 2019, rising to about 900 in 2024–2026.
- Prices (`bid`, `ask`, `markPrice`) in **BTC per 1 BTC underlying**. IVs in vol points. `underlyingPrice` is the
  forward of each expiry: futures premium of 4–6 %/yr seen in a 2025 sample. `indexPrice` is the BTC index.
- Snapshots are exactly on the hour. The marks satisfy inverse put–call parity `C − P = 1 − K/F` to ~5e-5 BTC.
- **Two-sided quotes** (bid > 0 and ask > 0): 77 % of rows (2019), 62 % (2023), 87 % (2024-12), 91 % (2026-10).
  Mark lies inside bid–ask in 95–99.6 % of two-sided rows.
- Median relative spread (ask − bid)/mid: 13 % (2019) → 4–5 % (2025–26). Mostly wide in the far wings.
- **Full bid–ask spread in bps of underlying notional**, 2025 H1, by days to expiry × |delta|:

| days \ abs delta | ≤ 0.1 | 0.1–0.25 | 0.25–0.4 | 0.4–0.6 | 0.6–0.9 | > 0.9 |
|---|---|---|---|---|---|---|
| ≤ 2 | 2 | 4 | 5 | 10 | 30 | 570 |
| 2–9 | 2 | 5 | 10 | 10 | 35 | 100 |
| 9–35 | 3 | 10 | 10 | 10 | 45 | 65 |
| 35–100 | 3 | 10 | 10 | 10 | 60 | 65 |
| 100–400 | 10 | 20 | 25 | 40 | 80 | 45 |

  So for OTM and ATM options up to 100 days, **mid + 10 bps ≈ paying the full quoted spread**. ITM and long-dated
  options cost more than the assumption. The far-side sensitivity covers that.

Problems found in phase 3 (all handled in code):

- **Linear options mixed in from October 2026.** The chain also carries `BTC_USDC-…` options, which are USD-quoted.
  They make up more than half the rows after 2026-10-14. `dn.data.inverse_only` keeps `BTC-…` instruments only.
  It is used by `ChainReader` and by the futures-marks cache. Listed-future marks did not change.
- **No quote sizes before 2021.** `bidVolume`/`askVolume` are 0 in 2019–2020.
- **Absurd quotes.** Some two-sided quotes have asks of several BTC, so their mid means nothing. The mid ± 0.001
  rule is applied only to legs with a spread ≤ 0.005 BTC (50 bps of underlying).
- **Stale snapshots.**
  - In 35 hours, more than 80 % of expiries show an unchanged `underlyingPrice`. The longest run is
    2021-10-28 13:00–21:00.
  - In 2024-01-12…20, quotes and/or F are stale for hours at a time.
  - Single snapshots are out of sync, with F lagging the quotes: 2024-11-11 04:00, and in 2026 every 08:00
    snapshot, the daily settlement hour.
  - These create fake parity "arbitrages" of 2–6 % that vanish within an hour. Treat any opportunity that does not
    survive a one-hour delay as a data artefact.

## Deribit futures: `deribit-futures/`

- `deribit_BTC_perpetual_1h.parquet`: BTC-PERPETUAL hourly OHLCV, 2018-08-14 → 2026-11-19, no missing hours.
  Trade prices; `volume` in BTC, `cost` in USD.
- `deribit_BTC_perpetual_funding_1h.parquet`: `interest_1h`, `interest_8h`, `index_price`; 2019-04-30 → 2026-11-19,
  2 missing hours.
  - Annualised mean funding: 14.6 % (2019), 9.3 % (2020), 16.5 % (2021), −2.3 % (2022), 6.9 % (2023),
    10.3 % (2024), 5.4 % (2025), 2.4 % (2026).
  - Negative hours: 11–35 % depending on the year.
- `deribit_BTC_futures_1h.parquet`: 521 dated futures (live and expired), hourly OHLCV from their first trade.
  - Quarterlies only up to 2020; about 50 a year in 2021–2025 (weeklies, monthlies, quarterlies); daily futures
    from 2026.
  - About 5 % of futures hours have no trades (close repeated, volume 0).
- Annualised basis of futures with > 30 days to expiry, median by year: −1.8 % (2018), 3.7 % (2019), 7.1 % (2020),
  9.7 % (2021), 1.7 % (2022), 4.4 % (2023), 10.6 % (2024), 6.7 % (2025), 4.0 % (2026).
- Deribit perpetual vs Binance BTCUSDT hourly close: median difference 0.06 %, return correlation 0.998.

## Gaps that limit the study

- **Futures have no bid/ask**, only trade prices. For option–future trades the backtest uses the option chain's
  synchronous `underlyingPrice`.
- **Hourly resolution:** intra-hour arbitrage, and how fast quotes are refreshed, cannot be seen. The one-hour-delay
  test bounds this.
- **Quote sizes** (`bidVolume`/`askVolume`) only bound capacity at the top of the book.
- **Missing data:** no historical open interest for futures, no order-book depth, no USD interest rate.
