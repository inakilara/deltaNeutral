# Results B: option-parity trades (B1–B5)

Phase 3, run 2026-11-19 on the full option chain (2019-11-25 → 2026-10-25, inverse `BTC-…` options only).
Code: `scripts/run_phase3_scan.py` (scan) and `scripts/run_phase3_report.py` (tables). Outputs: `reports/phase3/`.

## Verdict

**There is no tradable parity edge at hourly resolution.**

- Under the cost assumption, every option-parity structure on Deribit (conversion, reversal, box, jelly roll,
  static vertical/butterfly arbitrage) is positive in well under 1 % of observations.
- The few positive cases almost never survive a one-hour delay.
- Nearly all the large "edges" are data artefacts: stale or out-of-sync snapshots.
- Option-implied forwards match the futures prices to about 1–3 bps. So a box or synthetic forward locks the same
  USD rate as the futures basis (A1), and offers nothing beyond it.

| Idea | Kill criterion (`03_test_designs.md`) | Result | Status |
|---|---|---|---|
| B5 implied forward | measurement | median abs(deviation) 1–3 bps on listed expiries (2022–26) | options = futures |
| B1 conversion / reversal | edge ≤ 0 in > 90 % of cases after 1 h delay | positive in 0.03–0.4 % of cases, rarely survives 1 h | **killed** |
| B2 box | beats A1 in < 1 % of hours | positive in 0.01–0.3 % of expiry-hours; 15 episodes in 7 years survive 1 h | **killed** |
| B3 jelly roll | run only if B5 shows tenor-dependent deviations | B5 shows none; the structure is two B1 trades | **killed** |
| B4 static arbitrage | violations in < 0.1 % of hours | 0–2 % of hours, median 1 tick (5–10 bps), no size | **killed** |

## Method

Every structure is built from one quantity. For each hour, expiry and strike where the call and the put both have
two-sided quotes, the parity deviation is:

    d = (C_mid − P_mid) − (1 − K/F)        BTC per 1 BTC underlying (× 10⁴ = bps of underlying)

F is the chain's `underlyingPrice`: the future's mark for expiries with a listed future, and Deribit's synthetic
forward otherwise. Deribit's marks satisfy d = 0 by construction; bid/ask mids do not.

Edges after costs, in BTC per contract. Each one locks USD at expiry once hedged (USD edge = edge × F):

| Structure | Legs | Edge, mid ± 0.001 per option leg, futures ± 4 bps |
|---|---|---|
| Conversion | long C, short P, short future N = F | −d − 0.0024 |
| Reversal | short C, long P, long future | d − 0.0024 |
| Box (long or short) | four options at K₁ ≠ K₂, no future | d(Kᵢ) − d(Kⱼ) − 0.004 |
| Jelly roll | conversion at T₁ + reversal at T₂ | (d₂ − d₁) − 0.0048 |

- **Two pricing variants.**
  - *mid*: mid ± 0.001 BTC, the study assumption. It is used only for legs whose quoted spread is ≤ 0.005 BTC;
    wider quotes have meaningless mids.
  - *quoted*: the real bid/ask with no extra option cost, futures still ± 4 bps.
- **One-hour survival.** The same structure, at the same strikes, re-priced at the next hour's quotes.
- **Scope.**
  - B1 uses only expiries with a listed future (the future leg must exist) and strikes within ± 20 % of F.
  - B2 uses all expiries, strikes within ± 25 %.
  - B5 uses strikes within ± 10 %, median per expiry-hour.
  - Instruments with less than 1 day to expiry are excluded.

## B5: implied forward vs futures

Median absolute deviation of the option-implied forward from F (bps), on expiries with a listed future:

| Tenor | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|---|---|
| 1–7 d | 2.3 | 2.4 | 2.6 | 1.8 | 1.6 | 1.3 | 1.1 | 1.3 |
| 7–30 d | 2.6 | 2.6 | 2.9 | 2.2 | 1.6 | 1.4 | 1.1 | 1.1 |
| 30–90 d | 3.1 | 3.2 | 3.6 | 2.4 | 1.9 | 1.6 | 1.3 | 1.3 |
| 90 d+ | 4.0 | 4.5 | 4.2 | 3.4 | 2.8 | 2.9 | 2.1 | 1.8 |

- **Small and centred.** The signed median is within ± 1.4 bps in every listed-future cell. The 90th percentile is
  3–13 bps.
- **Tighter over time**, as the market deepened.
- **Persistent.** The hour-to-hour autocorrelation is 0.73. The deviations are slow-moving quote skew, not
  fleeting mispricing.
- **The cost bar is far above this.** Converting at mid ± 0.001 needs |d| > 24 bps.
- **Expiries without a listed future**, where F is Deribit's synthetic forward: deviations were larger in 2020–21
  (median 4–12 bps, 90th percentile up to 64 bps). Since 2022 they are the same as for listed expiries.
- **As a rate.** The implied USD rate equals the futures basis rate to within about 1–15 bps a year beyond 7 days.
  Under 7 days, tiny price gaps annualise into large numbers, which mean nothing.
- **Tenor.** No tenor-dependent pattern beyond the noise growing with tenor. B3 therefore has nothing to exploit.

## B1: conversion / reversal

*Quoted* bid/ask, listed-future expiries:

| Year | Expiry-hours | Positive | Hours with any | Median edge (bps) | Survive 1 h | Episodes | Median size (BTC) | Upper bound, entry | Upper bound, 1 h delay |
|---|---|---|---|---|---|---|---|---|---|
| 2019 | 1,917 | 0.73 % | 1.6 % | 9.5 | 21 % | 9 | n/a | n/a | n/a |
| 2020 | 24,088 | 0.32 % | 0.9 % | 3.1 | 3 % | 74 | n/a | n/a | n/a |
| 2021 | 51,382 | 0.42 % | 2.1 % | 7.1 | 9 % | 169 | 0 | 0.84 % | 0.07 % |
| 2022 | 59,023 | 0.05 % | 0.3 % | 2.8 | 0 % | 30 | 1.9 | 0.12 % | 0.00 % |
| 2023 | 58,775 | 0.12 % | 0.6 % | 16.2 | 44 % | 39 | 3.9 | 1.58 % | 0.31 % |
| 2024 | 58,896 | 0.35 % | 1.0 % | 39.7 | 58 % | 81 | 2.5 | 42.4 %* | 4.86 %* |
| 2025 | 59,075 | 0.03 % | 0.1 % | 1.3 | 40 % | 9 | 0.7 | 0.01 % | 0.01 % |
| 2026 | 64,125 | 0.14 % | 0.7 % | 84.7 | 0 % | 90 | 6.1 | 88.4 %* | 0.00 % |

**How the upper bound is built.** It is the USD edge per year as a share of USD 1M. Every episode is traded once,
at its full quoted size: at the entry quotes, or at the next hour's quotes when still positive. It ignores margin
and execution risk, and assumes perfect hindsight about which snapshot to trust.

\* **The 2024 and 2026 numbers are data artefacts.**

- In 2026, 94 % of the episodes are 08:00 snapshots, at daily settlement, where F lags the quotes. They show a
  2–4 % reversal edge on 2027 expiries, and **none** survives to 09:00.
- In 2024, 98 % of the delayed USD edge (USD 47.8k of 48.6k) comes from 12–21 January 2024. In that window the chain
  snapshot is frozen or stale for hours: identical F and identical quotes repeat.
- The remaining large entries are 2024-11-11 04:00, where all expiries jump to a 5–6 % edge at once. F lags a fast
  rally, and the edge is gone by 05:00.

**Excluding the stale window:**

- The 1-hour-delayed upper bound is USD 714 (2021), 3,070 (2023), 788 (2024) and 54 (2025) per year on USD 1M,
  i.e. ≤ 0.3 %/yr.
- That is before margin, and before the risk that the second leg (the future) has no real bid/ask at that price.

*Mid ± 0.001 variant:* positive in 0.07–1.3 % of expiry-hours. The median positive edge is 2–5 bps, apart from the
same artefacts. One-hour survival is 0–48 %.

## B2: box spread

| Year | Quoted: positive | Quoted: hours with any | Quoted: median edge (bps) | Quoted: survive 1 h | Quoted: episodes | Mid: positive | Mid: survive 1 h |
|---|---|---|---|---|---|---|---|
| 2019 | 0.06 % | 0.3 % | 12.0 | 0 % | 2 | 0.12 % | 0 % |
| 2020 | 0.03 % | 0.2 % | 5.6 | 0 % | 19 | 0.07 % | 0 % |
| 2021 | 0.24 % | 1.5 % | 12.3 | 1 % | 146 | 0.28 % | 1 % |
| 2022 | 0.02 % | 0.1 % | 4.1 | 0 % | 15 | 0.02 % | 0 % |
| 2023 | 0.06 % | 0.2 % | 26.9 | 56 % | 24 | 0.05 % | 55 % |
| 2024 | 0.28 % | 0.9 % | 50.1 | 62 % | 87 | 0.25 % | 57 % |
| 2025 | 0.01 % | 0.1 % | 2.9 | 50 % | 6 | 0.00 % | 0 % |
| 2026 | 0.08 % | 0.6 % | 122 | 0 % | 57 | 0.00 % | 0 % |

- **Survivors are artefacts or rare.** Of 356 quoted box episodes, 40 survive one hour. 25 of those are in the
  January 2024 stale window. The remaining **15 episodes in 7 years** have a median edge of 2–28 bps.
- **Width does not change the conclusion.** A wider box spreads the four leg costs over a larger payoff, so it
  lowers the cost as a rate. But the rate gap it would need to capture is the d dispersion across strikes, and
  that dispersion is almost always below the 40 bps of cost.
- **Box rate = futures basis.** The fair box price is (K₂ − K₁)/F, so its USD rate is exactly the futures basis
  rate. It can replace A1 as a USD lock, at 4 × 10 bps of cost instead of 4 bps on one future.

## B3: jelly roll

Not run as a separate scan; the decision follows from B1 and B5.

- **It is two B1 trades.** With its futures legs, a jelly roll is a conversion at T₁ plus a reversal at T₂. Its
  edge (d₂ − d₁) − 0.0048 is positive only where at least one of the two single conversions would already be
  profitable.
- **Without the futures legs** it carries the F₂ − F₁ calendar exposure, which is the A4 trade.
- **B5 found no tenor-dependent deviation** to exploit.

## B4: static no-arbitrage

Checks on adjacent strikes per expiry and option type:

- monotonicity in K;
- vertical bound |price difference| ≤ (K₂ − K₁)/F;
- butterfly ≥ 0.

Share of chain hours with at least one violation after costs:

| Year | Monotonicity, mid | Monotonicity, quoted | Vertical, mid | Vertical, quoted | Butterfly, mid | Butterfly, quoted |
|---|---|---|---|---|---|---|
| 2019 | 0 | 0 | 0 | 0 | 0.11 % | 0 |
| 2020 | 0.05 % | 0.02 % | 0.02 % | 0.01 % | 0.07 % | 0.38 % |
| 2021 | 2.0 % | 1.1 % | 1.9 % | 1.3 % | 2.4 % | 1.9 % |
| 2022 | 0.01 % | 0 | 0 | 0 | 0.09 % | 0.02 % |
| 2023 | 0.09 % | 0.13 % | 0.01 % | 0.10 % | 0.30 % | 0.74 % |
| 2024 | 0.79 % | 0.59 % | 0.22 % | 0.27 % | 1.3 % | 1.2 % |
| 2025 | 0.06 % | 0 | 0 | 0 | 0.08 % | 1.1 % |
| 2026 | 0.54 % | 0.03 % | 0.01 % | 0 | 0.55 % | 0.55 % |

- **Typically one price tick.** The median violation is 5–10 bps (0.0005–0.001 BTC). In 2025–26 the quoted
  butterfly violations are under 1 bp: rounding-level, worth less than the tick.
- **No capacity.** Wing quotes are small, and each structure needs 2–4 legs.
- **The 2021 and 2024 clusters** coincide with the fast-market and stale-snapshot episodes above.
- **Calendar check (4) not run.** On executable prices it needs an interpolated forward-moneyness grid; given (1)–(3)
  it is unlikely to change the verdict.

## What this means for the study

- **Rate locks.** Deribit's option market is priced off its futures. The only USD rate locks available are the
  futures basis (A1) and perpetual funding (A2). Options add no third, independent rate.
- **Collateral.** A box is a costlier way to get the A1 rate. It is worth it only if a venue's margin treatment
  favours it, which this backtest does not model.
- **Where option yield could come from.** Phase 4 tests risk premia instead: C1 short-vol, C2 calendar, C3 skew.
  These carry market risk (gamma/vega) and must be judged on risk-adjusted terms, not as arbitrage.
- **Data lesson.** Any backtest on this chain must require a one-hour-delayed fill, or similar staleness filters.
  Otherwise stale snapshots manufacture 2–6 % "arbitrages".
