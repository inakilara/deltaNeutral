# 02: Reusable simplified backtest

One engine for every idea in 01_ideas.md: hourly steps, inverse payoffs, one fill and cost model, and accounting
in **USD** (capital, P&L and yields), on an account that holds BTC as Deribit requires. Simplified on purpose:
no order book, no latency, no queue position. Each simplification is listed with the sensitivity that bounds it.

## 1. Data and time alignment

All raw data is read in place from `C:\ClaudeSandbox\shared-data\` (read-only). Derived panels go to
`deltaNeutral/data/cache/` (git-ignored) and are rebuilt by a script.

| series | source | value used at hour `t` |
|---|---|---|
| option quotes (bid, ask, mark, IVs, delta, sizes, OI) | `option-chain/option_chain_hourly.parquet` | the snapshot stamped `t` |
| forward of each expiry | same file, `underlyingPrice` (Deribit's underlying for that expiry: the future if listed, otherwise a synthetic) | snapshot `t`; this is synchronous with the options, so it is used for every option–future trade |
| dated futures, perpetual | `deribit-futures/*_1h.parquet` candles (trade prices) | close of the bar `[t−1h, t)`, i.e. the last trade before `t`; NaN if the bar had no trades |
| index | `deribit-futures/deribit_BTC_perpetual_funding_1h.parquet` `index_price` | value at `t` |
| funding | same file, `interest_1h` | accrued for the hour ending at `t` |

- Common window with options: 2019-11-25 → 2026-10-25. Futures-only strategies can use 2019-04-30 (funding
  start) → 2026-11-19.
- **No look-ahead:** a strategy deciding at `t` sees only data stamped ≤ `t`. Funding for the hour ending at
  `t + 1` is unknown at `t`.
- **Expiry settlement:** Deribit settles at the 30-minute TWAP of the index before 08:00 UTC. The backtest uses
  the index at 08:00 (sensitivity: the 07:00 value).

### Slim panels (built once, cached)

The full chain is 39M rows, so strategies read compact per-hour panels:
- `options_<year>.parquet`: two-sided quotes only, with columns `t, expiry, strike, cp, bid, ask, mid, mark, iv,
  delta, bid_size, ask_size, F`.
- `forwards.parquet`: per hour and expiry, the future's price and the option-implied forward from put–call parity
  (median over strikes near ATM), plus the number of pairs.
- `futures.parquet`: per hour, every live future's price and volume, plus the perpetual, index and funding.

## 2. Instruments (inverse payoffs)

| instrument | unit | value / P&L in BTC |
|---|---|---|
| option | 1 contract = 1 BTC underlying, price in BTC | at expiry: call `max(S−K,0)/S`, put `max(K−S,0)/S` |
| dated future | USD notional `N` (10-USD contracts) | long: `N·(1/F_entry − 1/F_exit)`; expiry exit at the settlement index |
| perpetual | USD notional `N` | as a future, plus funding: a long pays `interest_1h · N / S_t` BTC each hour (a short receives it) |
| BTC balance (collateral, premiums, realised P&L) | BTC | held at 0 interest; USD value `balance · S` |

**Account USD value** = (BTC balance + Σ open positions' BTC mark-to-market) × `S`.
**USD delta** (∂USD value / ∂S, in BTC units) = BTC balance + Σ positions' deltas:
- a long future or perpetual with notional `N`: about `+N/F` BTC (a short `−N/F`), computed numerically by bumping
  `S` (and `F` with it);
- an option: its USD delta, `N(d1)` per contract for a call and `N(d1) − 1` for a put (Black-76 on the forward).

Checked on the data (`scripts/check_data.py`, June 2025, 35k quotes): Deribit's reported `delta` **is** this USD
delta (median difference 0.0000; vs the BTC delta `N(d1) − price`, 0.058). Mark prices equal Black-76 on
`markIv` divided by `F` to 3e-5 BTC (median). The engine computes deltas analytically, and a unit test checks
them against a numerical bump of the account's USD value.

## 3. Fills and costs (the brief's assumptions)

| instrument | buy fill | sell fill |
|---|---|---|
| option | **mid + 0.0010 BTC per contract** (10 bps of the 1-BTC underlying) | **mid − 0.0010 BTC** |
| future, perpetual | `price × (1 + 0.0004)` | `price × (1 − 0.0004)` |

- `mid = (bid + ask)/2`. A quote is tradable only if two-sided (bid > 0 and ask > 0). The cost is always charged
  in full, even when the quoted half-spread is narrower than 10 bps.
- Implementation: trades execute at mid (options) or the market price (linear), and the cost is booked as a
  separate cash flow, so it can be reported on its own line.
- Holding, funding and expiry settlement are free. **Holding to expiry avoids the exit cost**, which matters for
  every class-0 trade.
- Size check: trade size vs quoted `bid_size`/`ask_size`, and vs open interest (capacity diagnostic, not a
  constraint in the base case).
- Sensitivities run for every strategy:
  - option cost 0 / 5 / 10 / 20 bps of the underlying;
  - fills at the far side (bid/ask) instead of mid;
  - **one-hour delay**: decide at `t`, fill at `t+1h` prices. This is the key test of whether an arbitrage survives.

## 4. Engine

```
for t in hours:
    market = Market(t)                         # quote lookups for options, futures, perpetual, index, funding
    portfolio.accrue(t, market)                # funding, expiries settled at the index
    orders = strategy.on_hour(t, market, portfolio)
    portfolio.execute(orders, market, costs)   # fills plus costs, per sections 2–3
    hedger.rebalance(t, market, portfolio)     # keep the account's USD delta within the band (perpetual, 4 bps)
    portfolio.mark(t, market)                  # MTM at Deribit mark price (options) and futures close, in USD
```

- **Delta hedger:** after the strategy's orders, if |account USD delta| exceeds a band (default 0.25 % of
  capital; sensitivity 0.1 % and 1 %), trade the perpetual back to zero. A 1 % band left a visible long bias in a
  first 2024 run, because funding received adds BTC between rebalances. The hedge instrument can be
  set to the nearest dated future. The hedger's P&L (funding, basis, costs) is booked to the **collateral carry**
  line; the strategy's own instruments go to the **strategy** line. For delta-one and locked strategies it is idle
  apart from the collateral hedge and small BTC flows (premiums, realised P&L).

- **Strategy interface:** `on_hour(t, market, portfolio) -> list[Order]`, where an order is
  `(instrument, qty)`. A strategy is one small file in `strategies/` with a config dict.
- **Marking to market** uses Deribit's `markPrice` (falling back to mid) to avoid bid/ask noise in daily P&L. Trading
  always uses mid ± cost.
- **Two modes:**
  1. *Opportunity study* (class-0 arbitrage, B1/B2/B4): a trade held to expiry has its P&L known at entry, so each
     hour's opportunities are computed vectorised: frequency, net edge after costs, size available, how long each
     persists. No portfolio needed.
  2. *Portfolio backtest* (all strategies): the hourly loop above, with a capital constraint, for realised P&L,
     drawdowns and capital usage.

## 5. Capital and margin

- **Capital is USD**, deposited as BTC at the index at the start (no conversion cost assumed) and immediately
  hedged by the delta hedger (synthetic dollar). All P&L and yields are in USD.
- **Sizing:** a strategy gets `C` USD of capital and sizes its positions so the account's margin stays within it.
  Margin is in BTC and is checked against the BTC balance. The simplified Deribit standard margin:
  - futures and perpetual initial margin ≈ `2 % · N/S` BTC (sensitivity 5 %);
  - short option `max(0.15 − OTM/S, 0.10) + mark` BTC per contract;
  - long option: the premium.

  Offsetting delta-one legs (A1/A2) still post margin on both legs, and the capital is that margin plus a buffer
  for mark-to-market swings.
- **Base case: fully funded.** The strategy's gross USD notional is at most the capital (1×). Sensitivity: 2×,
  3× and 5× with the worst intra-period margin usage reported. With the synthetic-dollar hedge, the BTC balance
  scales with `1/S` like the margin of the short hedge, so a 1× account is not liquidated by price moves.
- Locked structures (box, conversion) are also reported per unit of maximum loss (~0 under portfolio margin).

## 6. Metrics (one table per strategy and year, in USD)

- Annualised USD return on USD capital, split into **strategy** and **collateral carry**; volatility; Sharpe;
  max drawdown; worst day and worst week.
- For class 0: locked yield at entry vs realised (they must match), share of hours with an opportunity, median and
  90th-percentile edge, persistence (hours), capacity (contracts available at the quote).
- Costs: share of gross P&L paid in costs, turnover, number of trades.
- Residual exposure: realised correlation of the USD P&L with BTC returns; account USD delta over time
  (should be ~0); hedger turnover.
- Benchmarks: A1 (locked basis, the Deribit "risk-free" USD rate) and A2 (funding). External T-bill rates are
  not in the data and are quoted for reference in the summary.

## 7. Validation (phase 1, before any strategy)

Unit tests in `tests/`:
1. **Cash-and-carry:** 1 BTC plus a short future `N = F_0`, held to expiry, is worth exactly `F_0` USD for any
   `S_T`.
2. **Synthetic dollar:** 1 BTC plus a short perpetual `N = S_0` has constant USD value without funding.
3. **Box:** a long box pays exactly `K2 − K1` USD for any `S_T`.
4. **Conversion in USD:** long call, short put, short future `N = F_0` ends at exactly `F_0 − K` USD for any `S_T`.
5. **Zero-cost mark round trip:** with costs at 0 and fills at mark, parity trades on real data earn ≈ 0 (marks
   are parity-consistent to ~5e-5 BTC).
6. **Cost accounting:** P&L = gross − Σ costs exactly; strategy + collateral carry = total.
7. **Delta:** Deribit's reported option delta matches the numeric bump of the option's USD value (or its BTC
   value); a hedged option over a small move has ~0 USD P&L.

## 8. Code layout

```
deltaNeutral/
  dn/                 data.py  panels.py  instruments.py  execution.py  portfolio.py  engine.py  metrics.py  report.py
  strategies/         a1_cash_carry.py  a2_funding.py  ...  c1_short_straddle.py
  scripts/            build_cache.py  run.py (--strategy a1 --config ...)  scan_arb.py
  tests/
  data/cache/         derived panels (git-ignored)
  reports/<strategy>/ tables and figures per run
  documents/          this design and the results documents
```

Environment: its own Python 3.12 `.venv` (pandas, numpy, pyarrow, scipy, matplotlib, pytest), pinned in
`requirements.txt`.

## 9. Known simplifications and their bounds

| simplification | effect | bound |
|---|---|---|
| hourly snapshots, instant fill at the snapshot | overstates arbitrage capture | one-hour-delay sensitivity |
| mid fills | optimistic for wide quotes | far-side sensitivity; the 10 bps already ≈ the full spread for liquid strikes |
| futures at last-trade close (no bid/ask) | stale prices in quiet hours | use the synchronous `underlyingPrice` for option–future trades; skip bars with no trades |
| settlement at the 08:00 index | settlement differs slightly from the TWAP | 07:00 sensitivity; tiny for held-to-expiry trades |
| no interest on BTC collateral, no external USD rate | USD yields are not excess returns over T-bills | quote T-bill rates in the summary; the collateral carry is shown separately |
| BTC deposited at the index, no spot trading cost | capital conversion is free | one-off; negligible over a multi-year backtest |
| no exchange or counterparty risk | not modelled | stated in the results |
