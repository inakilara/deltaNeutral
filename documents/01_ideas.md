# 01: Strategy ideas

## Accounting in USD

**Capital, P&L and yields are in USD.** A strategy is market-neutral when its **USD P&L does not depend on the
BTC price**. Deribit's BTC instruments are inverse (margined and settled in BTC), so the account holds BTC, and
every strategy is built so that its USD value is price-independent:

- **Collateral:** USD capital is deposited as BTC at the index (no cost assumed) and hedged with a short
  perpetual (default; or a dated future), giving a **synthetic dollar**: `1 BTC + short N = S_0` is worth
  `S_0` USD at any price. The hedge earns funding (or basis). That **collateral carry** is reported as its own
  line, separate from the strategy's own P&L.
- **Strategies that lock a USD amount** (cash-and-carry, box spread, funding carry) need nothing else.
- **Strategies that lock a BTC amount** `X` at expiry (conversion/reversal, futures vs perpetual) are converted to
  USD with a **short inverse future of the same expiry**, `N = X·F_0`, which turns `X` BTC at `T` into exactly
  `X·F_0` USD. If no future is listed at that expiry, the perpetual is used and re-hedged (small residual).
- **Delta hedger:** the engine keeps the account's total USD delta (collateral, BTC balances, options, futures)
  within a band, using the perpetual. Delta-one and locked strategies leave it idle; it does the hedging for the
  option strategies.

### Inverse payoffs

`S` is the index, `F` a future's price, `K` a strike, `T` the time to expiry in years.

| instrument | P&L in BTC | USD value |
|---|---|---|
| option (1 BTC underlying, price in BTC) | at expiry: call `max(S_T−K,0)/S_T`, put `max(K−S_T,0)/S_T` | × `S_T`: the usual USD payoff |
| long future, notional `N` USD | `N·(1/F_0 − 1/F_T)` | × `S` |
| long perpetual, notional `N` | `N·(1/P_0 − 1/P_t)` − funding paid (`interest_1h · N / S` per hour) | × `S` |

Identities verified by unit tests in phase 1:
- **Cash-and-carry:** 1 BTC plus a short future `N = F_0` ends at `F_0/S_T` BTC, worth exactly `F_0` USD.
- **Box:** long C(K1), short C(K2), short P(K1), long P(K2) pays exactly `K2 − K1` USD (as BTC at `S_T`).
- **Parity (BTC lock):** long call, short put at K plus a short future `N = K` ends at exactly `1 − K/F_0` BTC.
  Plus a short future `N = (1 − K/F_0)·F_0 = F_0 − K` it is exactly `F_0 − K` USD. The two futures legs net to
  one short future `N = F_0`. So, in USD, a conversion = long call + short put + short future `N = F_0`, paying
  `F_0 − K` USD against a premium of `(C − P)·S_0` USD.

## Catalogue

Risk class: **0** = USD P&L locked at entry (only execution, counterparty and margin risk); **1** = carry with
residual funding or basis risk; **2** = price-neutral but exposed to volatility, skew or jumps.

### A. Delta-one carry

| id | idea | mechanics | locks | earns (USD) | residual risk | class |
|---|---|---|---|---|---|---|
| A1 | **Cash-and-carry** | hold BTC, short dated future `N = F_0`, hold to expiry, roll | USD | the basis `ln(F/S)/T`, locked (2–11 %/yr by year) | marking to market before expiry; none at expiry | 0 |
| A2 | **Funding carry** | hold BTC, short perpetual `N = S`, re-hedge daily; variants: always on, or on/off from **trailing** funding | — | funding (−2 to +17 %/yr by year) | negative funding (11–35 % of hours) | 1 |
| A3 | **Funding vs basis** | short perpetual / long future, or the reverse (BTC-locked difference of entry prices, converted to USD by the same-expiry future) | BTC → USD | funding minus basis (or the reverse), chosen from trailing funding | funding over the future's life | 1 |
| A4 | **Futures calendar** | long near / short far, same `N`, roll the near leg | partly | forward basis between expiries | the far leg's basis at the near expiry | 1 |
| A5 | **Best-carry roll** | hold the collateral hedge (A1 future or A2 perpetual) with the best net carry; switch only when the gain beats the costs plus a margin | USD | best available USD carry | switching costs, noise | 0–1 |
| A6 | **Expiry convergence** | last-day future vs index, perpetual-hedged | — | small convergence gaps | settlement TWAP vs our hourly index; mostly 2026 daily futures | 1 (low priority) |

### B. Option parity arbitrage (held to expiry)

| id | idea | mechanics | locks | earns (USD) | residual risk | class |
|---|---|---|---|---|---|---|
| B1 | **Conversion / reversal** | long call, short put at K, short future `N = F_0` (or the reverse) | USD (after the BTC→USD future, see above) | `F_0 − K − (C − P)·S_0` at entry prices, after costs | none if held to expiry; needs a listed future at that expiry | 0 |
| B2 | **Box spread** | long box (lend USD) or short box (borrow USD); compare its implied USD rate `ln((K2−K1)/(B·S_0))/T` with the futures basis of the same expiry. Box + opposite A1 = the arbitrage | USD | the box–basis rate gap, net of 4 option legs | none if held to expiry | 0 |
| B3 | **Jelly roll** | synthetic long T1 / synthetic short T2 vs the futures calendar | USD | forward-rate gap | many legs | 0 |
| B4 | **Static no-arbitrage scan** | violations of monotonicity, vertical bound `(K2−K1)/F` BTC, butterfly ≥ 0, calendar | USD after hedge | the violation | expected rare | 0 |
| B5 | **Implied forward vs futures** | measurement: option-implied forward per expiry vs the future | — | (diagnostic) | — | — |

By parity, a box's rate equals the futures basis. So B1, B2 and B3 all reduce to "options' implied forward vs
the future". **B5 is measured first** and tells how much room there is before any trade is simulated.

### C. Volatility carry (USD-delta-neutral via the engine's hedger; "IV carry")

| id | idea | mechanics | earns (USD) | residual risk | class |
|---|---|---|---|---|---|
| C1 | **Delta-hedged short straddle** | sell ATM straddle (7–30 d); the hedger keeps USD delta ~0 with the perpetual | variance risk premium | jumps, volatility spikes, vega | 2 |
| C2 | **IV calendar / term carry** | short front ATM / long back ATM, vega-matched | front premium plus roll-down | term inversions in sell-offs | 2 |
| C3 | **Skew carry** | sell 25-delta risk reversal (or 25-delta butterfly) | rich skew or wings | crash tails | 2 |

### Considered and excluded

- **Covered calls and cash-secured puts:** directional.
- **Naked short wings:** directional tail risk.
- **USDC-margined linear instruments:** outside the brief (inverse only).
- **Liquidation, settlement-auction and order-book games:** not observable in hourly snapshots.

## Expectations to test

- A1 is the robust baseline: a positive locked USD yield every year at 8 bps per round trip.
- A2 has the highest average but loses in bearish regimes (2022). A5 should get close to the better of A1 and A2.
- B1/B2 are probably killed by option costs (2–4 legs × 10 bps of the underlying), except at long tenors or in
  dislocations.
- C1–C3 probably earn more but are not low-risk. They are reported with their tails, separate from classes 0–1.

## Priority

1. A1, A2, A5 (futures and funding only; A1 also sets the collateral carry every other strategy is measured
   against)
2. B5 → B1, B2
3. A3, A4, B3, B4
4. C1, C2, then C3
5. A6
