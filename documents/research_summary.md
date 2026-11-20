# Research summary: low-risk yield on Deribit BTC inverse instruments

This is a one-page account of the study: what we asked, how we tested it, what failed and what is left. The numbers
are in [results_summary.md](results_summary.md), and the detail is in results_A, results_B and results_C.

## 1. Seed questions

The brief asked: **which yield-like strategies can run on Deribit's BTC inverse instruments (options, dated futures
and the perpetual) with little or no market risk?** The starting candidates were:

- box spreads;
- funding arbitrage (perpetual funding);
- futures carry: dated futures against spot or the perpetual, or against synthetic forwards built from options;
- calendar spreads and implied-volatility carry;
- anything else along the same lines.

These became four questions:

1. **Delta-one carry.** How much do the futures basis and perpetual funding pay once price risk is hedged, and
   can switching between them add anything?
2. **Option parity.** Do options ever price a forward or a locked rate different enough from the futures to trade
   (conversions, reversals, boxes, jelly rolls, static no-arbitrage violations)?
3. **Option risk premia.** Is there a volatility premium (short straddles), a term-structure premium (IV
   calendars) or a skew premium worth collecting once delta is hedged?
4. **Synthesis.** Which ones combine into a portfolio, and what is the realistic yield?

## 2. How it was tested

- **Data:** hourly snapshots from shared-data. The option chain covers Dec 2019 → Oct 2026. Futures and perpetual
  data start in May 2019.
- **Accounting in USD.** Capital is held as BTC, hedged to a synthetic dollar. Strategies that lock a BTC amount
  carry an extra short inverse future, so the result is fixed in USD.
- **Costs:**
  - options: mid price ± 0.001 BTC per contract (10 bps of the underlying);
  - futures and perpetual: 4 bps of notional.
- **One engine for every idea:** inverse payoffs, a portfolio, a delta hedger with a band, simplified standard
  margin, and metrics. Unit tests check the payoff identities (carry, box and conversion locks).
- **Kill criteria were written before each test** ([03_test_designs.md](03_test_designs.md)).
- **Data artefacts were treated as a risk to the result, not just noise.** Any edge also had to survive a
  one-hour-delayed fill.

## 3. What was found useless

| Idea | Why it failed |
|---|---|
| **Box spreads (B2), conversions and reversals (B1), jelly rolls (B3)** | Option-implied forwards match the futures within 1–3 bps (median). After costs, the upper bound is ≤ 0.3 %/yr. Only 15 box episodes survived the one-hour delay in 7 years. A box only earns the futures basis, at higher cost. |
| **Static no-arbitrage scan (B4)** (monotonicity, verticals, butterflies) | Apparent violations were stale or out-of-sync snapshots. They vanish within an hour. |
| **Switching between perp and futures, best-carry roll (A2-switch, A5)** | It looks like 8.3–8.8 %/yr on hourly marks. The gross edge is 18.5 % on marks but only 3.1 % at traded prices, so it was harvesting mark noise. |
| **Funding-vs-basis prediction (A3)** | Out-of-sample R² is about 0.001. Funding cannot be forecast from the basis well enough to trade. |
| **Futures calendar spread (A4)** | −0.6 %/yr compared with plain funding carry. |
| **Weekly short straddles (C1 7 d)** | Option costs of about 10 %/yr eat the whole premium. Closing a day early is worse still. |
| **IV calendar (C2)** | About −8 %/yr. Re-striking two straddles costs about 19 %/yr, and there is no term-structure premium to pay for it. |
| **Skew carry (C3)** | The risk reversal loses in 6–7 of 7 years: BTC skew flips sign in rallies. The short-wing butterfly also loses. |
| **Vol filter on straddles (IV − RV threshold)** | It skipped the calm months that pay and still caught the crashes. |

**Data lessons.** Several "arbitrages" were data artefacts:

- stale snapshots on 12–20 January 2024;
- the 2024-11-11 04:00 snapshot;
- every 08:00 snapshot in 2026;
- garbage quotes with asks of several BTC;
- linear BTC_USDC options mixed into the chain from Oct 2026.

Any future work on this chain must filter these.

## 4. What works

1. **Perpetual funding carry (A2): the core.** Hold BTC and short the perpetual.
   - **7.3 %/yr**, vol 1.4 %, max drawdown −4 %, with costs near zero.
   - Its risk is funding staying negative: 2022 returned −2.2 %.
2. **Cash-and-carry with dated futures (A1): a lock.**
   - **6.2–6.3 %/yr.** The rate is known at entry.
   - It has 4 % mark-to-market vol but converges at expiry. Its correlation with A2 is about 0.15.
   - **50/50 with A2:** 6.9 %/yr, and the worst year improves from −2.2 % to −0.9 %.
3. **30-day delta-hedged short straddle (C1): a risk premium, not a yield.**
   - Sized to 50 % margin, it adds **+2.2 %/yr**.
   - It has crash weeks of −4 % to −6 %. The premium was earned in 2020–22 and has been about flat since.
   - Keep it in a separate risk bucket.

**Main caveat.** Every carry source peaked in 2021 and has fallen since. In 2025–26 the low-risk yield is about
2–6 %/yr, close to a USD money-market rate.

## 5. What could still work (untested)

None of these were backtested. They are where a next round would look.

- **Rules for when to use A1 vs A2.** Lock with dated futures only when the annualised basis is well above recent
  funding. A3 shows funding can't be forecast, but a simple threshold on the level is untested.
- **Finer data for parity trades.** At hourly resolution there is no edge. Tick or minute data with real order-book
  depth could show short-lived box or conversion edges that a fast maker could capture.
- **Lower execution cost.** Every option idea is cost-bound. Maker fills or block trades below 10 bps per leg
  would change C1 and might revive C2 at longer rolls. Re-running at 5 bps and 2 bps is cheap.
- **Crash-capped straddle.** C1 with long far-OTM wings (an iron fly) to cut the March 2020-style loss. It would
  reduce the premium, so the question is whether it still beats costs.
- **Portfolio margin.** It would raise the scale C1 can run at, and it changes the capital efficiency of A1 and A2.
- **Expiry convergence (A6).** Skipped as low priority, because the expected edge is below cost.
- **Risks not modelled.** Exchange and counterparty risk, liquidation, intra-hour execution, and futures bid/ask.
  These bound how far any of the numbers above can be trusted.
