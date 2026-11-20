# Results A: delta-one carry (A1–A5)

Phase 2, run 2026-11-19/20.

- **Window:** 2019-05-01 → 2026-11-19 (7.55 years).
- **Capital:** USD 1M, deposited as BTC and hedged to USD by the hedger (band 0.25 % of capital unless stated).
- **Costs:** futures and perpetual 4 bps of notional per trade.
- **Futures prices:** the option chain's synchronous `underlyingPrice` marks, falling back to traded closes.
- **Code:** `scripts/run_phase2.py`. **Outputs:** `reports/phase2/`.

All returns are in USD, net of costs, annualised.

## Verdict

- **The perpetual funding carry (A2) is the best low-risk yield:** 8.0 %/yr, vol 1.5 %, max drawdown −4.0 %,
  correlation with BTC ≈ 0. It is the synthetic dollar itself: hold BTC, short the perpetual, collect funding.
  - It lost money in one year (2022: −2.2 %), when funding turned negative.
- **The cash-and-carry (A1) locks the basis:** 6.0 %/yr over the window, known at entry.
  - It is volatile in between: vol 4.9 %, drawdown −6.8 %, from mark-to-market of the basis. That converges at
    expiry.
  - It beat A2 in 2022, 2024, 2025 and 2026.
- **Switching between A1 and A2 (A2-switch, A5) adds nothing robust.**
  - Without a margin it churns and loses.
  - With a 25 bp margin it shows 8.3–8.8 %, but at three times A2's vol.
  - A price-source check shows that much of the gross carry of frequent switching is harvested noise in the hourly
    futures marks.
- **Funding forecasting (A3) and the futures calendar (A4) have no edge.**
  - The forecast of funding vs basis has R² 0.001 out of sample.
  - The A3 signal overlays and A4 earn −0.7 to +0.2 %/yr over A2.

## Summary

| Run | Return | Vol | Sharpe | Max DD | Worst week | Costs/yr | Correlation with BTC | Hedge trades |
|---|---|---|---|---|---|---|---|---|
| **A2 perpetual (band 0.25 %)** | **8.01 %** | 1.47 % | 5.26 | −4.00 % | −2.3 % | 0.01 % | −0.04 | 397 |
| A2 perpetual (band 0.10 %) | 8.00 % | 1.47 % | 5.25 | −3.99 % | −2.4 % | 0.01 % | −0.05 | 1,005 |
| A2 perpetual (band 1.00 %) | 7.87 % | 1.50 % | 5.07 | −4.47 % | −2.6 % | 0.01 % | +0.03 | 93 |
| **A1 nearest quarterly** | **5.99 %** | 4.89 % | 1.21 | −6.78 % | −2.9 % | 0.20 % | −0.39 | 31 |
| A1 nearest quarterly (candle closes) | 5.96 % | 4.85 % | 1.22 | −6.85 % | −3.0 % | 0.20 % | −0.40 | 31 |
| A1 nearest monthly | 5.86 % | 4.66 % | 1.25 | −6.78 % | −2.9 % | 0.51 % | −0.36 | 74 |
| A1 closest to 30 d | 6.16 % | 4.44 % | 1.37 | −6.78 % | −1.4 % | 0.54 % | −0.35 | 77 |
| A1 closest to 180 d | 5.75 % | 5.77 % | 1.00 | −7.56 % | −2.9 % | 0.10 % | −0.42 | 16 |
| A2-switch lb 7 d, m 0 bp | 6.61 % | 5.20 % | 1.26 | −7.41 % | −3.1 % | 11.0 % | −0.30 | 1,009 |
| A2-switch lb 7 d, m 25 bp | 8.55 % | 5.06 % | 1.65 | −5.63 % | −2.9 % | 3.1 % | −0.33 | 416 |
| A2-switch lb 30 d, m 25 bp | 8.30 % | 4.58 % | 1.76 | −6.91 % | −3.2 % | 1.9 % | −0.32 | 309 |
| A5 best carry lb 7 d, m 0 bp | 3.49 % | 5.25 % | 0.68 | −8.83 % | −3.3 % | 15.0 % | −0.27 | 1,342 |
| A5 best carry lb 7 d, m 25 bp | 8.82 % | 5.00 % | 1.72 | −5.63 % | −2.6 % | 3.6 % | −0.32 | 426 |
| A5 best carry lb 30 d, m 25 bp | 8.38 % | 4.58 % | 1.78 | −6.91 % | −3.2 % | 2.3 % | −0.30 | 319 |
| A3 long basis / short perpetual | 9.37 % | 4.08 % | 2.22 | −7.65 % | −5.0 % | 0.50 % | +0.30 | 759 |
| A3 signal lb 30 d, threshold 2 % | 8.18 % | 4.01 % | 1.98 | −5.76 % | −3.2 % | 0.50 % | +0.04 | 448 |
| A4 calendar near/far quarterly | 7.43 % | 2.95 % | 2.44 | −2.68 % | −1.1 % | 0.49 % | −0.34 | 392 |

(lb = lookback, m = switching margin. All 26 runs are in `reports/phase2/summary.csv`.)

Return by calendar year, %:

| Run | 2019* | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026* |
|---|---|---|---|---|---|---|---|---|
| A2 perpetual | 15.8 | 9.9 | 18.1 | −2.2 | 7.0 | 11.0 | 5.5 | 2.4 |
| A1 nearest quarterly | 4.6 | 4.6 | 10.0 | 2.5 | 1.6 | 14.1 | 7.1 | 3.3 |
| A1 closest to 30 d | 4.6 | 4.6 | 14.5 | 0.5 | 3.8 | 12.9 | 5.8 | 2.5 |
| A5 lb 7 d, m 25 bp | 0.1 | 7.5 | 18.7 | 8.7 | 6.5 | 15.1 | 7.7 | 3.8 |
| A3 long basis / short perpetual | 26.7 | 13.5 | 23.3 | −5.4 | 10.1 | 8.8 | 4.4 | 1.7 |
| A4 calendar | 8.3 | 7.3 | 21.9 | 0.0 | 3.8 | 10.1 | 6.8 | 2.2 |

\* Partial years, annualised.

## A2: perpetual funding carry

- **Construction.** The account holds BTC and shorts the perpetual for the same USD notional. Every hour it receives
  `interest_1h × N` (pays when negative).
  - Returns track mean funding: 14.6 %, 9.3 %, 16.5 %, −2.3 %, 6.9 %, 10.3 %, 5.4 %, 2.4 % (2019–2026).
  - Hedge-band slippage and costs are negligible: 0.01 %/yr.
- **The band barely matters.** 0.10 % and 0.25 % give the same result. 1 % leaves a small residual delta
  (correlation +0.03) and costs about 0.15 %/yr.
- **Risk.** The worst stretch is funding turning negative for months (2022). The vol is funding variability, not
  price risk.
  - Not modelled: exchange or counterparty risk, and perpetual liquidation. The short perpetual is fully
    collateralised by the BTC held, so a price spike does not liquidate it under portfolio margin.
- **Funding is falling.** It has declined since 2024, to 2.4 % in 2026 so far.

## A1: cash-and-carry

- **Construction.** BTC plus a short dated future, which locks `F₀` USD at expiry. It is rolled to the next contract
  at expiry, choosing by tenor rule.
- **Return vs vol.** The locked return is the basis: median 3.7–10.6 %/yr by year.
  - The 4.9 % vol and the −0.39 correlation with BTC are mark-to-market. The basis widens in rallies, so the short
    future loses temporarily. It all converges at expiry.
  - For an investor who can hold to expiry, the economic risk is far lower than the vol suggests.
- **Tenor.**
  - 30-day contracts earned most (6.16 %) and were the least volatile: more frequent re-locks capture rising-basis
    periods.
  - 180-day contracts earned least (5.75 %) with the most mark-to-market (vol 5.8 %).
  - Quarterly and 90-day are the same strategy here.
- **Price source.** Valuing at traded candle closes instead of synchronous marks changes almost nothing
  (5.96 % vs 5.99 %), because A1 trades only at rolls.
- **A1 vs A2.**
  - A2 out-earned A1 by about 2 %/yr over the window. Funding exceeded the basis in the 2019–21 bull years.
  - A1 won in 2022, 2024, 2025 and 2026. The basis prices future funding, but with a premium in some years and a
    discount in others. That is A3's question, answered below.

## A2-switch and A5: hold whichever carries more

- **Policy.** Hold the hedge in whichever instrument (perpetual or a future) has the higher expected carry:
  - for the perpetual, trailing funding over the lookback;
  - for a future, its annualised basis.

  Switch only when the expected gain over the remaining horizon exceeds the round-trip cost (8 bps) plus a margin.
  Decisions use the previous hour's prices.
- **No margin is a disaster** (3.5 %, and 1.8 % at lb 30 d). The policy switches about 700 times and pays 11–15 % of
  capital a year in costs.
- **With a 25 bp margin**, about 4–6 switches a year: 8.3–8.8 %. That is up to +0.8 %/yr over A2, but with vol
  4.6–5.0 % against 1.5 %, and a worse 2019 (only 0.1 %, against A2's 15.8 %).
- **Noise check** (`scripts/check_a5_noise.py`, A5 lb 7 d, no margin):

  | Futures priced at | Futures cost | Net | Costs/yr | Gross |
  |---|---|---|---|---|
  | synchronous marks | 4 bps | 3.5 % | 15.0 % | 18.5 % |
  | synchronous marks | 8 bps | 1.0 % | 12.1 % | 13.1 % |
  | traded candle closes | 4 bps | −22.9 % | 26.0 % | 3.1 % |
  | traded candle closes | 8 bps | −20.3 % | 22.0 % | 1.7 % |

  An 18 % gross carry from switching between instruments that each carry 6–8 % is not plausible. The policy is
  picking up hour-to-hour noise in the futures marks: the basis looks high when the mark is briefly rich, and the
  switch "sells" at that price. On traded prices the gross carry is 2–3 %.

  Futures have no bid/ask in the data, so neither price series shows what a switch would really fill at. The
  low-turnover (25 bp) variants are less exposed, but their small edge over A2 is within that uncertainty.
- **Verdict:** not adopted. A2 alone dominates on risk-adjusted terms. A slow rule (switch only on large,
  persistent gaps) remains an option, but it needs real futures quotes to evaluate.

## A3: funding vs basis

- **Forecast test.** For every quarterly future, daily while 14–120 days from expiry, we compare realised mean
  funding until expiry with forecasts available at the time (`reports/phase2/funding_forecast.csv`):

  | Sample | realised ~ trailing 7 d | realised ~ trailing 30 d | realised ~ basis | (realised − basis) ~ (trailing 30 d − basis) |
  |---|---|---|---|---|
  | fit 2019–22 (n = 1,543) | R² 0.135 | 0.152 | 0.124 | **0.031** |
  | test 2023–26 (n = 1,574) | 0.175 | 0.154 | 0.215 | **0.001** (slope −0.05) |

  - Trailing funding and the basis each explain about 15–20 % of future funding.
  - Whether funding will beat the basis, which is what an A3 trade bets on, is unpredictable out of sample.
- **Overlays on the A2 collateral** (total − A2):

  | Overlay | Total | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
  |---|---|---|---|---|---|---|---|---|---|
  | short basis / long perpetual | −2.33 | −11.8 | −5.3 | −7.6 | +3.6 | −4.6 | +2.2 | +0.8 | +0.4 |
  | long basis / short perpetual | +1.36 | +11.0 | +3.6 | +5.2 | −3.2 | +3.1 | −2.2 | −1.1 | −0.7 |
  | signal lb 7 d, threshold 2 % | −0.42 | −13.0 | −1.6 | +4.4 | +1.4 | +3.9 | −3.6 | +0.8 | +0.4 |
  | signal lb 30 d, threshold 2 % | +0.18 | +1.0 | −1.4 | +5.5 | +2.8 | −1.7 | −3.1 | −2.0 | +1.0 |

  - "Short basis / long perpetual" plus the A2 collateral is A1, and earns A1's return.
  - "Long basis / short perpetual" is double the perpetual carry funded by a long future. It earned +1.4 %/yr, all
    from 2019–21 when funding ran above the basis. It has lost since 2024, and it is correlated with BTC (+0.30).
- **Kill criterion met:** no out-of-sample edge, and the signal overlays are zero ± 0.7 %/yr.

## A4: futures calendar (long near / short far quarterly)

- **Result:** overlay −0.58 %/yr. It loses when the curve steepens (2019, 2020, 2023) and gains when it flattens
  (2021, 2022, 2025).
- **Kill.** This is a directional bet on the shape of the term structure, not a carry.

## A6: expiry convergence

Not run (low priority). Phase 3 showed what it would face: a futures price that converges to the index under
noise of a few bps, against 8 bps of round-trip cost.

## Lessons for the framework

- **Stale prices produce fake carry.** An earlier run priced futures at candle closes that can be hours old, and
  "earned" +1,800 % in 2022. Fixes:
  - synchronous marks;
  - one-hour decision delay;
  - no hedge trading on an instrument with no price;
  - (bug fix) the account delta keeps unpriced positions at their last settled price.
- **Turnover is the enemy of carry.** Any rule that trades more than a few times a year on futures marks needs a
  price-noise check like the one above.
