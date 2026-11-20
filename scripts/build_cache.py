"""Build derived panels in data/cache/ (never in shared-data).

    python scripts/build_cache.py

futures_mark_1h.parquet: per hour t and expiry, Deribit's underlying price of that expiry from the option chain
(median over the expiry's rows; equal to the dated future's mark where a future is listed). Synchronous with the
index, unlike the futures' last-trade candle closes, which can be stale or dislocated in fast markets.
"""
import os
import sys
import time

import pandas as pd
import pyarrow.parquet as pq

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from dn import data  # noqa: E402

CACHE = os.path.join(ROOT, "data", "cache")


def futures_marks():
    f = pq.ParquetFile(data.CHAIN)
    parts, t0 = [], time.time()
    for i in range(f.metadata.num_row_groups):
        d = data.inverse_only(f.read_row_group(
            i, columns=["timestamp", "expirationTimestamp", "underlyingPrice", "instrument"])).drop_columns(
            ["instrument"]).to_pandas(ignore_metadata=True)
        parts.append(d.groupby(["timestamp", "expirationTimestamp"])["underlyingPrice"].median().reset_index())
    m = pd.concat(parts).groupby(["timestamp", "expirationTimestamp"])["underlyingPrice"].median().reset_index()
    m.columns = ["t", "expiry", "F_mark"]
    print("futures marks: %d rows (%.0fs)" % (len(m), time.time() - t0))
    return m


def main():
    os.makedirs(CACHE, exist_ok=True)
    m = futures_marks()
    m.to_parquet(os.path.join(CACHE, "futures_mark_1h.parquet"), index=False)
    # agreement with traded candle closes where the bar traded
    fut = data.load_futures()
    j = fut.merge(m, on=["t", "expiry"], how="inner")
    j = j[j["volume"] > 0]
    d = (j["price"] / j["F_mark"] - 1).abs() * 1e4
    print("listed-future hours with a chain mark: %d; |close/mark - 1| bps: median %.1f, 99%% %.1f, max %.0f" % (
        len(j), d.median(), d.quantile(0.99), d.max()))


if __name__ == "__main__":
    main()
