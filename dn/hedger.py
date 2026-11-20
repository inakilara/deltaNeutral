"""Delta hedger: keeps the account's USD delta within a band with one hedge instrument (book "hedge").

The hedge instrument is chosen by a policy each hour:
    PerpPolicy()                      always the perpetual (A2 funding carry as collateral)
    FuturePolicy(select)              a dated future chosen by `select(mkt) -> name` (A1 cash-and-carry)
    BestCarryPolicy(...)              A5: whichever of perpetual / futures has the best expected carry
When the chosen instrument changes, the old hedge is closed and the new one opened (both pay costs).
"""
import numpy as np

from dn.account import PERP


def is_quarterly(expiry):
    return expiry.month in (3, 6, 9, 12) and expiry.weekday() == 4 and expiry.day >= 22


def is_monthly(expiry):
    return expiry.weekday() == 4 and expiry.day >= 22


def select_future(kind="quarterly", target_days=None, min_days=7):
    """Return select(mkt) -> instrument name or None.
    kind: 'quarterly' / 'monthly' / 'any'; picks the nearest with >= min_days, or the one closest to target_days."""
    def sel(mkt):
        f = mkt.live_futures(min_days)
        if f.empty:
            return None
        if kind == "quarterly":
            f = f[f["expiry"].map(is_quarterly)]
        elif kind == "monthly":
            f = f[f["expiry"].map(is_monthly)]
        if f.empty:
            return None
        if target_days is None:
            return f.index[0]
        return (f["days"] - target_days).abs().idxmin()
    return sel


class PerpPolicy:
    def instrument(self, mkt, current):
        return PERP


class FuturePolicy:
    """Hold a dated future until it expires (or falls under `roll_days`), then move to select(mkt)."""

    def __init__(self, select, roll_days=0.0):
        self.select, self.roll_days = select, roll_days

    def instrument(self, mkt, current):
        if current is not None and current != PERP and current in mkt.futures.index:
            days = (mkt.futures.at[current, "expiry"] - mkt.t).total_seconds() / 86400
            if days > self.roll_days:
                return current
        return self.select(mkt) or PERP


class BestCarryPolicy:
    """A2 switching / A5: hold the collateral hedge with the best expected carry.

    carry(perpetual) = trailing mean funding over `lookback_h` (annualised);
    carry(future)    = its annualised basis vs the index (locked if held to expiry).
    Decisions use the previous hour's prices (one-hour delay); trades execute at the current hour's prices.
    Switch only when the expected gain over the horizon, (carry_best - carry_current) x horizon, exceeds the
    round-trip switching cost (close + open, 2 x linear cost) plus `margin_bps`. The horizon is the remaining life
    of the futures involved (capped at `max_horizon_days`; perpetual alone: `max_horizon_days`).
    A held future is left when it falls under `min_days`.
    """

    def __init__(self, funding, candidates, lookback_h=24 * 7, margin_bps=0.0, min_days=7, max_horizon_days=90,
                 linear_cost=4e-4):
        self.cum = funding.fillna(0.0).cumsum()
        self.lookback_h, self.margin = lookback_h, margin_bps * 1e-4
        self.min_days, self.max_h, self.switch_cost = min_days, max_horizon_days, 2 * linear_cost
        self.candidates = candidates
        self.prev = None  # (carry dict, days-to-expiry dict) from the previous hour

    def perp_carry(self, t):
        i = self.cum.index.searchsorted(t, side="right") - 1
        j = i - self.lookback_h
        if j < 0:
            return np.nan
        return (self.cum.iloc[i] - self.cum.iloc[j]) / self.lookback_h * 8766

    def _snapshot(self, mkt):
        carry, days = {PERP: self.perp_carry(mkt.t)}, {PERP: np.inf}
        for name in self.candidates(mkt):
            carry[name] = mkt.basis_ann(name)
            days[name] = (mkt.futures.at[name, "expiry"] - mkt.t).total_seconds() / 86400
        return {k: v for k, v in carry.items() if np.isfinite(v)}, days

    def instrument(self, mkt, current):
        decide, self.prev = self.prev, self._snapshot(mkt)
        if decide is None:
            return current or PERP
        carry, days = decide
        live = lambda n: n == PERP or n in mkt.futures.index  # noqa: E731
        carry = {k: v for k, v in carry.items() if live(k)}
        if not carry:
            return current or PERP
        best = max(carry, key=carry.get)
        if current is None or current not in carry:  # start, or the held future expired / fell under min_days
            return best
        horizon = min(days.get(best, np.inf), days.get(current, np.inf), self.max_h) / 365.25
        gain = (carry[best] - carry[current]) * horizon
        return best if gain > self.switch_cost + self.margin else current


def future_candidates(kind="any", min_days=7, max_days=400):
    def cand(mkt):
        f = mkt.live_futures(min_days)
        f = f[f["days"] <= max_days]
        if kind == "quarterly":
            f = f[f["expiry"].map(is_quarterly)]
        elif kind == "monthly":
            f = f[f["expiry"].map(is_monthly)]
        return list(f.index)
    return cand


class Hedger:
    def __init__(self, policy=None, band_frac=0.01, capital_usd=1.0):
        self.policy = policy or PerpPolicy()
        self.band_frac, self.capital_usd = band_frac, capital_usd
        self.current = None
        self.trades = 0

    def rebalance(self, t, mkt, acct):
        if (self.current is not None and acct.linear_N("hedge", self.current) != 0
                and mkt.lin_price(self.current) is None):
            return  # the open hedge has no price this hour: keep it, trade nothing
        target = self.policy.instrument(mkt, self.current)
        if target != self.current:
            if self.current is not None:
                N = acct.linear_N("hedge", self.current)
                if N != 0 and mkt.lin_price(self.current) is not None:
                    acct.trade_linear(t, mkt, "hedge", self.current, -N)
            self.current = target
        delta = acct.delta_btc(mkt)
        band = self.band_frac * self.capital_usd / mkt.S
        if abs(delta) > band or (acct.linear_N("hedge", target) == 0 and abs(delta) > 1e-9):
            px = mkt.lin_price(target)
            if px is None or not np.isfinite(px):
                return
            expiry = None if target == PERP else mkt.futures.at[target, "expiry"]
            acct.trade_linear(t, mkt, "hedge", target, -delta * px, expiry=expiry)
            self.trades += 1
