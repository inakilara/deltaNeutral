"""Phase 2: delta-one carry (A1, A2, A5 as collateral policies; A3, A4 as overlays on the A2 collateral).

    python scripts/run_phase2.py            # all runs -> reports/phase2/
"""
import json
import os
import sys
import time
import warnings

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from dn import engine, metrics  # noqa: E402
from dn.hedger import BestCarryPolicy, FuturePolicy, PerpPolicy, future_candidates, select_future  # noqa: E402
from strategies.delta_one import Calendar, FundingBasis  # noqa: E402

warnings.filterwarnings("ignore")
OUT = os.path.join(ROOT, "reports", "phase2")
CAP = 1e6
START, END = "2019-05-01", "2026-11-19"


def runs(funding):
    q = select_future("quarterly", min_days=7)
    yield "A2 perp (band 0.25%)", dict(policy=PerpPolicy())
    yield "A2 perp (band 0.10%)", dict(policy=PerpPolicy(), band_frac=0.001)
    yield "A2 perp (band 1.00%)", dict(policy=PerpPolicy(), band_frac=0.01)
    yield "A1 nearest quarterly", dict(policy=FuturePolicy(q))
    yield "A1 nearest quarterly (candle closes)", dict(policy=FuturePolicy(q), price_source="close")
    yield "A1 nearest monthly", dict(policy=FuturePolicy(select_future("monthly", min_days=7)))
    for d in (30, 90, 180):
        yield "A1 closest to %dd" % d, dict(policy=FuturePolicy(select_future("any", target_days=d, min_days=7)))
    for lb in (7, 30):
        for m in (0, 25):
            yield "A2 switch perp/quarterly lb=%dd m=%dbp" % (lb, m), dict(
                policy=BestCarryPolicy(funding, future_candidates("quarterly"), lookback_h=24 * lb, margin_bps=m))
    for lb in (7, 30):
        for m in (0, 10, 25):
            yield "A5 best carry lb=%dd m=%dbp" % (lb, m), dict(
                policy=BestCarryPolicy(funding, future_candidates("any"), lookback_h=24 * lb, margin_bps=m))
    yield "A3 short basis / long perp", dict(policy=PerpPolicy(), strategy=FundingBasis(funding, CAP, "short_basis"))
    yield "A3 long basis / short perp", dict(policy=PerpPolicy(), strategy=FundingBasis(funding, CAP, "long_basis"))
    for lb in (7, 30):
        for thr in (0.02, 0.04):
            yield "A3 signal lb=%dd thr=%d%%" % (lb, 100 * thr), dict(
                policy=PerpPolicy(), strategy=FundingBasis(funding, CAP, "signal", threshold=thr, lookback_h=24 * lb))
    yield "A4 calendar near/far quarterly", dict(policy=PerpPolicy(), strategy=Calendar(CAP))


def funding_forecast(perp, fut):
    """A3 forecast check: for every quarterly future, daily at 08:00 while 14-120 d to expiry: realised mean funding
    to expiry vs trailing 7 d / 30 d mean funding and vs the basis."""
    f = perp["funding_1h"].fillna(0.0)
    cum = f.cumsum()
    rows = []
    q = fut[fut["expiry"].map(lambda e: e.month in (3, 6, 9, 12) and e.weekday() == 4 and e.day >= 22)]
    q = q[q["t"].dt.hour == 8]
    S = perp["index"]
    for _, r in q.iterrows():
        t, e = r["t"], r["expiry"]
        days = (e - t).total_seconds() / 86400
        if not 14 <= days <= 120 or t not in cum.index or e not in cum.index:
            continue
        i = cum.index.get_loc(t)
        if i < 720:
            continue
        real = (cum.loc[e] - cum.loc[t]) / (days * 24) * 8766
        tr7 = (cum.iloc[i] - cum.iloc[i - 168]) / 168 * 8766
        tr30 = (cum.iloc[i] - cum.iloc[i - 720]) / 720 * 8766
        basis = np.log(r["price"] / S.loc[t]) / (days / 365.25)
        rows.append((t, r["instrument"], days, real, tr7, tr30, basis))
    d = pd.DataFrame(rows, columns=["t", "future", "days", "realised", "trail7", "trail30", "basis"])
    out = {}
    for split, sub in (("fit 2019-2022", d[d.t.dt.year <= 2022]), ("test 2023-2026", d[d.t.dt.year >= 2023]), ("all", d)):
        for x in ("trail7", "trail30", "basis"):
            b = np.polyfit(sub[x], sub["realised"], 1)
            r2 = np.corrcoef(sub[x], sub["realised"])[0, 1] ** 2
            out["%s | realised ~ %s" % (split, x)] = {"slope": b[0], "r2": r2, "n": len(sub)}
        y = sub["realised"] - sub["basis"]
        xs = sub["trail30"] - sub["basis"]
        out["%s | (realised-basis) ~ (trail30-basis)" % split] = {
            "slope": np.polyfit(xs, y, 1)[0], "r2": np.corrcoef(xs, y)[0, 1] ** 2, "n": len(sub)}
    return d, pd.DataFrame(out).T


def main():
    os.makedirs(OUT, exist_ok=True)
    perp, futd = engine.market_data()
    funding = perp["funding_1h"]
    from dn import data
    fut = data.load_futures()
    d, fc = funding_forecast(perp, fut)
    d.to_csv(os.path.join(OUT, "funding_forecast_samples.csv"), index=False)
    fc.to_csv(os.path.join(OUT, "funding_forecast.csv"))
    print(fc.round(3).to_string(), flush=True)
    summ, years = {}, {}
    for name, kw in runs(funding):
        t0 = time.time()
        res = engine.run(start=START, end=END, capital_usd=CAP, verbose=False, **kw)
        summ[name] = metrics.summary(res)
        y = metrics.by_year(res)
        years[name] = y["return_ann"]
        y.to_csv(os.path.join(OUT, "years_%s.csv" % name.replace(" ", "_").replace("/", "-").replace("%", "pct")))
        res["hist"]["equity_usd"].resample("1D").last().to_csv(
            os.path.join(OUT, "equity_%s.csv" % name.replace(" ", "_").replace("/", "-").replace("%", "pct")))
        st = kw.get("strategy")
        if st is not None and getattr(st, "entries", None):
            pd.DataFrame(st.entries).to_csv(os.path.join(OUT, "entries_%s.csv" % name.replace(" ", "_").replace(
                "/", "-").replace("%", "pct")), index=False)
        print("%-42s ann %6.2f%%  vol %5.2f%%  maxDD %6.2f%%  (%.0fs)" % (
            name, 100 * summ[name]["ann_return"], 100 * summ[name]["ann_vol"], 100 * summ[name]["max_drawdown"],
            time.time() - t0), flush=True)
    s = pd.DataFrame(summ).T
    s.to_csv(os.path.join(OUT, "summary.csv"))
    pd.DataFrame(years).T.to_csv(os.path.join(OUT, "by_year.csv"))
    print(pd.DataFrame(years).T.mul(100).round(2).to_string())


if __name__ == "__main__":
    main()
