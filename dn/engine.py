"""Hourly backtest loop.

    res = run(strategy, hedger_policy, start, end, capital_usd=1e6, use_options=False)

Order each hour t: funding for the hour ending t on positions held -> settle linear positions at t prices ->
expiries at the index -> strategy.on_hour -> hedger.rebalance -> record.
"""
import os
import time

import numpy as np
import pandas as pd

from dn import data
from dn.account import Account, Costs
from dn.hedger import Hedger
from dn.market import Market

_CACHE = {}


MARKS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "cache",
                     "futures_mark_1h.parquet")


def market_data(price_source="mark"):
    """price_source: 'mark' (synchronous chain marks, fallback traded close) or 'close' (raw candle closes)."""
    if price_source not in _CACHE:
        if "perp" not in _CACHE:
            _CACHE["perp"] = data.load_perp()
        fut = data.load_futures()
        if price_source == "mark":
            fut = data.futures_with_marks(fut, MARKS)
            fut = fut[fut["price"].notna()]
        _CACHE[price_source] = data.futures_by_hour(fut)
    return _CACHE["perp"], _CACHE[price_source]


class NullStrategy:
    """No positions of its own: the account is only the hedged collateral (A1 / A2 / A5 via the hedge policy)."""
    name = "collateral only"

    def on_hour(self, t, mkt, acct):
        pass


def run(strategy=None, policy=None, start=None, end=None, capital_usd=1e6, use_options=False, band_frac=0.0025,
        costs=None, verbose=True, price_source="mark"):
    perp, fut = market_data(price_source)
    strategy = strategy or NullStrategy()
    idx = perp.index
    if start is not None:
        idx = idx[idx >= pd.Timestamp(start, tz="UTC")]
    if end is not None:
        idx = idx[idx <= pd.Timestamp(end, tz="UTC")]
    acct = Account(costs or Costs())
    hedger = Hedger(policy, band_frac=band_frac, capital_usd=capital_usd)
    chain = data.ChainReader(start=idx[0], end=idx[-1]).hours() if use_options else None
    nxt = next(chain, None) if chain else None
    rows = perp.loc[idx]
    rec = []
    t0 = time.time()
    for i, t in enumerate(idx):
        opts = None
        if chain is not None:
            while nxt is not None and nxt[0] < t:
                nxt = next(chain, None)
            if nxt is not None and nxt[0] == t:
                opts = nxt[1]
        mkt = Market(t, rows.iloc[i], fut.get(t), opts)
        if i == 0:
            acct.deposit_usd(t, capital_usd, mkt.S)
        acct.accrue_funding(t, mkt)
        acct.settle_linear(t, mkt)
        acct.expire(t, mkt)
        strategy.on_hour(t, mkt, acct)
        hedger.rebalance(t, mkt, acct)
        eq = acct.equity_btc(mkt)
        rec.append((t, mkt.S, eq, eq * mkt.S, acct.delta_btc(mkt) * mkt.S, acct.gross_notional_usd(mkt),
                    acct.margin_btc(mkt) / eq if eq > 0 else np.nan, hedger.current))
        if verbose and i % 8766 == 0 and i:
            print("  %s  equity %.0f USD  (%.0fs)" % (t.date(), eq * mkt.S, time.time() - t0), flush=True)
    hist = pd.DataFrame(rec, columns=["t", "S", "equity_btc", "equity_usd", "delta_usd", "gross_usd", "margin_ratio",
                                      "hedge"]).set_index("t")
    ledger = pd.DataFrame(acct.ledger, columns=["t", "book", "kind", "btc", "usd"])
    return {"hist": hist, "ledger": ledger, "account": acct, "hedger_trades": hedger.trades,
            "strategy": getattr(strategy, "name", type(strategy).__name__), "capital_usd": capital_usd}
