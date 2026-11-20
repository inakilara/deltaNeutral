"""Phase 3: option-parity opportunity scan over the full chain (B5, B1, B2, B4).

    python scripts/run_phase3_scan.py          # scan -> reports/phase3/*.parquet (about 10-20 min)
    python scripts/run_phase3_report.py        # tables -> reports/phase3/*.csv

Everything is built from the parity deviation of each two-sided call/put pair at strike K:
    d = (C_mid - P_mid) - (1 - K/F)          [BTC per 1 BTC underlying; x 1e4 = bps of underlying]
F is the chain's underlyingPrice (the future's mark for expiries with a listed future, Deribit's synthetic
forward otherwise). Deribit marks satisfy d = 0 exactly; bid/ask mids do not.

Edges (BTC per contract, USD-locked at expiry once hedged: USD edge = edge x F):
    conversion (long C, short P, short future N = F):   -d - 2 x 0.001 - 0.0004
    reversal   (the mirror):                             d - 2 x 0.001 - 0.0004
    box (long/short, strikes K1 != K2, no future):       d(Ki) - d(Kj) - 4 x 0.001
'quoted' variants use the actual bid/ask instead of mid +- 0.001 (futures still +-4 bps).
B4 checks adjacent strikes per expiry and option type: monotonicity, vertical bound (K2-K1)/F, butterfly >= 0.
"""
import os
import sys
import time
import warnings

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from dn import data  # noqa: E402

warnings.filterwarnings("ignore")
OUT = os.path.join(ROOT, "reports", "phase3")
OPT, FUT = 0.001, 0.0004
MIN_DAYS = 1.0
SPREAD_CAP = 0.005  # mid +- 0.001 only for legs quoted with bid-ask <= 50 bps of underlying; wider mids are noise
H = pd.Timedelta(hours=1)
NS = "datetime64[ns, UTC]"


def listed_futures():
    f = data.load_futures()
    f = f[f["price"].notna()] if "price" in f else f
    return set(zip(f["t"].astype(NS), f["expiry"].astype(NS)))


def pairs(d, listed):
    d = d[(d["bid"] > 0) & (d["ask"] > 0)]
    key = ["t", "expiry", "strike"]
    c = d[d["is_call"]][key + ["bid", "ask", "bid_size", "ask_size", "F", "index"]]
    p = d[~d["is_call"]][key + ["bid", "ask", "bid_size", "ask_size"]]
    m = c.merge(p, on=key, suffixes=("_c", "_p"))
    m["days"] = (m["expiry"] - m["t"]).dt.total_seconds() / 86400
    m = m[m["days"] >= MIN_DAYS].copy()
    m["lm"] = np.log(m["strike"] / m["F"])
    m["fair"] = 1 - m["strike"] / m["F"]
    tight = ((m["ask_c"] - m["bid_c"]) <= SPREAD_CAP) & ((m["ask_p"] - m["bid_p"]) <= SPREAD_CAP)
    m["d"] = ((m["bid_c"] + m["ask_c"]) / 2 - (m["bid_p"] + m["ask_p"]) / 2 - m["fair"]).where(tight)
    m["cq"] = m["fair"] - (m["ask_c"] - m["bid_p"])  # conversion at quotes, option legs only
    m["rq"] = (m["bid_c"] - m["ask_p"]) - m["fair"]  # reversal at quotes, option legs only
    m["size_conv"] = np.minimum(m["ask_size_c"], m["bid_size_p"])
    m["size_rev"] = np.minimum(m["bid_size_c"], m["ask_size_p"])
    m = m.sort_values(["expiry", "strike", "t"])
    g = m.groupby(["expiry", "strike"], sort=False)
    ok = (g["t"].shift(-1) - m["t"]) == H
    for col in ("d", "cq", "rq"):
        m[col + "_next"] = g[col].shift(-1).where(ok)
    m["listed"] = [k in listed for k in zip(m["t"].astype(NS), m["expiry"].astype(NS))]
    return m


def b5(m):
    x = m[(m["lm"].abs() <= 0.10) & m["d"].notna()].copy()
    x["F_impl"] = x["strike"] / (1 - x["fair"] - x["d"])
    g = x.groupby(["t", "expiry"])
    out = g.agg(F=("F", "first"), S=("index", "first"), days=("days", "first"), listed=("listed", "first"),
                F_impl=("F_impl", "median"), n=("strike", "size")).reset_index()
    out["dev_bps"] = (out["F_impl"] / out["F"] - 1) * 1e4
    tau = out["days"] / 365.25
    out["rate_impl"] = np.log(out["F_impl"] / out["S"]) / tau
    out["rate_fut"] = np.log(out["F"] / out["S"]) / tau
    return out


def b1(m):
    x = m[m["listed"] & (m["lm"].abs() <= 0.20)].copy()
    conv_a, rev_a = -x["d"] - 2 * OPT - FUT, x["d"] - 2 * OPT - FUT
    conv_an, rev_an = -x["d_next"] - 2 * OPT - FUT, x["d_next"] - 2 * OPT - FUT
    x["edge_a"] = np.maximum(conv_a, rev_a)
    x["side_a"] = np.where(conv_a >= rev_a, "conv", "rev")
    x["edge_a_next"] = np.where(conv_a >= rev_a, conv_an, rev_an)
    cq, rq = x["cq"] - FUT, x["rq"] - FUT
    x["edge_q"] = np.maximum(cq, rq)
    x["side_q"] = np.where(cq >= rq, "conv", "rev")
    x["edge_q_next"] = np.where(cq >= rq, x["cq_next"] - FUT, x["rq_next"] - FUT)
    x["size_q"] = np.where(cq >= rq, x["size_conv"], x["size_rev"])
    x["pos_a"] = x["edge_a"] > 0
    x["pos_q"] = x["edge_q"] > 0
    g = x.groupby(["t", "expiry"])
    base = g.agg(days=("days", "first"), F=("F", "first"), n=("strike", "size"), n_pos_a=("pos_a", "sum"),
                 n_pos_q=("pos_q", "sum"))
    xa = x[x["d"].notna()]
    ia = xa.loc[xa.groupby(["t", "expiry"])["edge_a"].idxmax(),
                ["t", "expiry", "strike", "edge_a", "side_a", "edge_a_next", "d"]]
    iq = x.loc[g["edge_q"].idxmax(), ["t", "expiry", "strike", "edge_q", "side_q", "edge_q_next", "size_q"]]
    ia = ia.rename(columns={"strike": "K_a"}).set_index(["t", "expiry"])
    iq = iq.rename(columns={"strike": "K_q"}).set_index(["t", "expiry"])
    return base.join(ia).join(iq).reset_index()


def _top2(x, col, ascending=False):
    s = x.sort_values(["t", "expiry", col], ascending=[True, True, ascending])
    s["r"] = s.groupby(["t", "expiry"]).cumcount()
    s = s[s["r"] < 2].set_index(["t", "expiry", "r"])[[col, "strike", col + "_n"]]
    return s.unstack("r")


def b2(m):
    x = m[m["lm"].abs() <= 0.25].copy()
    g = x.groupby(["t", "expiry"])
    base = g.agg(days=("days", "first"), F=("F", "first"), listed=("listed", "first"), n=("strike", "size"))
    base = base[base["n"] >= 2]
    # mid +- 0.001 (tight legs only): edge = max d - min d - 4 x 0.001
    xa = x[x["d"].notna()]
    ga = xa.groupby(["t", "expiry"])
    hi = xa.loc[ga["d"].idxmax(), ["t", "expiry", "strike", "d", "d_next"]].set_index(["t", "expiry"])
    lo = xa.loc[ga["d"].idxmin(), ["t", "expiry", "strike", "d", "d_next"]].set_index(["t", "expiry"])
    base["edge_a"] = hi["d"] - lo["d"] - 4 * OPT
    base["edge_a_next"] = hi["d_next"] - lo["d_next"] - 4 * OPT
    base["width_a"] = (hi["strike"] - lo["strike"]).abs()
    # quoted: best conversion-leg at Ki + reversal-leg at Kj, i != j (a long or short box)
    x["cq_n"], x["rq_n"] = x["cq_next"], x["rq_next"]
    c2 = _top2(x, "cq")
    c2.columns = ["%s%d" % (a, b) for a, b in c2.columns]
    r2 = _top2(x, "rq")
    r2.columns = ["%s%d" % (a.replace("strike", "rstrike"), b) for a, b in r2.columns]
    j = c2.join(r2, how="inner")
    same = j["strike0"] == j["rstrike0"]
    alt1 = j["cq0"] + j["rq1"]  # keep best conversion leg, second-best reversal leg
    alt2 = j["cq1"] + j["rq0"]
    use1 = alt1.fillna(-np.inf) >= alt2.fillna(-np.inf)
    edge = np.where(~same, j["cq0"] + j["rq0"], np.where(use1, alt1, alt2))
    nxt = np.where(~same, j["cq_n0"] + j["rq_n0"], np.where(use1, j["cq_n0"] + j["rq_n1"], j["cq_n1"] + j["rq_n0"]))
    Kc = np.where(~same | use1, j["strike0"], j["strike1"])
    Kr = np.where(~same, j["rstrike0"], np.where(use1, j["rstrike1"], j["rstrike0"]))
    q = pd.DataFrame({"edge_q": edge, "edge_q_next": nxt, "width_q": np.abs(Kr - Kc)}, index=j.index)
    return base.join(q).reset_index()


def b4(d):
    d = d[(d["bid"] > 0) & (d["ask"] > 0)].copy()
    d["days"] = (d["expiry"] - d["t"]).dt.total_seconds() / 86400
    d = d[d["days"] >= MIN_DAYS].sort_values(["t", "expiry", "is_call", "strike"])
    d["mid"] = ((d["bid"] + d["ask"]) / 2).where((d["ask"] - d["bid"]) <= SPREAD_CAP)  # mids of tight quotes only
    g = d.groupby(["t", "expiry", "is_call"], sort=False)
    K1, K2, K3 = d["strike"], g["strike"].shift(-1), g["strike"].shift(-2)
    m1, m2, m3 = d["mid"], g["mid"].shift(-1), g["mid"].shift(-2)
    b1_, a1 = d["bid"], d["ask"]
    b2_, a2 = g["bid"].shift(-1), g["ask"].shift(-1)
    a3 = g["ask"].shift(-2)
    call = d["is_call"]
    width = (K2 - K1) / d["F"]
    rows = {}
    # monotonicity: call price falls with K, put price rises with K
    rows["mono_a"] = np.where(call, m2 - m1, m1 - m2) - 2 * OPT
    rows["mono_q"] = np.where(call, b2_ - a1, b1_ - a2)
    # vertical bound: |price difference| <= (K2-K1)/F
    rows["vert_a"] = np.where(call, m1 - m2, m2 - m1) - width - 2 * OPT
    rows["vert_q"] = np.where(call, b1_ - a2, b2_ - a1) - width
    # butterfly on K1<K2<K3: w P(K1) + (1-w) P(K3) >= P(K2)
    w = (K3 - K2) / (K3 - K1)
    rows["fly_a"] = m2 - (w * m1 + (1 - w) * m3) - 2 * OPT
    rows["fly_q"] = b2_ - (w * a1 + (1 - w) * a3)
    out = d[["t", "expiry", "is_call", "strike", "days", "F", "bid_size", "ask_size"]].copy()
    for k, v in rows.items():
        out[k] = np.asarray(v, dtype=float)
    cols = list(rows)
    keep = (out[cols] > 0).any(axis=1)
    n_checked = d.groupby("t").size()
    return out[keep], n_checked


def main(limit=None):
    os.makedirs(OUT, exist_ok=True)
    listed = listed_futures()
    res = {k: [] for k in ("b5", "b1", "b2", "b4", "b4n")}
    t0 = time.time()
    for n, d in enumerate(data.ChainReader().batches()):
        m = pairs(d, listed)
        res["b5"].append(b5(m))
        res["b1"].append(b1(m))
        res["b2"].append(b2(m))
        v, nc = b4(d)
        res["b4"].append(v)
        res["b4n"].append(nc.rename("n_checked").reset_index())
        print("batch %2d  %s .. %s  pairs %8d  (%.0fs)" % (n, d["t"].min(), d["t"].max(), len(m), time.time() - t0),
              flush=True)
        if limit and n + 1 >= limit:
            break
    for k, v in res.items():
        pd.concat(v, ignore_index=True).to_parquet(os.path.join(OUT, "%s.parquet" % k), index=False)
    print("done (%.0fs)" % (time.time() - t0))


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else None)
