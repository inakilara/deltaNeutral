"""Payoff identities of documents/02_backtest_framework.md section 7, on synthetic markets."""
import os
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dn import pricing  # noqa: E402
from dn.account import PERP, Account, Costs  # noqa: E402
from dn.market import Market  # noqa: E402

T0 = pd.Timestamp("2025-01-03 08:00", tz="UTC")
EXP = pd.Timestamp("2025-03-28 08:00", tz="UTC")
FUT = "BTC-28MAR25"
TAU = (EXP - T0).total_seconds() / (365.25 * 86400)


def mkt(t, S, F=None, perp=None, funding=0.0, options=None):
    row = {"index": S, "perp": perp if perp is not None else S, "funding_1h": funding}
    fut = pd.DataFrame({"expiry": [EXP], "price": [F if F is not None else S], "volume": [1.0]}, index=[FUT])
    return Market(t, row, fut, options)


def chain(t, S, F, strikes, sigma=0.6):
    tau = max((EXP - t).total_seconds() / (365.25 * 86400), 1e-9)
    rows = []
    for K in strikes:
        for c in (True, False):
            p = float(pricing.price_btc(F, K, sigma, tau, c))
            rows.append({"expiry": EXP, "strike": float(K), "is_call": c, "bid": p, "ask": p, "mark": p, "iv": sigma,
                         "F": F, "delta": np.nan})
    return pd.DataFrame(rows)  # same layout as ChainReader.hours(): plain columns


@pytest.mark.parametrize("ST", [20_000.0, 95_000.0, 400_000.0])
def test_cash_and_carry_locks_F0_usd(ST):
    S0, F0 = 100_000.0, 103_000.0
    a = Account(Costs(0, 0))
    m0 = mkt(T0, S0, F0)
    a.deposit_usd(T0, S0, S0)                      # 1 BTC
    a.trade_linear(T0, m0, "strategy", FUT, -F0, expiry=EXP)
    mid = mkt(T0 + pd.Timedelta(days=30), 70_000.0, 71_000.0)
    a.settle_linear(mid.t, mid)
    mT = mkt(EXP, ST, ST)
    a.settle_linear(EXP, mT)
    a.expire(EXP, mT)
    assert a.equity_btc(mT) * ST == pytest.approx(F0, rel=1e-12)


def test_synthetic_dollar_constant_usd():
    S0 = 100_000.0
    a = Account(Costs(0, 0))
    m0 = mkt(T0, S0)
    a.deposit_usd(T0, S0, S0)
    a.trade_linear(T0, m0, "hedge", PERP, -S0)
    for k, S in enumerate([60_000.0, 150_000.0, 99_000.0]):
        m = mkt(T0 + pd.Timedelta(hours=k + 1), S)
        a.settle_linear(m.t, m)
        assert a.equity_btc(m) * S == pytest.approx(S0, rel=1e-12)
        assert a.delta_btc(m) == pytest.approx(0.0, abs=1e-12)


@pytest.mark.parametrize("ST", [30_000.0, 100_000.0, 250_000.0])
def test_box_pays_strike_width_usd(ST):
    S0, F0, K1, K2 = 100_000.0, 102_000.0, 90_000.0, 110_000.0
    a = Account(Costs(0, 0))
    m0 = mkt(T0, S0, F0, options=chain(T0, S0, F0, [K1, K2]))
    for key, q in [((EXP, K1, True), 1), ((EXP, K2, True), -1), ((EXP, K1, False), -1), ((EXP, K2, False), 1)]:
        assert a.trade_option(T0, m0, "strategy", key, q) is not None
    premium = -a.balance
    mT = mkt(EXP, ST, ST)
    a.expire(EXP, mT)
    assert (a.balance + premium) * ST == pytest.approx(K2 - K1, rel=1e-12)
    # fair box price = (K2-K1)/F0 BTC (parity), i.e. the futures-implied USD rate
    assert premium == pytest.approx((K2 - K1) / F0, rel=1e-9)


@pytest.mark.parametrize("ST", [30_000.0, 100_000.0, 250_000.0])
def test_conversion_locks_F0_minus_K_usd(ST):
    S0, F0, K = 100_000.0, 102_000.0, 95_000.0
    a = Account(Costs(0, 0))
    m0 = mkt(T0, S0, F0, options=chain(T0, S0, F0, [K]))
    a.trade_option(T0, m0, "strategy", (EXP, K, True), 1)
    a.trade_option(T0, m0, "strategy", (EXP, K, False), -1)
    premium = -a.balance
    a.trade_linear(T0, m0, "strategy", FUT, -F0, expiry=EXP)
    mT = mkt(EXP, ST, ST)
    a.settle_linear(EXP, mT)
    a.expire(EXP, mT)
    assert (a.balance + premium) * ST == pytest.approx(F0 - K, rel=1e-9)
    assert premium == pytest.approx(1 - K / F0, rel=1e-9)  # parity C - P = 1 - K/F


def test_costs_accounting():
    S0, F0 = 100_000.0, 101_000.0
    a = Account(Costs(10, 4))
    m0 = mkt(T0, S0, F0, options=chain(T0, S0, F0, [100_000.0]))
    a.trade_linear(T0, m0, "strategy", FUT, -50_000.0, expiry=EXP)
    a.trade_option(T0, m0, "strategy", (EXP, 100_000.0, True), -2)
    led = pd.DataFrame(a.ledger, columns=["t", "book", "kind", "btc", "usd"])
    cost = led.loc[led["kind"] == "cost", "btc"].sum()
    assert cost == pytest.approx(-(4e-4 * 50_000.0 / F0 + 2 * 1e-3), rel=1e-12)


@pytest.mark.parametrize("K,is_call", [(90_000.0, True), (110_000.0, False), (100_000.0, True)])
def test_option_delta_matches_bump(K, is_call):
    S0, b = 100_000.0, 0.05
    t = T0
    F0 = S0 * np.exp(b * TAU)

    def usd_value(S):
        F = S * np.exp(b * TAU)
        m = mkt(t, S, F, options=chain(t, S, F, [K]))
        a = Account(Costs(0, 0))
        a.opts[("strategy", EXP, K, is_call)] = 3.0
        return a.equity_btc(m) * S, a, m
    h = 1.0
    up, _, _ = usd_value(S0 + h)
    dn, _, _ = usd_value(S0 - h)
    _, a, m = usd_value(S0)
    assert a.delta_btc(m) == pytest.approx((up - dn) / (2 * h), rel=1e-4)


def test_funding_paid_by_longs():
    S0 = 100_000.0
    a = Account(Costs(0, 0))
    m0 = mkt(T0, S0)
    a.trade_linear(T0, m0, "hedge", PERP, -S0)        # short 1 BTC worth
    m1 = mkt(T0 + pd.Timedelta(hours=1), S0, funding=1e-5)
    a.accrue_funding(m1.t, m1)
    assert a.balance == pytest.approx(1e-5, rel=1e-12)  # short receives N * f / S BTC
