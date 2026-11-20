"""Delta-one overlay strategies (book "strategy"); the collateral hedge is the engine's hedger.

A3 FundingBasis: pair future / perpetual with equal USD notional, held to the future's expiry.
    side +1 = short future / long perpetual  (earn the basis, pay funding)
    side -1 = long future / short perpetual  (earn funding, give up the basis)
    mode "signal": side chosen at entry from basis_ann - trailing funding_ann vs a threshold (only data <= t);
    mode "short_basis" / "long_basis": always +1 / -1.
A4 Calendar: long near / short far future (same notional), held to the near expiry, then re-entered.
Notional per leg = `notional_frac` x capital (USD).
"""
import numpy as np

from dn.account import PERP
from dn.hedger import is_quarterly


def _pick(mkt, kind, min_days):
    f = mkt.live_futures(min_days)
    if kind == "quarterly":
        f = f[f["expiry"].map(is_quarterly)]
    return f


class FundingBasis:
    def __init__(self, funding, capital_usd, mode="signal", threshold=0.04, lookback_h=24 * 30, kind="quarterly",
                 min_days=14, notional_frac=1.0):
        self.cum = funding.fillna(0.0).cumsum()
        self.capital, self.mode, self.thr, self.lb = capital_usd, mode, threshold, lookback_h
        self.kind, self.min_days, self.frac = kind, min_days, notional_frac
        self.fut, self.side = None, 0
        self.name = "A3 funding-basis %s thr=%.2f lb=%dd %s" % (mode, threshold, lookback_h // 24, kind)
        self.entries = []

    def trailing_funding(self, t):
        i = self.cum.index.searchsorted(t, side="right") - 1
        j = i - self.lb
        return np.nan if j < 0 else (self.cum.iloc[i] - self.cum.iloc[j]) / self.lb * 8766

    def on_hour(self, t, mkt, acct):
        if self.fut is not None and acct.linear_N("strategy", self.fut) == 0:  # future expired (settled)
            N = acct.linear_N("strategy", PERP)
            if N:
                acct.trade_linear(t, mkt, "strategy", PERP, -N)
            self.fut, self.side = None, 0
        if self.fut is not None:
            return
        f = _pick(mkt, self.kind, self.min_days)
        if f.empty:
            return
        name = f.index[0]
        basis, fund = mkt.basis_ann(name), self.trailing_funding(t)
        if self.mode == "short_basis":
            side = 1
        elif self.mode == "long_basis":
            side = -1
        else:
            if not np.isfinite(fund):
                return
            s = basis - fund
            side = 1 if s > self.thr else (-1 if s < -self.thr else 0)
        if side == 0:
            return
        N = self.frac * self.capital
        acct.trade_linear(t, mkt, "strategy", name, -side * N, expiry=f.at[name, "expiry"])
        acct.trade_linear(t, mkt, "strategy", PERP, side * N)
        self.fut, self.side = name, side
        self.entries.append((t, name, side, basis, fund))


class Calendar:
    def __init__(self, capital_usd, min_days=14, notional_frac=1.0):
        self.capital, self.min_days, self.frac = capital_usd, min_days, notional_frac
        self.near = self.far = None
        self.name = "A4 calendar long near / short far quarterly"
        self.entries = []

    def on_hour(self, t, mkt, acct):
        if self.near is not None and acct.linear_N("strategy", self.near) == 0:  # near leg settled
            N = acct.linear_N("strategy", self.far)
            if N and mkt.lin_price(self.far) is not None:
                acct.trade_linear(t, mkt, "strategy", self.far, -N)
            self.near = self.far = None
        if self.near is not None:
            return
        f = _pick(mkt, "quarterly", self.min_days)
        if len(f) < 2:
            return
        near, far = f.index[0], f.index[1]
        N = self.frac * self.capital
        acct.trade_linear(t, mkt, "strategy", near, N, expiry=f.at[near, "expiry"])
        acct.trade_linear(t, mkt, "strategy", far, -N, expiry=f.at[far, "expiry"])
        self.near, self.far = near, far
        self.entries.append((t, near, far, mkt.basis_ann(near), mkt.basis_ann(far)))
