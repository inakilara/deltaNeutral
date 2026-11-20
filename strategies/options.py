"""Option strategies (phase 4). Collateral and delta hedging come from the engine's hedger (perpetual by default),
so total return = A2 synthetic-dollar carry + the option overlay.
"""
import numpy as np
import pandas as pd

DAY = 86400.0


def chain_ok(mkt, max_index_gap=0.002):
    """Skip snapshots we do not trust: the 08:00 settlement snapshot (out of sync in 2026), and snapshots whose
    index disagrees with the perpetual feed's index (stale chain)."""
    if not mkt.has_options or mkt.t.hour == 8:
        return False
    idx = float(mkt.options["index"].iloc[0])
    return abs(idx / mkt.S - 1) < max_index_gap


def atm_pair(mkt, target_days, min_days=1.0):
    """(expiry, strike, call row, put row, days) of the ATM straddle at the expiry closest to target_days, using
    strikes with two-sided quotes on both legs; None if none."""
    o = mkt.options
    exps = pd.DatetimeIndex(o["expiry"].unique())
    days = pd.Series((exps - mkt.t).total_seconds() / DAY, index=exps)
    days = days[days >= max(min_days, 0.5 * target_days)]
    if days.empty:
        return None
    e = (days - target_days).abs().idxmin()
    sub = o[o["expiry"] == e]
    two = sub[(sub["bid"] > 0) & (sub["ask"] > 0)]
    two = two.drop_duplicates(["strike", "is_call"])  # the chain has occasional duplicate rows
    calls = two[two["is_call"]].set_index("strike")
    puts = two[~two["is_call"]].set_index("strike")
    ks = calls.index.intersection(puts.index)
    if len(ks) == 0:
        return None
    F = float(sub["F"].iloc[0])
    K = min(ks, key=lambda k: abs(k - F))
    return e, K, calls.loc[K], puts.loc[K], days[e]


def _expiry_near(mkt, target_days, min_days=1.0):
    o = mkt.options
    exps = pd.DatetimeIndex(o["expiry"].unique())
    days = pd.Series((exps - mkt.t).total_seconds() / DAY, index=exps)
    days = days[days >= max(min_days, 0.5 * target_days)]
    if days.empty:
        return None, None
    e = (days - target_days).abs().idxmin()
    return e, days[e]


def _two_sided(mkt, e):
    o = mkt.options
    s = o[(o["expiry"] == e) & (o["bid"] > 0) & (o["ask"] > 0)]
    return s


def _vega(row, t, e):
    from dn import pricing
    tau = (e - t).total_seconds() / (365.25 * DAY)
    return float(pricing.vega_usd(row["F"], row["strike"], row["iv"], tau))


def _atm(s):
    s = s.drop_duplicates(["strike", "is_call"])  # the chain has occasional duplicate rows
    c, p = s[s["is_call"]].set_index("strike"), s[~s["is_call"]].set_index("strike")
    ks = c.index.intersection(p.index)
    if len(ks) == 0:
        return None
    F = float(s["F"].iloc[0])
    K = min(ks, key=lambda k: abs(k - F))
    return K, c.loc[K], p.loc[K]


def _by_delta(s, is_call, target):
    x = s[s["is_call"] == is_call]
    if x.empty:
        return None
    r = x.iloc[(x["delta"] - target).abs().argmin()]
    return r if abs(r["delta"] - target) < 0.10 else None


def build_calendar(mkt, qty, front_days=10, back_days=45):
    """C2: short front ATM straddle, long back ATM straddle, vega-matched (USD vega of the back = front)."""
    ef, df_ = _expiry_near(mkt, front_days)
    eb, db = _expiry_near(mkt, back_days, min_days=front_days + 7)
    if ef is None or eb is None or eb <= ef:
        return None
    af, ab = _atm(_two_sided(mkt, ef)), _atm(_two_sided(mkt, eb))
    if af is None or ab is None:
        return None
    Kf, cf, pf = af
    Kb, cb, pb = ab
    vf = _vega(dict(cf, strike=Kf), mkt.t, ef) + _vega(dict(pf, strike=Kf), mkt.t, ef)
    vb = _vega(dict(cb, strike=Kb), mkt.t, eb) + _vega(dict(pb, strike=Kb), mkt.t, eb)
    if not (vf > 0 and vb > 0):
        return None
    qb = qty * vf / vb
    legs = [((ef, Kf, True), -qty), ((ef, Kf, False), -qty), ((eb, Kb, True), qb), ((eb, Kb, False), qb)]
    info = {"front": ef, "back": eb, "Kf": Kf, "Kb": Kb, "iv_front": 0.5 * (cf["iv"] + pf["iv"]),
            "iv_back": 0.5 * (cb["iv"] + pb["iv"]), "q_back": qb}
    return legs, info


def build_skew(mkt, qty, days=30, kind="rr"):
    """C3: 'rr' = sell the 25-delta risk reversal (short 25d put, long 25d call);
    'fly' = sell the 25-delta strangle, buy the ATM straddle, vega-matched (short wings)."""
    e, d = _expiry_near(mkt, days)
    if e is None:
        return None
    s = _two_sided(mkt, e)
    c25, p25 = _by_delta(s, True, 0.25), _by_delta(s, False, -0.25)
    if c25 is None or p25 is None:
        return None
    if kind == "rr":
        legs = [((e, float(p25["strike"]), False), -qty), ((e, float(c25["strike"]), True), qty)]
        return legs, {"expiry": e, "iv_put25": p25["iv"], "iv_call25": c25["iv"], "skew": p25["iv"] - c25["iv"]}
    a = _atm(s)
    if a is None:
        return None
    K, ca, pa = a
    vw = _vega(c25, mkt.t, e) + _vega(p25, mkt.t, e)
    va = _vega(dict(ca, strike=K), mkt.t, e) + _vega(dict(pa, strike=K), mkt.t, e)
    qa = qty * vw / va
    legs = [((e, float(p25["strike"]), False), -qty), ((e, float(c25["strike"]), True), -qty),
            ((e, K, True), qa), ((e, K, False), qa)]
    return legs, {"expiry": e, "wing_iv": 0.5 * (c25["iv"] + p25["iv"]), "atm_iv": 0.5 * (ca["iv"] + pa["iv"]),
                  "q_atm": qa}


class Rolling:
    """Open the structure from builder(mkt, qty) -> (legs, info); when its nearest leg expires, close what is left
    and open the next. qty = notional_frac x capital in BTC contracts."""

    def __init__(self, name, builder, capital_usd, notional_frac=1.0, book="opt", **kw):
        self.name, self.builder, self.capital_usd, self.frac, self.book, self.kw = (
            name, builder, capital_usd, notional_frac, book, kw)
        self.legs = []  # keys (expiry, K, is_call) currently held
        self.entries = []

    def _held(self, acct):
        return [k for k in self.legs if abs(acct.opts.get((self.book,) + tuple(k), 0.0)) > 1e-12]

    def on_hour(self, t, mkt, acct):
        held = self._held(acct)
        if held:
            if min(k[0] for k in self.legs) > t:
                return  # nearest leg still alive
            if not chain_ok(mkt):
                return
            for k in held:  # the nearest leg has settled: close the rest
                q = acct.opts[(self.book,) + tuple(k)]
                if acct.trade_option(t, mkt, self.book, k, -q) is not None:
                    acct.opts.pop((self.book,) + tuple(k), None)
            if self._held(acct):
                return
        if not chain_ok(mkt):
            return
        b = self.builder(mkt, self.frac * self.capital_usd / mkt.S, **self.kw)
        if b is None:
            return
        legs, info = b
        if any(mkt.option(k) is None for k, _ in legs):
            return
        for k, q in legs:
            acct.trade_option(t, mkt, self.book, k, q)
        self.legs = [k for k, _ in legs]
        self.entries.append({"t": t, "S": mkt.S, **{k: (float(v) if isinstance(v, (int, float, np.floating)) else v)
                                                     for k, v in info.items()}})


class ShortStraddle:
    """C1: sell the ATM straddle (expiry closest to target_days), hold to expiry or close `close_days` before.
    Size: notional_frac x capital in BTC contracts per leg. Optional vol filter: enter only when the straddle's
    mark IV minus trailing realised vol (rv_hours of hourly index returns) exceeds vol_filter (decimal)."""

    def __init__(self, capital_usd, target_days=7, notional_frac=1.0, close_days=0.0, vol_filter=None, index=None,
                 rv_hours=24 * 30, book="opt"):
        self.capital_usd, self.target, self.frac = capital_usd, target_days, notional_frac
        self.close_days, self.vol_filter, self.book = close_days, vol_filter, book
        self.name = "short straddle %dd" % target_days
        self.pos = None  # (expiry, K, qty)
        self.entries = []
        self.rv = None
        if index is not None:
            r = np.log(index).diff()
            self.rv = r.rolling(rv_hours).std() * np.sqrt(8766)

    def _close(self, t, mkt, acct):
        e, K, _ = self.pos
        done = True
        for is_call in (True, False):
            key = (self.book, e, K, is_call)
            q = acct.opts.get(key, 0.0)
            if q != 0:
                if acct.trade_option(t, mkt, self.book, (e, K, is_call), -q) is None:
                    done = False
                elif abs(acct.opts.get(key, 0.0)) < 1e-12:
                    acct.opts.pop(key, None)
        if done:
            self.pos = None

    def on_hour(self, t, mkt, acct):
        if self.pos is not None:
            e = self.pos[0]
            if e <= t:
                self.pos = None  # settled by the account
            elif self.close_days and (e - t).total_seconds() / DAY < self.close_days and chain_ok(mkt):
                self._close(t, mkt, acct)
            if self.pos is not None:
                return
        if not chain_ok(mkt):
            return
        p = atm_pair(mkt, self.target)
        if p is None:
            return
        e, K, c, pu, days = p
        if self.close_days and days <= self.close_days + 0.5:
            return
        iv = 0.5 * (float(c["iv"]) + float(pu["iv"]))
        rv = float(self.rv.asof(t)) if self.rv is not None else np.nan
        if self.vol_filter is not None and not (np.isfinite(rv) and iv - rv > self.vol_filter):
            return
        qty = self.frac * self.capital_usd / mkt.S
        acct.trade_option(t, mkt, self.book, (e, K, True), -qty)
        acct.trade_option(t, mkt, self.book, (e, K, False), -qty)
        self.pos = (e, K, qty)
        prem = 0.5 * (c["bid"] + c["ask"]) + 0.5 * (pu["bid"] + pu["ask"])
        self.entries.append({"t": t, "expiry": e, "K": K, "days": days, "F": float(c["F"]), "S": mkt.S, "iv": iv,
                             "rv": rv, "qty": qty, "premium_btc": float(prem)})
