# Results C: option risk premia (C1–C3)

Phase 4, run 2026-11-20.

- **Window:** 2019-12-01 → 2026-10-25, the option-chain coverage. Statistics below start 2020-01-01, skipping the
  one-month 2019 stub.
- **Capital:** USD 1M on the A2 synthetic-dollar collateral. The perpetual hedger keeps the account's USD delta
  within a band of 2 %, 5 % or 10 % of capital.
- **Costs:** options at mid ± 0.001 BTC per contract, perpetual 4 bps.
- **Code:** `strategies/options.py`, `scripts/run_phase4.py`, `scripts/phase4_overlay.py`. **Outputs:**
  `reports/phase4/`.

**How the results are measured.**

- Each structure is run at 1× capital notional per leg.
- Its **overlay** is the run's daily USD return minus the A2 baseline's (7.2 %/yr over this window).
- 1× notional is not feasible: peak margin under the simplified Deribit standard margin reaches 68–124 % of
  equity. So the overlay is **scaled to a 50 % peak margin ratio**, as `03_test_designs.md` asks. Positions,
  hedges and costs all scale linearly.

## Verdict

- **Only the 30-day delta-hedged short straddle (C1) has earned a premium.**
  - Scaled to 50 % margin: **+2.2 %/yr over A2**, vol 4.1 %, overlay max drawdown −8.0 %, worst week −4.1 %.
  - The premium is concentrated in 2021–22 (+8.8 %, +2.9 %). It is about flat in 2023–26 (−1.5 %, +2.0 %, +0.1 %,
    +0.6 %).
  - This is a risk premium with crash exposure (−12.6 % unscaled in March 2020), not a yield. Risk class 2.
- **Weekly straddles lose to costs.** At mid ± 0.001 per leg, rolling a 1×-notional straddle every week costs
  10.4 % of capital a year in option costs alone, about equal to the premium earned.
- **C2 (IV calendar) and C3 (skew) are killed.**
  - C2 loses about 8 %/yr: two straddles re-struck every cycle cost about 19 %/yr.
  - C3's risk reversal loses in 6–7 of 7 years. Its short-wings butterfly loses in 6 of 7.

## C1: delta-hedged short straddle

Overlay over A2, scaled to 50 % peak margin (2020-01 → 2026-10):

| Variant | Scale | Overlay | Vol | Sharpe | Max DD | Worst week | Worst year | Years < 0 |
|---|---|---|---|---|---|---|---|---|
| **30 d, band 10 %** | 0.44 | **+2.21 %** | 4.1 % | 0.54 | −8.0 % | −4.1 % | −1.5 % | 1 |
| 30 d, band 5 % | 0.42 | +1.84 % | 3.9 % | 0.47 | −7.5 % | −4.5 % | −1.0 % | 1 |
| 30 d, band 2 % | 0.42 | +1.58 % | 3.8 % | 0.42 | −7.6 % | −3.9 % | −1.3 % | 2 |
| 30 d, band 5 %, IV − RV > 5 pts | 0.40 | +1.53 % | 3.7 % | 0.41 | −7.5 % | −4.4 % | −2.9 % | 2 |
| 30 d, band 5 %, IV − RV > 10 pts | 0.41 | +0.84 % | 4.1 % | 0.20 | −10.7 % | −4.5 % | −5.3 % | 2 |
| 14 d, band 10 % | 0.54 | +2.39 % | 5.0 % | 0.47 | −15.2 % | −3.4 % | −0.8 % | 2 |
| 14 d, band 5 % | 0.54 | +1.99 % | 4.7 % | 0.42 | −12.0 % | −2.9 % | −1.3 % | 3 |
| 7 d, band 10 % | 0.74 | +1.04 % | 7.5 % | 0.14 | −14.8 % | −3.8 % | −5.6 % | 5 |
| 7 d, band 5 % | 0.70 | −0.20 % | 7.3 % | −0.03 | −16.5 % | −3.6 % | −5.9 % | 5 |
| 7 d, band 5 %, close 1 d before expiry | 0.69 | −5.76 % | 9.8 % | −0.59 | −38.4 % | −9.0 % | −16.6 % | 5 |

Overlay by year (scaled, %):

| Variant | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|---|
| 30 d, band 10 % | 2.2 | 8.8 | 2.9 | −1.5 | 2.0 | 0.1 | 0.6 |
| 14 d, band 10 % | 3.4 | 4.9 | 7.9 | 0.3 | −0.1 | 0.7 | −0.8 |
| 7 d, band 10 % | −0.5 | 15.0 | 5.2 | −5.6 | −1.5 | −3.4 | −2.2 |

Crash windows. Total return of the unscaled 1× run (collateral included) vs A2:

| Window | A2 | C1 30 d, band 10 % | C1 14 d, band 10 % | C1 7 d, band 10 % |
|---|---|---|---|---|
| 2020-03-08 → 03-20 (covid) | −2.6 % | −12.6 % | −8.0 % | −8.8 % |
| 2021-05-10 → 05-25 (China ban) | −0.1 % | −4.4 % | −7.8 % | −8.6 % |
| 2022-06-10 → 06-20 (Luna/3AC) | −0.3 % | −3.5 % | −3.0 % | −2.6 % |
| 2022-11-06 → 11-15 (FTX) | −1.5 % | −6.5 % | −4.8 % | −5.1 % |

At the 0.44 scale, the 30-day covid loss is about −4.4 %, about two years of the overlay's average.

**Findings.**

- **Tenor.**
  - 30-day and 14-day straddles keep the premium.
  - Weeklies don't: their premium per year is the largest (about 310 % of notional collected), but so are the
    option costs (10.4 %/yr) and the hedging turnover.
  - Closing a day early doubles the option costs, gives up the cheapest part of the decay, and is clearly worse.
- **Hedge band.**
  - A wider band is better throughout: 10 % > 5 % > 2 %. Gamma hedging at 4 bps is expensive. At a 2 % band the
    unscaled 30-day run pays 5.6 % of capital a year in perpetual costs, about USD 140M traded per USD 1M. At
    10 % it pays 2.9 %.
  - The residual delta at a 10 % band is the price paid. Daily correlation with BTC stays about 0, but intraday
    exposure reaches ±10 % of capital.
- **The vol filter did not help.** Selling only when IV exceeded trailing RV by 5 or 10 points skipped the calm
  months that pay, and still caught the crashes.
- **Margin.** The 30-day straddle at 1× notional needs about 1.1–1.2× equity at peak under standard margin, hence
  the 0.44 scale. Portfolio margin would need less, but this backtest does not model it.

## C2: IV calendar (short 10 d / long 45 d ATM straddle, vega-matched)

| Variant | Scale | Overlay | Vol | Max DD | Years < 0 |
|---|---|---|---|---|---|
| band 5 % | 0.42 | −8.3 % | 5.0 % | −44 % | 6 / 7 |
| band 10 % | 0.66 | −8.5 % | 7.4 % | −47 % | 6 / 7 |

- **Cost.** Re-striking both straddles every week costs about 19 % of capital a year in option costs (1× notional).
- **No term-structure premium to offset it.** It gained only in 2021 and lost 9–18 %/yr from 2023 on.
- **Kill:** its Sharpe is below C1's and its drawdowns are larger. A monthly roll of the back leg would cut costs
  but cannot fix a negative gross.

## C3: skew carry (30 d)

| Variant | Scale | Overlay | Vol | Max DD | Worst week | Years < 0 |
|---|---|---|---|---|---|---|
| sell 25-delta risk reversal (short put, long call), band 5 % | 0.80 | −4.8 % | 4.8 % | −30 % | −5.9 % | 6 / 7 |
| same, band 10 % | 0.78 | −5.3 % | 5.5 % | −33 % | −6.4 % | 7 / 7 |
| sell 25-delta wings vs ATM straddle (butterfly), band 5 % | 0.47 | −2.0 % | 2.0 % | −13.5 % | −1.4 % | 6 / 7 |
| same, band 10 % | 0.47 | −1.7 % | 2.2 % | −12.2 % | −2.0 % | 6 / 7 |

- **The risk reversal has no persistent premium.** BTC skew flips sign: calls were bid in the 2020–21 and 2024
  rallies. Selling puts against calls buys the rich wing then, and it lost −13 % to −15 % in 2020 alone (the covid
  crash).
- **The wings are not overpriced** relative to ATM after costs.
- **Kill:** the average P&L is negative, so the "worst week vs one year of P&L" test is moot. Not low-risk, and no
  premium.

## Caveats

- **Hourly snapshots.** Hedging and fills are hourly, there are no intra-hour paths, and option fills are at the
  chain's hourly mid ± cost.
- **Fills avoid known-bad snapshots.**
  - Entries skip the 08:00 settlement snapshot and any snapshot whose index disagrees with the perpetual feed by
    more than 0.2 %.
  - Settlement uses the hourly index at expiry, not Deribit's 30-minute TWAP.
- **Margin** is a simplified standard-margin formula. Portfolio margin, liquidation and funding of margin are not
  modelled. The 50 %-margin scaling is the safeguard.
- **Option values** are marked at Deribit's mark price. Daily vol therefore includes mark noise, but realised P&L
  is at fills and settlement.
