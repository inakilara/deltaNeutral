"""Phase 5 synthesis: correlations and combined portfolios on the common window 2020-01-01 -> 2026-10-25.

    python scripts/run_phase5.py   -> reports/phase5/*.csv

Building blocks (daily USD returns on USD capital):
    A2   perpetual funding carry (phase 4 baseline run, chain window)
    A1   nearest-quarterly cash-and-carry (phase 2)
    A1m  closest-to-30d cash-and-carry (phase 2)
    C1   30d short straddle overlay (run - A2), scaled to a 50 % peak margin ratio (phase4_overlay)
Portfolios are daily-rebalanced capital splits (a simplification: the carry legs share one USD collateral).
"""
import json
import os

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P2, P4 = os.path.join(ROOT, "reports", "phase2"), os.path.join(ROOT, "reports", "phase4")
OUT = os.path.join(ROOT, "reports", "phase5")
START, END = "2020-01-01", "2026-10-25"


def ret(path):
    e = pd.read_csv(path, index_col=0, parse_dates=True).iloc[:, 0]
    r = e.pct_change().dropna()
    return r[(r.index >= pd.Timestamp(START, tz="UTC")) & (r.index <= pd.Timestamp(END, tz="UTC"))]


def stats(r):
    eq = (1 + r).cumprod()
    yrs = len(r) / 365.25
    by_y = r.groupby(r.index.year).apply(lambda x: (1 + x).prod() - 1)
    return {"ann_return": eq.iloc[-1] ** (1 / yrs) - 1, "vol": r.std() * np.sqrt(365.25),
            "sharpe": r.mean() / r.std() * np.sqrt(365.25), "max_dd": (eq / eq.cummax() - 1).min(),
            "worst_week": eq.resample("7D").last().pct_change().min(), "median_year": by_y.median(),
            "worst_year": by_y.min()}


def main():
    os.makedirs(OUT, exist_ok=True)
    a2 = ret(os.path.join(P4, "A2_baseline_chain_window_equity.csv"))
    a1 = ret(os.path.join(P2, "equity_A1_nearest_quarterly.csv"))
    a1m = ret(os.path.join(P2, "equity_A1_closest_to_30d.csv"))
    s = json.load(open(os.path.join(P4, "C1_straddle_30d_band_10pct.json")))
    c1r = ret(os.path.join(P4, "C1_straddle_30d_band_10pct_equity.csv"))
    c1 = (c1r - a2) * min(1.0, 0.5 / s["max_margin_ratio"])
    blocks = pd.DataFrame({"A2": a2, "A1": a1, "A1m": a1m, "C1 overlay": c1}).dropna()
    corr = blocks.corr()
    ports = {
        "A2 perpetual carry": blocks["A2"],
        "A1 quarterly cash-and-carry": blocks["A1"],
        "A1 30d cash-and-carry": blocks["A1m"],
        "50% A2 + 50% A1 30d": 0.5 * blocks["A2"] + 0.5 * blocks["A1m"],
        "A2 + C1 overlay (50% margin)": blocks["A2"] + blocks["C1 overlay"],
        "50/50 A2/A1 30d + C1 overlay": 0.5 * blocks["A2"] + 0.5 * blocks["A1m"] + blocks["C1 overlay"],
    }
    tab = pd.DataFrame({k: stats(v) for k, v in ports.items()}).T
    years = pd.DataFrame({k: v.groupby(v.index.year).apply(lambda x: (1 + x).prod() - 1) for k, v in ports.items()}).T
    corr.to_csv(os.path.join(OUT, "correlation.csv"))
    tab.to_csv(os.path.join(OUT, "portfolios.csv"))
    years.to_csv(os.path.join(OUT, "portfolios_by_year.csv"))
    pd.set_option("display.width", 250)
    print(corr.round(3).to_string())
    print(tab.astype(float).round(4).to_string())
    print((100 * years).round(1).to_string())


if __name__ == "__main__":
    main()
