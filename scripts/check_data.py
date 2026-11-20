"""Data checks for the engine's conventions (phase 1):
  1. which delta Deribit reports for inverse options: USD delta N(d1) or BTC delta N(d1) - price;
  2. mark prices vs Black-76/F on markIv (the pricing convention);
  3. inverse parity of marks C - P = 1 - K/F.
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dn import data, pricing  # noqa: E402

rows = []
for t, g in data.ChainReader(start=pd.Timestamp("2025-06-01", tz="UTC"), end=pd.Timestamp("2025-06-03", tz="UTC")).hours():
    g = g.copy()
    rows.append(g)
d = pd.concat(rows)
d["tau"] = (d["expiry"] - d["t"]).dt.total_seconds() / (365.25 * 86400)
d = d[(d["tau"] > 2 / 365) & (d["iv"] > 0)]
model = pricing.price_btc(d["F"], d["strike"], d["iv"], d["tau"], d["is_call"])
du = pricing.delta_usd(d["F"], d["strike"], d["iv"], d["tau"], d["is_call"])
print("rows", len(d))
print("mark vs Black76/F on markIv: median |diff| %.2e BTC, 99%% %.2e" % (
    np.median(np.abs(model - d["mark"])), np.quantile(np.abs(model - d["mark"]), 0.99)))
print("reported delta vs USD delta N(d1):         median |diff| %.4f" % np.median(np.abs(d["delta"] - du)))
print("reported delta vs BTC delta N(d1) - price: median |diff| %.4f" % np.median(np.abs(d["delta"] - (du - d["mark"]))))
k = d.set_index(["t", "expiry", "strike", "is_call"])["mark"].unstack("is_call").dropna()
F = d.groupby(["t", "expiry", "strike"])["F"].first().reindex(k.index)
res = (k[True] - k[False]) - (1 - k.index.get_level_values("strike") / F)
print("parity of marks: median |C-P-(1-K/F)| %.2e BTC, 99%% %.2e" % (res.abs().median(), res.abs().quantile(0.99)))
