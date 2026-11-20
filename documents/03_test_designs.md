# 03: Test design per idea

Common to all tests (see 02_backtest_framework.md):
- **USD accounting:** capital, P&L and yields in USD. The account holds BTC, hedged to a synthetic dollar by the
  engine's delta hedger (perpetual, band 1 % of capital).
- Each result splits **strategy P&L** from **collateral carry** (the hedger's funding, basis and costs).
- Costs: mid + 10 bps of the underlying price (0.001 BTC per contract) per option leg; 4 bps of notional per
  futures or perpetual trade.
- Capital: 1×, fully funded.
- Windows: options from 2019-11-25 to 2026-10-25; futures and funding from 2019-04-30 to 2026-11-19.
- Results are reported by calendar year and over the full sample.
- Sensitivities on every test: option cost 0/5/10/20 bps, far-side fills, one-hour delay, hedge band,
  leverage 2×/3×/5×.
- Kill criteria are stated before running, so a negative result is a result.
- Every test reports the account's USD delta over time, which must stay ~0.

---

## A1: Cash-and-carry

- **Hypothesis:** the locked basis is positive in every year and pays a USD yield well above 8 bps per round trip.
- **Construction:** hold BTC worth the capital and short the chosen future with `N = F_0` per BTC. Hold to
  expiry; at settlement re-enter the next future. The hedger is switched off; the future *is* the hedge.
- **Variants:**
  - tenor: nearest quarterly, nearest monthly, or the future closest to 30 / 90 / 180 days;
  - entry: at each roll only.
- **Measure:** locked annualised basis at entry net of costs vs realised USD yield (must match at expiry);
  mark-to-market drawdown before expiry; yield by year.
- **Sensitivity:** synchronous `underlyingPrice` vs candle close as `F`; skip hours without trades.
- **Kill:** none; A1 is the baseline.

## A2: Funding carry

- **Hypothesis:** shorting the perpetual against BTC earns funding above A1 on average, with worse years (2022).
- **Construction:** this is the engine's default collateral (BTC plus a short perpetual, re-hedged on the band).
  The strategy line is empty and all P&L is collateral carry.
- **Variants:**
  - always on;
  - **switching:** hold the perpetual short while trailing 7 d (or 30 d) funding is above a threshold (0, the A1
    basis, or the A1 basis + switching costs); otherwise hold A1 (the future). Only past funding is used.
- **Measure:** USD yield, time on each leg, funding received vs costs, max drawdown from negative funding runs.
- **Kill:** switching must beat both always-on and A1 after costs in at least 4 of 7 years; otherwise only the
  better of the two is kept.

## A3: Funding vs basis

- **Hypothesis:** when the locked basis of a future differs from expected funding over its life, the
  future/perpetual pair earns the difference.
- **Construction:** short future `N` / long perpetual `N` (earn the basis, pay funding) or the reverse.
  - The pair locks `N(1/F_0 − 1/P_0)` BTC at expiry. That BTC amount is converted to USD with a short future of
    the same expiry, `N_x = X·F_0`; the hedger handles the BTC balance otherwise.
  - Signal: `basis_ann − trailing funding_ann` (7 d, 30 d) beyond 2, 4 or 6 %/yr. Hold to expiry, or close when
    the signal reverses by more than the exit cost.
- **Measure:** realised P&L = (basis − realised funding) × time − costs; hit rate; forecast quality (realised
  funding over the future's life regressed on trailing funding: slope and R², fit 2019–2022, test 2023–2026).
- **Kill:** R² < 0.1 out of sample means no forecasting edge; report the unconditional spread only.

## A4: Futures calendar

- **Construction:** long near / short far future, same `N`. At the near expiry the long settles. Close the far
  leg or roll a new near leg into it.
- **Measure:** forward basis at entry vs realised; P&L volatility from the far leg's basis at the near expiry;
  costs (4 legs per cycle).
- **Kill:** if the far-leg residual flips the sign of P&L in > 40 % of cycles, report it as not low-risk.

## A5: Best-carry roll

- **Construction:** for the collateral hedge, hold whichever of {each future via A1, the perpetual via A2 at
  trailing funding} has the best net carry. Switch only when the gain over the remaining life beats the switching
  cost plus a margin of 0, 1 or 2 %/yr.
- **Measure:** USD yield vs A1-quarterly and A2-always-on; switches; cost share.
- **Kill:** if it does not beat the better of A1 and A2 by more than its extra costs, keep the simpler one. The
  winner becomes the default collateral for the B and C tests (with A2 also reported).

## A6: Expiry convergence (low priority)

- In the last 24 h before expiry, enter future vs perpetual when `|F/S − 1|` exceeds costs plus a margin, and
  hold to settlement.
- **Measure:** frequency and size (mostly 2026 daily futures).

---

## B5: Implied forward vs futures (measurement, run first in phase 3)

- For each hour and expiry, the implied forward is `F_impl = K / (1 − (C − P))` from mid prices of two-sided
  call/put pairs within ±10 % of ATM; the median is used.
- Compare with the future's synchronous `underlyingPrice` (where a future is listed), in bps; also as an implied
  USD rate vs the basis.
- Output: deviation by tenor and year, and persistence. This sets expectations for B1–B3 before any trade is
  simulated.

## B1: Conversion / reversal

- **Construction:** for every expiry with a listed future, each hour, and each strike within ±20 % of the forward
  with two-sided quotes:
  - **conversion:** long call, short put at K, short future `N = F_0` per contract (which includes the BTC→USD
    conversion of the locked BTC); locked USD edge = `F_fill − K − (C_fill − P_fill)·S` at entry;
  - **reversal:** the mirror trade;
  - option fills at mid ± 0.001 BTC, future at `F(1 ∓ 4 bps)`; held to expiry.
- **Measure (opportunity study):**
  - share of hours with edge > 0;
  - edge in USD per contract and as an annualised USD yield on the margin used;
  - size available at the quote;
  - persistence;
  - one-hour-delay survival.
- **Portfolio:** best opportunity each hour above a minimum edge (0, 5 or 10 bps of the underlying), subject to
  capital; annual USD yield.
- **Kill:** if the edge is ≤ 0 in > 90 % of cases after a one-hour delay, B1 is not tradable at hourly resolution.

## B2: Box spread

- **Construction:** for each expiry with a listed future and each strike pair (K1 < K2 within ±25 % of the
  forward, four two-sided legs):
  - long box price `B` (BTC) = sum of the four fills (mid ± 0.001 each);
  - box USD rate = `ln((K2 − K1)/(B·S))/T`, compared with the basis rate `ln(F/S)/T` of the same expiry.
  - **Lend:** long box when its rate > basis + margin. It replaces A1 as the USD lock; the BTC paid out comes from
    the collateral.
  - **Borrow:** short box plus A1 on the proceeds when the box rate < basis − margin.
  - Held to expiry.
- **Measure:** rate gap by width and tenor (wider boxes spread the 4 × 10 bps over more payoff); frequency, size,
  persistence; yield vs A1.
- **Kill:** if no width or tenor beats A1 net of costs in more than 1 % of hours, report "box = futures basis, no
  edge".

## B3: Jelly roll

- **Construction:** synthetic long at T1 / synthetic short at T2 at the same strike, with their futures legs.
  Compare the options' forward rate between T1 and T2 with the futures calendar.
- **Measure:** as B1. Run only if B5 shows tenor-dependent deviations.

## B4: Static no-arbitrage scan

- **Checks per hour and expiry, on executable prices** (mid ± 0.001 BTC):
  1. monotonicity in K;
  2. vertical `C(K1) − C(K2) ≤ (K2 − K1)/F` (BTC), and the same for puts;
  3. butterfly ≥ 0;
  4. calendar in forward moneyness.

  Each violation is traded as its static structure, hedged to USD by the hedger and held to expiry.
- **Measure:** count, size, persistence; clustering in wings or near expiry.
- **Kill:** violations after costs in < 0.1 % of hours → "no static arbitrage".

---

## C1: Delta-hedged short straddle

- **Construction:** sell ATM straddle (expiry closest to 7, 14 or 30 d), sized so the short-option margin is
  ≤ 50 % of capital. The hedger keeps the account's USD delta within the band (hourly check; band 1 %, 2 %,
  5 % of capital). Hold to expiry, or close 1 day before.
- **Measure:**
  - USD P&L split into premium decay, gamma, vega, hedge funding and costs;
  - yield, volatility, Sharpe, skew, max drawdown, worst week;
  - behaviour in the 2020-03, 2021-05, 2022-06 and 2022-11 crashes.
- **Variant:** a vol filter (sell only when 30 d IV − trailing 30 d RV > 0, 5 or 10 vol points).
- **Kill:** none (risk class 2). Reported separately, with its tails.

## C2: IV calendar

- **Construction:** short front ATM straddle (7–14 d), long back ATM straddle (30–60 d), vega-matched, hedged by
  the hedger. Roll the front at expiry.
- **Measure:** as C1, plus P&L from term-structure moves.
- **Kill:** if Sharpe is below C1 and drawdowns are not smaller, drop it.

## C3: Skew carry

- **Construction:** sell the 25-delta risk reversal (or the 25-delta butterfly), 30 d, held to expiry, hedged by
  the hedger.
- **Measure:** as C1, with attention to crash weeks.
- **Kill:** if the worst week exceeds a year of average P&L, label it "not low-risk" and stop.

---

## Synthesis (phase 5)

One table, one row per strategy and variant:
- USD yield (median year, worst year), split strategy vs collateral carry;
- volatility and max drawdown;
- cost share and capacity;
- risk class.

Plus the correlation matrix of daily USD P&L, a combined portfolio (class 0–1 only, then with C1), and a
recommendation.
