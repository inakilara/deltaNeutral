"""Inverse (BTC-settled) option pricing used for deltas and checks.

Deribit BTC option price (BTC per 1 BTC underlying) = undiscounted Black-76 USD price on the expiry forward F,
divided by F (consistent with inverse parity C - P = 1 - K/F, checked on the data to ~5e-5 BTC).

USD value of one contract = price_btc * S. With F = S * exp(b*tau), d(USD value)/dS = N(d1) for a call and
N(d1) - 1 for a put: the USD delta in BTC units, the same as a linear option.
"""
import numpy as np
from scipy.special import ndtr


def d1(F, K, sigma, tau):
    s = sigma * np.sqrt(np.maximum(tau, 1e-12))
    return (np.log(F / K) + 0.5 * s * s) / s


def price_btc(F, K, sigma, tau, is_call):
    F, K, sigma, tau = (np.asarray(x, float) for x in (F, K, sigma, tau))
    is_call = np.asarray(is_call, bool)
    s = sigma * np.sqrt(np.maximum(tau, 1e-12))
    a = (np.log(F / K) + 0.5 * s * s) / s
    b = a - s
    call = F * ndtr(a) - K * ndtr(b)
    usd = np.where(is_call, call, call - F + K)
    return usd / F


def delta_usd(F, K, sigma, tau, is_call):
    """dV_usd/dS per contract (BTC units): N(d1) call, N(d1)-1 put."""
    n = ndtr(d1(np.asarray(F, float), np.asarray(K, float), np.asarray(sigma, float), np.asarray(tau, float)))
    return np.where(np.asarray(is_call, bool), n, n - 1.0)


def vega_usd(F, K, sigma, tau):
    """dV_usd/dsigma per contract (USD per 1.00 of vol), Black-76 undiscounted: F phi(d1) sqrt(tau)."""
    F, K, sigma, tau = (np.asarray(x, float) for x in (F, K, sigma, tau))
    x = d1(F, K, sigma, tau)
    return F * np.exp(-0.5 * x * x) / np.sqrt(2 * np.pi) * np.sqrt(np.maximum(tau, 1e-12))


def payoff_btc(S, K, is_call):
    S, K = np.asarray(S, float), np.asarray(K, float)
    return np.where(np.asarray(is_call, bool), np.maximum(S - K, 0.0), np.maximum(K - S, 0.0)) / S
