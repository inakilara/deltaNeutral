"""A5 sanity check: is the gross carry of frequent switching real, or harvested mark noise?

    python scripts/check_a5_noise.py mark|close [linear_bps]
"""
import os
import sys
import warnings

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from dn import engine, metrics  # noqa: E402
from dn.account import Costs  # noqa: E402
from dn.hedger import BestCarryPolicy, future_candidates  # noqa: E402

warnings.filterwarnings("ignore")
src = sys.argv[1]
bps = float(sys.argv[2]) if len(sys.argv) > 2 else 4.0
perp, _ = engine.market_data(src)
pol = BestCarryPolicy(perp["funding_1h"], future_candidates("any"), lookback_h=24 * 7, margin_bps=0,
                      linear_cost=bps * 1e-4)
res = engine.run(policy=pol, start="2019-05-01", end="2026-11-19", verbose=False, price_source=src,
                 costs=Costs(linear_bps=bps))
s = metrics.summary(res)
print("A5 lb=7d m=0 | prices=%s linear=%.0fbp | ann %.2f%%  costs %.2f%%/yr  gross %.2f%%  trades %d" % (
    src, bps, 100 * s["ann_return"], 100 * s["costs_usd_per_year_pct"],
    100 * (s["ann_return"] + s["costs_usd_per_year_pct"]), s["hedger_trades"]))
