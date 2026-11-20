"""Market snapshot at hour t: index, perpetual, funding, live futures and (optionally) the option chain."""
import numpy as np
import pandas as pd

from dn.account import PERP


class Market:
    def __init__(self, t, row, futures=None, options=None):
        self.t = t
        self.S = float(row["index"])
        self.perp = float(row["perp"])
        self.funding_1h = float(row["funding_1h"])
        self.futures = futures if futures is not None else pd.DataFrame(columns=["expiry", "price", "volume"])
        self.options = options
        self.has_options = options is not None and len(options) > 0
        self._pos = self._cols = None

    def lin_price(self, name):
        if name == PERP:
            return self.perp
        if name in self.futures.index:
            return float(self.futures.at[name, "price"])
        return None

    def option(self, key):
        """Quote for (expiry, strike, is_call) as a dict of columns, or None. Lookup via a per-hour hash map."""
        if not self.has_options:
            return None
        if self._pos is None:
            o = self.options
            ek = pd.DatetimeIndex(o["expiry"]).as_unit("ns").asi8
            self._pos = {k: i for i, k in enumerate(zip(ek.tolist(), o["strike"].tolist(), o["is_call"].tolist()))}
            self._cols = {c: o[c].to_numpy() for c in o.columns if c not in ("t", "expiry", "strike", "is_call")}
        e, K, c = key
        i = self._pos.get((pd.Timestamp(e).value, float(K), bool(c)))
        if i is None:
            return None
        return {c: v[i] for c, v in self._cols.items()}

    def live_futures(self, min_days=0.0):
        f = self.futures
        if f.empty:
            return f.assign(days=pd.Series(dtype=float))
        days = (pd.to_datetime(f["expiry"]) - self.t).dt.total_seconds() / 86400
        return f.assign(days=days)[days >= min_days].sort_values("days")

    def basis_ann(self, name):
        """Annualised log basis of a future vs the index."""
        if name not in self.futures.index:
            return np.nan
        f = self.futures.loc[name]
        tau = (f["expiry"] - self.t).total_seconds() / (365.25 * 86400)
        return np.log(f["price"] / self.S) / tau if tau > 0 else np.nan
