"""Loaders for the shared, read-only Deribit datasets (read in place; nothing is ever written there).

Time convention: every series is stamped at the hour `t` it is *known*:
  * perpetual / futures price at t = close of the 1h candle [t-1h, t) (last trade before t);
  * index, funding (interest_1h for the hour ending at t) from the funding file at t;
  * option snapshot at t as stamped in the chain.
"""
import os

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

SHARED = r"C:\ClaudeSandbox\shared-data"
CHAIN = os.path.join(SHARED, "option-chain", "option_chain_hourly.parquet")
FUT_DIR = os.path.join(SHARED, "deribit-futures")
H = pd.Timedelta(hours=1)

CHAIN_COLS = ["timestamp", "expirationTimestamp", "strike", "putCall", "bid", "ask", "markPrice", "markIv", "delta",
              "bidVolume", "askVolume", "underlyingPrice", "indexPrice", "instrument"]


def inverse_only(tbl):
    """Keep inverse BTC options (instrument 'BTC-...'); drops the linear BTC_USDC-... options (USD-quoted) that the
    chain also carries from October 2026."""
    import pyarrow.compute as pc
    return tbl.filter(pc.starts_with(tbl["instrument"], "BTC-"))


def load_perp():
    """DataFrame indexed by hour t: perp (price), perp_volume, index, funding_1h (interest_1h of the hour ending t)."""
    c = pd.read_parquet(os.path.join(FUT_DIR, "deribit_BTC_perpetual_1h.parquet"))
    p = pd.DataFrame({"perp": c["close"].values, "perp_volume": c["volume"].values},
                     index=c["datetime"] + H)
    f = pd.read_parquet(os.path.join(FUT_DIR, "deribit_BTC_perpetual_funding_1h.parquet")).set_index("datetime")
    p = p.join(f[["index_price", "interest_1h"]].rename(columns={"index_price": "index", "interest_1h": "funding_1h"}),
               how="inner")
    p.index.name = "t"
    return p


def load_futures():
    """Long table (t, instrument, expiry, price, volume), price stamped at the end of its candle."""
    c = pd.read_parquet(os.path.join(FUT_DIR, "deribit_BTC_futures_1h.parquet"),
                        columns=["instrument", "expiry", "datetime", "close", "volume"])
    out = pd.DataFrame({"t": c["datetime"] + H, "instrument": c["instrument"], "expiry": c["expiry"],
                        "price": c["close"], "volume": c["volume"]})
    return out[out["t"] <= out["expiry"]].reset_index(drop=True)


def futures_with_marks(fut, marks_path):
    """Price = synchronous mark from the option chain (cache/futures_mark_1h.parquet) where available; otherwise the
    candle close if that bar traded; otherwise NaN (no trade or settlement at a stale price)."""
    out = fut.copy()
    out["close"] = out["price"]
    if os.path.exists(marks_path):
        m = pd.read_parquet(marks_path)
        m = m[m["F_mark"] > 0]
        out = out.merge(m, on=["t", "expiry"], how="left")
    else:
        out["F_mark"] = np.nan
    out["price"] = out["F_mark"].where(out["F_mark"].notna(), out["close"].where(out["volume"] > 0))
    out["source"] = np.where(out["F_mark"].notna(), "mark", np.where(out["volume"] > 0, "close", "none"))
    return out


class _ByHour:
    """Lazy per-hour view: .get(t) -> DataFrame(index=instrument, columns=expiry, price, volume) or None."""

    def __init__(self, fut):
        f = fut.sort_values("t", kind="stable").reset_index(drop=True)
        f["instrument"] = f["instrument"].astype(object)
        self.f = f.set_index("instrument")[["expiry", "price", "volume"]]
        t = f["t"].values
        starts = np.flatnonzero(np.r_[True, t[1:] != t[:-1]])
        ends = np.r_[starts[1:], len(t)]
        self.pos = dict(zip(pd.DatetimeIndex(t[starts]).tz_localize("UTC") if f["t"].dt.tz is None else
                            pd.DatetimeIndex(f["t"].iloc[starts]), zip(starts, ends)))

    def get(self, t, default=None):
        p = self.pos.get(t)
        return default if p is None else self.f.iloc[p[0]:p[1]]


def futures_by_hour(fut):
    return _ByHour(fut)


class ChainReader:
    """Iterates the option chain hour by hour, reading one row group at a time.

    Yields (t, DataFrame) with columns expiry, strike, is_call, bid, ask, mark, iv, delta, bid_size, ask_size, F, index.
    Prices in BTC per 1 BTC underlying; iv as a decimal.
    """

    def __init__(self, path=CHAIN, start=None, end=None):
        self.f = pq.ParquetFile(path)
        self.start, self.end = start, end

    @staticmethod
    def _prep(tbl):
        d = tbl.to_pandas(ignore_metadata=True)
        out = pd.DataFrame({
            "t": d["timestamp"], "expiry": d["expirationTimestamp"], "strike": d["strike"].astype(float),
            "is_call": d["putCall"].values == "C",
            "bid": d["bid"].astype(float), "ask": d["ask"].astype(float), "mark": d["markPrice"].astype(float),
            "iv": d["markIv"].astype(float) / 100.0, "delta": d["delta"].astype(float),
            "bid_size": d["bidVolume"].astype(float), "ask_size": d["askVolume"].astype(float),
            "F": d["underlyingPrice"].astype(float), "index": d["indexPrice"].astype(float)})
        return out

    def hours(self):
        """Yields (t, DataFrame) per hour: plain columns (no index), see the class docstring; cheap row slices."""
        for d in self.batches():
            d = d.sort_values("t", kind="stable").reset_index(drop=True)
            t = d["t"].to_numpy()
            starts = np.flatnonzero(np.r_[True, t[1:] != t[:-1]])
            ends = np.r_[starts[1:], len(t)]
            for a, b in zip(starts, ends):
                yield d["t"].iloc[a], d.iloc[a:b]

    def batches(self):
        """Yields one DataFrame per row group (column t included), each holding only whole hours."""
        md = self.f.metadata
        ts_col = [md.row_group(0).column(j).path_in_schema for j in range(md.num_columns)].index("timestamp")
        groups = []
        for i in range(md.num_row_groups):
            s = md.row_group(i).column(ts_col).statistics
            if s is not None and s.has_min_max:
                lo, hi = _utc(s.min), _utc(s.max)
                if (self.end is not None and lo > self.end) or (self.start is not None and hi < self.start):
                    continue
            groups.append(i)
        carry = None
        for n, i in enumerate(groups):
            d = self._prep(inverse_only(self.f.read_row_group(i, columns=CHAIN_COLS)))
            if carry is not None:  # an hour may straddle two row groups
                d = pd.concat([carry, d], ignore_index=True)
            last = d["t"].max()
            carry = d[d["t"] == last] if n < len(groups) - 1 else None
            if carry is not None:
                d = d[d["t"] < last]
            if self.start is not None:
                d = d[d["t"] >= self.start]
            if self.end is not None:
                d = d[d["t"] <= self.end]
            if len(d):
                yield d


def _utc(x):
    ts = pd.Timestamp(x)
    return ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")


def hours_between(a, b):
    return pd.date_range(a, b, freq=H)


def year_frac(dt):
    return dt / pd.Timedelta(days=365.25) if isinstance(dt, pd.Timedelta) else np.asarray(dt) / (365.25 * 86400)
