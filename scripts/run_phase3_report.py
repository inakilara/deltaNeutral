"""Phase 3 tables from the parity scan (reports/phase3/*.parquet -> reports/phase3/*.csv, printed).

Opportunity statistics per year:
    obs          expiry-hours scanned (B1: listed-future expiries only)
    pos          share of expiry-hours with a positive edge after costs
    hours_pos    share of chain hours with at least one positive edge
    edge_bps     median edge when positive (bps of underlying)
    survive_1h   share of positive edges still positive one hour later at the same strikes (quoted: at that hour's quotes)
    episodes     runs of consecutive positive hours on the same expiry (counted once)
    yield_ub     upper bound: every episode traded once at its entry edge on its quoted size (B1 quoted only, where
                 sizes exist), USD edge / USD 1M capital per year. Ignores margin and execution risk.
"""
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "reports", "phase3")
CAP = 1e6
H = pd.Timedelta(hours=1)


def tenor(days):
    return pd.cut(days, [0, 7, 30, 90, 400], labels=["1-7d", "7-30d", "30-90d", "90d+"], right=False)


def episodes(df, edge):
    """Rows (t, expiry) with edge > 0; a new episode starts when the previous positive hour of that expiry is not t-1h."""
    p = df[df[edge] > 0].sort_values(["expiry", "t"])
    new = (p.groupby("expiry")["t"].diff() != H)
    return p[new.values]


def opp_table(df, edge, nxt, hours_per_year):
    df = df[df[edge].notna()].copy()
    df["year"] = df["t"].dt.year
    rows = {}
    for y, g in df.groupby("year"):
        pos = g[g[edge] > 0]
        ep = episodes(g, edge)
        rows[y] = {
            "obs": len(g),
            "pos": len(pos) / len(g),
            "hours_pos": pos["t"].nunique() / hours_per_year.get(y, np.nan),
            "edge_bps": 1e4 * pos[edge].median() if len(pos) else np.nan,
            "edge_bps_q90": 1e4 * pos[edge].quantile(0.9) if len(pos) else np.nan,
            "survive_1h": (pos[nxt] > 0).mean() if len(pos) else np.nan,
            "episodes": len(ep),
        }
    return pd.DataFrame(rows).T


def main():
    b5 = pd.read_parquet(os.path.join(OUT, "b5.parquet"))
    b1 = pd.read_parquet(os.path.join(OUT, "b1.parquet"))
    b2 = pd.read_parquet(os.path.join(OUT, "b2.parquet"))
    b4 = pd.read_parquet(os.path.join(OUT, "b4.parquet"))
    b4n = pd.read_parquet(os.path.join(OUT, "b4n.parquet"))
    hpy = b4n.groupby(b4n["t"].dt.year)["t"].nunique().to_dict()
    pd.set_option("display.width", 250)
    out = {}

    # B5: implied forward (tight call/put mids, |ln K/F| <= 10%, median per expiry-hour) vs the chain forward F
    b5["year"], b5["tenor"] = b5["t"].dt.year, tenor(b5["days"])
    b5["absdev"] = b5["dev_bps"].abs()
    b5["rate_gap_bps"] = 1e4 * (b5["rate_impl"] - b5["rate_fut"])
    t = b5.groupby(["listed", "tenor", "year"], observed=True).agg(
        n=("dev_bps", "size"), dev_med=("dev_bps", "median"), absdev_med=("absdev", "median"),
        absdev_q90=("absdev", lambda s: s.quantile(0.9)), rate_gap_med_bps=("rate_gap_bps", "median"))
    out["b5_by_tenor_year"] = t
    # persistence: autocorrelation of the deviation of one expiry from hour to hour
    s = b5.sort_values(["expiry", "t"])
    g = s.groupby("expiry")
    ok = (g["t"].diff() == H)
    lag = g["dev_bps"].shift(1)
    out["b5_persistence"] = pd.DataFrame({"ac1": [s.loc[ok, "dev_bps"].corr(lag[ok])], "n": [ok.sum()]})

    # B1 conversion / reversal (listed-future expiries)
    out["b1_mid"] = opp_table(b1, "edge_a", "edge_a_next", hpy)
    q = opp_table(b1, "edge_q", "edge_q_next", hpy)
    b1["year"] = b1["t"].dt.year
    ep = episodes(b1, "edge_q")
    ep = ep.assign(usd=ep["edge_q"] * ep["F"] * ep["size_q"], year=ep["t"].dt.year)
    q["size_med"] = ep.groupby("year")["size_q"].median()
    q["usd_edge"] = ep.groupby("year")["usd"].sum()
    q["yield_ub"] = q["usd_edge"] / CAP
    # one-hour delay: the opportunity seen at t is executed at t+1 quotes (only when still positive)
    ep = ep.assign(usd_next=ep["edge_q_next"].clip(lower=0).fillna(0) * ep["F"] * ep["size_q"])
    q["usd_edge_delayed"] = ep.groupby("year")["usd_next"].sum()
    q["yield_ub_delayed"] = q["usd_edge_delayed"] / CAP
    q["share_at_0800"] = ep.groupby("year")["t"].apply(lambda s: (s.dt.hour == 8).mean())
    out["b1_quoted"] = q

    # B2 box (all expiries)
    b2 = b2[b2["n"] >= 2]
    out["b2_mid"] = opp_table(b2[b2["width_a"] > 0], "edge_a", "edge_a_next", hpy)
    out["b2_quoted"] = opp_table(b2, "edge_q", "edge_q_next", hpy)

    # B4 static checks
    b4["year"] = b4["t"].dt.year
    rows = {}
    for y, g in b4.groupby("year"):
        r = {}
        for c in ("mono_a", "vert_a", "fly_a", "mono_q", "vert_q", "fly_q"):
            v = g[g[c] > 0]
            r[c + "_hours"] = v["t"].nunique() / hpy.get(y, np.nan)
            r[c + "_n"] = len(v)
            r[c + "_bps"] = 1e4 * v[c].median() if len(v) else np.nan
        rows[y] = r
    out["b4"] = pd.DataFrame(rows).T

    for k, v in out.items():
        v.to_csv(os.path.join(OUT, k + ".csv"))
        print("\n== %s" % k)
        print(v.round(4).to_string())


if __name__ == "__main__":
    main()
