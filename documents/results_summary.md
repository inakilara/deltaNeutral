# Results summary and recommendation

Phase 5, run 2026-11-20.

- **Basis:** results_A (delta-one carry), results_B (option parity) and results_C (option risk premia).
- **Comparison window:** 2020-01-01 → 2026-10-25, the window where options and futures overlap.
- **Code:** `scripts/run_phase5.py`. **Outputs:** `reports/phase5/`.
- **All figures:** USD returns on USD capital, net of costs (options mid ± 0.001 BTC, futures and perpetual 4 bps).

## Recommendation

1. **Core: the perpetual funding carry (A2).** Hold BTC, short an equal USD notional of BTC-PERPETUAL, collect
   funding.
   - It has the best risk-adjusted yield found: **7.3 %/yr, vol 1.4 %, Sharpe 5.2, max drawdown −4.0 %**, with no
     price exposure.
   - Its risk is funding turning negative for long periods (2022: −2.2 %). Funding has also trended down
     (2.4 % a year so far in 2026).
2. **Optional: lock part of the yield with the cash-and-carry (A1).** Use a short dated future, re-locked about
   monthly.
   - It is lower (6.3 %/yr) and shows 4 % mark-to-market vol, but the rate is known at entry and converges at
     expiry.
   - Its daily P&L has a correlation of only 0.16 with A2.
   - A 50/50 split cut the worst year from −2.2 % to −0.9 % and the worst week from −2.3 % to −0.8 %, for
     −0.5 %/yr of return.
   - Use it when the basis exceeds expected funding, or when a known rate is worth more than the extra 0.5–1 %.
3. **Not low-risk, but the only positive option premium: the 30-day delta-hedged short straddle (C1).** Run it as an
   overlay sized to at most 50 % margin, about 0.44× capital notional.
   - It added +2.2 %/yr, with 4 % vol and crash weeks of −4 % to −6 %.
   - The premium was earned in 2020–22 and has been about flat since 2023.
   - It belongs in a separate risk bucket, not in the "low-risk yield".
4. **Do not run:**
   - option-parity arbitrage (B1–B4): no edge after costs at hourly resolution;
   - switching between perpetual and futures (A2-switch, A5): its edge is not robust to price noise;
   - funding-vs-basis bets (A3), the futures calendar (A4), the IV calendar (C2) and skew trades (C3).

## Comparison table

| Strategy | Risk class | Return | Median year | Worst year | Vol | Max DD | Worst week | Costs/yr | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| A2 perpetual funding carry | 0–1 | **7.3 %** | 7.0 % | −2.2 % | 1.4 % | −4.0 % | −2.3 % | 0.01 % | **core** |
| A1 30 d cash-and-carry | 0 | 6.3 % | 4.6 % | +0.5 % | 4.1 % | −6.8 % | −1.4 % | 0.5 % | optional lock |
| A1 quarterly cash-and-carry | 0 | 6.2 % | 4.6 % | +1.6 % | 4.6 % | −6.8 % | −2.9 % | 0.2 % | optional lock |
| 50 % A2 + 50 % A1 30 d | 0–1 | 6.9 % | 5.7 % | −0.9 % | 2.3 % | −4.4 % | −0.8 % | 0.3 % | balanced |
| A2-switch / A5 best carry (m 25 bp) | 1 | 8.3–8.8 %* | | −0.4 to +0.1 %* | 4.6–5.0 % | −5.6 to −6.9 % | −3 % | 2–4 % | not robust |
| A3 funding vs basis (overlay) | 1 | −0.7 to +0.2 % over A2* | | | | | | | killed |
| A4 futures calendar (overlay) | 1 | −0.6 % over A2* | | | | | | | killed |
| B1–B4 option parity | 0 | ≤ 0.3 %/yr upper bound | | | | | | | killed |
| C1 30 d short straddle overlay (50 % margin) | 2 | +2.2 % over A2 | +2.0 % | −1.5 % | 4.1 % | −8.0 % | −4.1 % | about 2.3 % | risk bucket |
| A2 + C1 overlay | 2 | 9.6 % | 5.6 % | +0.6 % | 4.3 % | −8.0 % | −6.3 % | | |
| C2 IV calendar overlay | 2 | −8.3 % | | | | | | about 13 % | killed |
| C3 skew (risk reversal / butterfly) overlay | 2 | −4.8 % / −2.0 % | | | | | | | killed |

\* Phase-2 window 2019-05 → 2026-11, where it differs from the 2020–26 comparison window.

Risk classes, from `01_ideas.md`:

- **0:** locked USD, no market risk.
- **1:** USD carry with rate or basis risk, no price exposure.
- **2:** option premia with gamma, vega and crash risk.

## Year by year (%)

| Portfolio | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 (to Oct) |
|---|---|---|---|---|---|---|---|
| A2 perpetual carry | 9.9 | 18.1 | −2.2 | 7.0 | 10.9 | 5.5 | 1.9 |
| A1 30 d cash-and-carry | 4.6 | 14.5 | 0.5 | 3.8 | 12.9 | 5.8 | 1.9 |
| 50 % A2 + 50 % A1 30 d | 7.3 | 16.3 | −0.9 | 5.4 | 11.9 | 5.6 | 1.9 |
| A2 + C1 overlay | 12.0 | 28.7 | 0.6 | 5.4 | 13.1 | 5.6 | 2.5 |
| 50/50 A2/A1 + C1 overlay | 9.4 | 26.8 | 2.0 | 3.8 | 14.1 | 5.7 | 2.5 |

**Yields are falling.** Every carry source peaked in 2021 and has fallen since: perpetual funding, the futures basis
and the option premium. In 2025–26 the best low-risk yield is about 2–6 %/yr, close to a USD money-market rate.
This is the key forward-looking caveat.

## Correlation of daily USD P&L (2020–2026)

| | A2 | A1 quarterly | A1 30 d | C1 overlay |
|---|---|---|---|---|
| A2 | 1 | 0.12 | 0.16 | −0.02 |
| A1 quarterly | 0.12 | 1 | 0.90 | −0.05 |
| A1 30 d | 0.16 | 0.90 | 1 | −0.05 |
| C1 overlay | −0.02 | −0.05 | −0.05 | 1 |

The three return sources are close to independent day to day:

- funding (A2);
- basis mark-to-market (A1);
- short gamma and vega (C1).

They are not independent in crashes. In March 2020 all three lost together: A2 −2.6 %, and C1 −12.6 % unscaled.

## Capacity and costs

- **A2 and A1** trade a few times a year in the most liquid Deribit instruments. Costs are under 0.5 %/yr, and
  capacity is large: the limits are exchange exposure and the futures' depth at roll.
- **C1** needs about 0.44 × capital of ATM option notional per month, plus continuous perpetual hedging.
  - Option costs plus hedge costs are about 2.3 %/yr at the 0.44 scale.
  - Top-of-book sizes (median a few BTC, results_B) limit a single fill. Larger capital would need to work orders
    over hours, which this backtest does not model.

## Risks this backtest does not capture

- **Exchange and counterparty risk** on Deribit. All capital sits on one venue.
- **Margin and liquidation mechanics.** Simplified standard margin; no liquidation engine, no portfolio margin.
- **Execution.** Futures have no bid/ask in the data. Fills are at hourly marks plus 4 bps, and intra-hour paths
  are missing.
- **Data quality.** Stale and out-of-sync chain snapshots exist (04_data_notes). They are filtered or avoided, but
  not perfectly.

## How each idea was tested

| Idea | Result document | Status |
|---|---|---|
| A1 cash-and-carry | results_A | kept (optional lock) |
| A2 funding carry | results_A | **kept (core)** |
| A3 funding vs basis | results_A | killed (no out-of-sample forecast) |
| A4 futures calendar | results_A | killed |
| A5 best-carry roll | results_A | not robust (noise harvesting) |
| A6 expiry convergence | results_A | not run (low priority, < cost) |
| B1 conversion / reversal | results_B | killed |
| B2 box | results_B | killed (= futures basis at higher cost) |
| B3 jelly roll | results_B | killed (two B1 trades) |
| B4 static no-arbitrage | results_B | killed |
| B5 implied forward | results_B | measured: options = futures within 1–3 bps |
| C1 short straddle | results_C | kept as risk-bucket overlay (30 d) |
| C2 IV calendar | results_C | killed |
| C3 skew carry | results_C | killed |
