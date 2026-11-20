"""Phase 4: option risk-premium overlays (C1 short straddle, C2 IV calendar, C3 skew), delta-hedged on the A2
synthetic-dollar collateral. Runs with an existing result file are skipped.

    python scripts/run_phase4.py 0/4      # shard 0 of 4 (run shards in parallel) -> reports/phase4/<run>.*
    python scripts/run_phase4.py report   # combine -> reports/phase4/summary.csv, by_year.csv, crashes.csv
"""
import json
import os
import sys
import time
import warnings

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from dn import engine, metrics  # noqa: E402
from dn.hedger import PerpPolicy  # noqa: E402
from strategies.options import Rolling, ShortStraddle, build_calendar, build_skew  # noqa: E402

warnings.filterwarnings("ignore")
OUT = os.path.join(ROOT, "reports", "phase4")
CAP = 1e6
START, END = "2019-12-01", "2026-10-25"  # option-chain coverage
CRASHES = {"2020-03 covid": ("2020-03-08", "2020-03-20"), "2021-05 china ban": ("2021-05-10", "2021-05-25"),
           "2022-06 luna/3ac": ("2022-06-10", "2022-06-20"), "2022-11 ftx": ("2022-11-06", "2022-11-15")}


def runs(index):
    yield "A2 baseline (chain window)", dict(strategy=None, band_frac=0.0025, use_options=False)
    for d in (7, 14, 30):
        for band in (0.02, 0.05, 0.10):
            yield "C1 straddle %dd band %d%%" % (d, 100 * band), dict(
                strategy=ShortStraddle(CAP, d, index=index), band_frac=band)
    yield "C1 straddle 7d band 5% close 1d before", dict(
        strategy=ShortStraddle(CAP, 7, close_days=1.0, index=index), band_frac=0.05)
    for vf in (0.05, 0.10):
        yield "C1 straddle 30d band 5%% IV-RV>%d" % (100 * vf), dict(
            strategy=ShortStraddle(CAP, 30, vol_filter=vf, index=index), band_frac=0.05)
    for band in (0.05, 0.10):
        yield "C2 calendar 10d-45d band %d%%" % (100 * band), dict(
            strategy=Rolling("C2", build_calendar, CAP), band_frac=band)
        yield "C3 short 25d risk reversal 30d band %d%%" % (100 * band), dict(
            strategy=Rolling("C3 rr", build_skew, CAP, kind="rr"), band_frac=band)
        yield "C3 short 25d wings (fly) 30d band %d%%" % (100 * band), dict(
            strategy=Rolling("C3 fly", build_skew, CAP, kind="fly"), band_frac=band)


def fname(name):
    return name.replace(" ", "_").replace("/", "-").replace("%", "pct").replace(">", "gt").replace("(", "").replace(
        ")", "")


def split(res):
    """USD P&L by component, per year of capital: option premium+settlement (realised), option MTM at end, hedge
    linear P&L, hedge funding, costs per book."""
    led = res["ledger"]
    led = led[led["kind"] != "deposit"]
    years = (res["hist"].index[-1] - res["hist"].index[0]).total_seconds() / (365.25 * 86400)
    g = led.groupby(led["book"] + ":" + led["kind"])["usd"].sum() / CAP / years
    acct, h = res["account"], res["hist"]
    return g.to_dict()


def run_shard(i, n):
    os.makedirs(OUT, exist_ok=True)
    perp, _ = engine.market_data()
    for k, (name, kw) in enumerate(runs(perp["index"])):
        if k % n != i or os.path.exists(os.path.join(OUT, fname(name) + ".json")):
            continue  # not this shard, or already done
        t0 = time.time()
        st = kw.pop("strategy")
        res = engine.run(st, PerpPolicy(), START, END, capital_usd=CAP, verbose=False,
                         use_options=kw.pop("use_options", True), **kw)
        s = metrics.summary(res)
        s["max_margin_ratio"] = float(res["hist"]["margin_ratio"].max())
        s["pnl_split"] = split(res)
        e = metrics.daily(res)
        s["crashes"] = {c: float(e.loc[a:b].iloc[-1] / e.loc[:a].iloc[-1] - 1) for c, (a, b) in CRASHES.items()}
        f = fname(name)
        with open(os.path.join(OUT, f + ".json"), "w") as fh:
            json.dump({"name": name, **s}, fh, indent=1, default=float)
        metrics.by_year(res).to_csv(os.path.join(OUT, f + "_years.csv"))
        e.to_csv(os.path.join(OUT, f + "_equity.csv"))
        if st is not None and getattr(st, "entries", None):
            pd.DataFrame(st.entries).to_csv(os.path.join(OUT, f + "_entries.csv"), index=False)
        print("%-42s ann %6.2f%%  vol %5.2f%%  maxDD %6.2f%%  margin %.2f  (%.0fs)" % (
            name, 100 * s["ann_return"], 100 * s["ann_vol"], 100 * s["max_drawdown"], s["max_margin_ratio"],
            time.time() - t0), flush=True)


def report():
    rows, years, crashes, splits = {}, {}, {}, {}
    for f in sorted(os.listdir(OUT)):
        if not f.endswith(".json"):
            continue
        s = json.load(open(os.path.join(OUT, f)))
        name = s.pop("name")
        crashes[name] = s.pop("crashes")
        splits[name] = s.pop("pnl_split")
        rows[name] = s
        years[name] = pd.read_csv(os.path.join(OUT, f[:-5] + "_years.csv"), index_col=0)["return_ann"]
    pd.set_option("display.width", 250)
    for nm, df in (("summary", pd.DataFrame(rows).T), ("by_year", pd.DataFrame(years).T),
                   ("crashes", pd.DataFrame(crashes).T), ("pnl_split", pd.DataFrame(splits).T.fillna(0.0))):
        df.to_csv(os.path.join(OUT, nm + ".csv"))
        print("\n== %s" % nm)
        num = df.apply(pd.to_numeric, errors="coerce")
        print(num.round(4).to_string())


if __name__ == "__main__":
    if sys.argv[1] == "report":
        report()
    else:
        i, n = map(int, sys.argv[1].split("/"))
        run_shard(i, n)
