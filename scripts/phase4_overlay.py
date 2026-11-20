"""Phase 4 overlays: option structure = run - A2 baseline (daily USD returns), scaled to a 50 % peak margin ratio.

    python scripts/phase4_overlay.py      -> reports/phase4/overlay.csv
Scaling is linear (positions, hedges and costs all scale with notional), using the run's peak margin ratio.
"""
import json
import os

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "reports", "phase4")
TARGET_MARGIN = 0.5
START = "2020-01-01"  # skip the one-month 2019 stub


def daily(f):
    e = pd.read_csv(os.path.join(OUT, f), index_col=0, parse_dates=True).iloc[:, 0]
    return e.pct_change().dropna()


def main():
    base = daily("A2_baseline_chain_window_equity.csv")
    rows = {}
    for f in sorted(os.listdir(OUT)):
        if not f.endswith(".json") or f.startswith("A2"):
            continue
        s = json.load(open(os.path.join(OUT, f)))
        r = daily(f[:-5] + "_equity.csv")
        ov = (r - base).dropna()
        ov = ov[ov.index >= pd.Timestamp(START, tz=ov.index.tz)]
        k = min(1.0, TARGET_MARGIN / s["max_margin_ratio"])
        x = ov * k
        eq = (1 + x).cumprod()
        yrs = len(x) / 365.25
        ann = x.mean() * 365.25
        wk = eq.resample("7D").last().pct_change().min()
        by_y = x.groupby(x.index.year).sum()
        rows[s["name"]] = {
            "scale": k, "overlay_ann": ann, "overlay_vol": x.std() * np.sqrt(365.25),
            "overlay_sharpe": ann / (x.std() * np.sqrt(365.25)), "overlay_maxdd": (eq / eq.cummax() - 1).min(),
            "worst_week": wk, "worst_week_over_ann": -wk / ann if ann > 0 else np.inf,
            "worst_year": by_y.min(), "best_year": by_y.max(), "years_negative": int((by_y < 0).sum()),
            "corr_with_A2": r.corr(base)}
    df = pd.DataFrame(rows).T.sort_values("overlay_sharpe", ascending=False)
    df.to_csv(os.path.join(OUT, "overlay.csv"))
    pd.set_option("display.width", 250)
    print(df.astype(float).round(4).to_string())
    years = {}
    for f in sorted(os.listdir(OUT)):
        if f.endswith(".json") and not f.startswith("A2"):
            s = json.load(open(os.path.join(OUT, f)))
            r = daily(f[:-5] + "_equity.csv")
            x = (r - base).dropna() * min(1.0, TARGET_MARGIN / s["max_margin_ratio"])
            x = x[x.index >= pd.Timestamp(START, tz=x.index.tz)]
            years[s["name"]] = x.groupby(x.index.year).sum()
    y = pd.DataFrame(years).T
    y.to_csv(os.path.join(OUT, "overlay_by_year.csv"))
    print((100 * y).round(1).to_string())


if __name__ == "__main__":
    main()
