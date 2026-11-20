# deltaNeutral: yield strategies on Deribit BTC inverse instruments

Goal: find and measure **yield-like strategies with low or no market risk** that run only on Deribit's BTC
inverse instruments (options, dated futures, perpetual). Examples: arbitrages, carry trades that lock a rate on
capital posted up front, and delta-neutral premium harvesting. Each strategy is backtested on the shared hourly
history with one reusable engine and one cost model.

| document | content |
|---|---|
| [01_ideas.md](01_ideas.md) | catalogue of strategy ideas: mechanics, what each earns, residual risks, priority |
| [02_backtest_framework.md](02_backtest_framework.md) | the reusable simplified backtest: data, conventions, fills and costs, capital, metrics, code layout |
| [03_test_designs.md](03_test_designs.md) | one test design per idea: construction, rules, measurements, sensitivities, kill criteria |
| [04_data_notes.md](04_data_notes.md) | what the shared data contains and its limits (checked 2026-11-19) |
| [results_A.md](results_A.md) | phase 2: delta-one carry (A1–A5) |
| [results_B.md](results_B.md) | phase 3: option parity (B1–B5) |
| [results_C.md](results_C.md) | phase 4: option risk premia (C1–C3) |
| [results_summary.md](results_summary.md) | **phase 5: comparison, portfolios, recommendation (start here for results)** |

**Status (2026-11-20):** all phases run.

- **Core:** perpetual funding carry, 7.3 %/yr, vol 1.4 %.
- **Optional lock:** the cash-and-carry.
- **Risk-bucket overlay:** the 30-day short straddle.
- **No tradable arbitrage** in option parity.

## Assumptions fixed by the brief

- Instruments: Deribit BTC inverse options, dated futures and BTC-PERPETUAL only. They settle in BTC.
- **Accounting in USD:** capital, P&L and yields in USD. The account holds BTC hedged to a synthetic dollar.
  Strategies that lock a USD amount need nothing more. Strategies that lock a BTC amount add a short inverse
  future of the same expiry, so the result is locked in USD.
- **Options fill at mid price plus an execution cost of 10 bps** covering fees, slippage and market impact.
  The 10 bps is taken on the underlying price (0.001 BTC per contract), as Deribit charges option fees. For liquid
  strikes this is about the full quoted spread, so it is not an optimistic assumption (see 04_data_notes.md).
- **Futures and the perpetual fill at the reference price plus 4 bps** of notional.
- Expiry settlement, funding and holding positions cost nothing.
- Data: the hourly snapshots in `C:\ClaudeSandbox\shared-data\` (read-only, read in place). The common window
  for options plus futures is 2019-11-25 → 2026-10-25.

## Plan

| phase | content | output |
|---|---|---|
| 0. setup | project venv, data loaders, slim cached panels built from the shared data (`data/cache`, git-ignored) | `dn/data.py`, cache build script |
| 1. engine | instruments (inverse payoffs), fills and costs, portfolio with USD accounting and a delta hedger, metrics; unit tests that check the payoff identities (carry, box, conversion locks) | `dn/` package plus `tests/`, all green |
| 2. delta-one carry | A1 cash-and-carry, A2 funding carry, A5 best-carry roll, A3 funding vs basis, A4 futures calendar | `documents/results_A.md` |
| 3. option parity | B1 conversion/reversal, B2 box spreads, B3 jelly roll, B4 static no-arbitrage scan | `documents/results_B.md` |
| 4. volatility carry | C1 delta-hedged short straddle, C2 IV calendar, C3 skew carry | `documents/results_C.md` |
| 5. synthesis | one comparison table (yield, risk, capacity, cost share), correlations, a combined portfolio, a recommendation | `documents/results_summary.md` |

Phases 2–4 use the same engine. A strategy is one file in `strategies/` plus its section in
03_test_designs.md. Every result document lists the exact settings used, so each run can be reproduced.
