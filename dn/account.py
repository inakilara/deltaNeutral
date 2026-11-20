"""Account holding BTC with inverse futures / perpetual and options, valued in USD.

* Linear positions (futures, perpetual) are sized in USD notional N (+ long) and settled into the BTC balance every
  hour at the market price (P&L N(1/ref - 1/price)), like Deribit's session settlement; `ref` is then reset.
* Options are held as contracts (+ long, 1 BTC underlying each); premium leaves / enters the balance at the trade
  (mid +/- cost); positions are marked at Deribit's mark; at expiry they pay their BTC payoff at the index.
* Every position belongs to a book ("strategy" or "hedge") so costs and cash flows can be attributed.
* Costs (the brief): options 0.001 BTC per contract (10 bps of the underlying price), linear 4 bps of notional.
"""
from collections import defaultdict

import numpy as np

from dn import pricing

PERP = "BTC-PERPETUAL"


class Costs:
    def __init__(self, option_bps=10.0, linear_bps=4.0):
        self.option_btc = option_bps * 1e-4  # BTC per contract: bps of the underlying price (1 BTC)
        self.linear = linear_bps * 1e-4


class Account:
    def __init__(self, costs=None):
        self.costs = costs or Costs()
        self.balance = 0.0                       # BTC
        self.lin = {}                            # (book, name) -> dict(N, ref, expiry)
        self.opts = defaultdict(float)           # (book, expiry, strike, is_call) -> contracts
        self.last_opt = {}                       # (expiry, strike, is_call) -> (mark, iv, F)
        self.ledger = []                         # cash flows: (t, book, kind, btc, usd)

    # ---- bookkeeping -------------------------------------------------------------------------------
    def _flow(self, t, book, kind, btc, S):
        self.balance += btc
        self.ledger.append((t, book, kind, btc, btc * S))

    def deposit_usd(self, t, usd, S):
        self._flow(t, "capital", "deposit", usd / S, S)

    # ---- linear instruments ------------------------------------------------------------------------
    def settle_linear(self, t, mkt):
        for (book, name), p in self.lin.items():
            px = mkt.lin_price(name)
            if px is None or not np.isfinite(px) or px == p["ref"]:
                continue
            self._flow(t, book, "linear_pnl", p["N"] * (1.0 / p["ref"] - 1.0 / px), mkt.S)
            p["ref"] = px

    def accrue_funding(self, t, mkt):
        f = mkt.funding_1h
        if f is None or not np.isfinite(f) or f == 0:
            return
        for (book, name), p in self.lin.items():
            if name == PERP and p["N"] != 0:
                self._flow(t, book, "funding", -p["N"] * f / mkt.S, mkt.S)  # longs pay when f > 0

    def trade_linear(self, t, mkt, book, name, dN, expiry=None):
        """Trade dN USD notional at the market price (+ explicit cost). Returns the price used."""
        if dN == 0:
            return None
        px = mkt.lin_price(name)
        if px is None or not np.isfinite(px):
            raise ValueError("no price for %s at %s" % (name, t))
        key = (book, name)
        p = self.lin.get(key)
        if p is None:
            p = self.lin[key] = {"N": 0.0, "ref": px, "expiry": expiry if name != PERP else None}
        elif p["ref"] != px:  # settle to the current price first
            self._flow(t, book, "linear_pnl", p["N"] * (1.0 / p["ref"] - 1.0 / px), mkt.S)
            p["ref"] = px
        p["N"] += dN
        self._flow(t, book, "cost", -self.costs.linear * abs(dN) / px, mkt.S)
        if abs(p["N"]) < 1e-6:
            del self.lin[key]
        return px

    def linear_N(self, book, name):
        p = self.lin.get((book, name))
        return p["N"] if p else 0.0

    # ---- options -----------------------------------------------------------------------------------
    def trade_option(self, t, mkt, book, key, qty):
        """key = (expiry, strike, is_call). Buys (qty>0) / sells at mid +/- cost. Returns fill price or None."""
        q = mkt.option(key)
        if q is None or not (q["bid"] > 0 and q["ask"] > 0):
            return None
        mid = 0.5 * (q["bid"] + q["ask"])
        self._flow(t, book, "premium", -qty * mid, mkt.S)
        self._flow(t, book, "cost", -abs(qty) * self.costs.option_btc, mkt.S)
        self.opts[(book,) + tuple(key)] += qty
        return mid + np.sign(qty) * self.costs.option_btc

    def _opt_state(self, mkt, key):
        q = mkt.option(key) if mkt.has_options else None
        if q is not None and np.isfinite(q["mark"]):
            self.last_opt[key] = (q["mark"], q["iv"], q["F"])
        return self.last_opt.get(key)

    def expire(self, t, mkt):
        for key in [k for k, p in self.lin.items() if p["expiry"] is not None and p["expiry"] <= t]:
            p = self.lin.pop(key)
            self._flow(t, key[0], "linear_pnl", p["N"] * (1.0 / p["ref"] - 1.0 / mkt.S), mkt.S)
        for key in [k for k in self.opts if k[1] <= t]:
            qty = self.opts.pop(key)
            book, expiry, K, is_call = key
            self._flow(t, book, "settlement", qty * float(pricing.payoff_btc(mkt.S, K, is_call)), mkt.S)
            self.last_opt.pop((expiry, K, is_call), None)

    # ---- valuation ---------------------------------------------------------------------------------
    def option_value_btc(self, mkt, book=None):
        v = 0.0
        for (b, expiry, K, is_call), qty in self.opts.items():
            if book is not None and b != book:
                continue
            st = self._opt_state(mkt, (expiry, K, is_call))
            if st is not None:
                v += qty * st[0]
        return v

    def equity_btc(self, mkt):
        unreal = 0.0
        for (book, name), p in self.lin.items():
            px = mkt.lin_price(name)
            if px is not None and np.isfinite(px):
                unreal += p["N"] * (1.0 / p["ref"] - 1.0 / px)
        return self.balance + unreal + self.option_value_btc(mkt)

    def delta_btc(self, mkt):
        """d(account USD value)/dS in BTC: balance + option USD deltas + N/price of linear positions."""
        d = self.equity_btc(mkt) - self.option_value_btc(mkt)  # balance incl. unrealised linear P&L
        for (book, name), p in self.lin.items():
            px = mkt.lin_price(name)
            if px is None or not np.isfinite(px):
                px = p["ref"]  # no price this hour: last settled price (the position is still there)
            d += p["N"] / px
        for (b, expiry, K, is_call), qty in self.opts.items():
            st = self._opt_state(mkt, (expiry, K, is_call))
            if st is None:
                continue
            tau = max((expiry - mkt.t).total_seconds() / (365.25 * 86400), 1e-6)
            d += qty * float(pricing.delta_usd(st[2], K, st[1], tau, is_call))
        return d

    def gross_notional_usd(self, mkt):
        lin = sum(abs(p["N"]) for p in self.lin.values())
        return lin + sum(abs(q) for q in self.opts.values()) * mkt.S

    def margin_btc(self, mkt, im_linear=0.02):
        """Simplified Deribit standard initial margin (BTC)."""
        m = sum(im_linear * abs(p["N"]) / (mkt.lin_price(n) or mkt.S) for (b, n), p in self.lin.items())
        for (b, expiry, K, is_call), qty in self.opts.items():
            if qty < 0:
                st = self._opt_state(mkt, (expiry, K, is_call))
                mark = st[0] if st else 0.0
                otm = max(K - mkt.S, 0.0) if is_call else max(mkt.S - K, 0.0)
                m += -qty * (max(0.15 - otm / mkt.S, 0.10) + mark)
        return m
