"""Performance metrics in USD from an engine result."""
import numpy as np
import pandas as pd

DAYS_YEAR = 365.25


def daily(res):
    return res["hist"]["equity_usd"].resample("1D").last().dropna()


def summary(res):
    e = daily(res)
    r = e.pct_change().dropna()
    years = (e.index[-1] - e.index[0]).days / DAYS_YEAR
    dd = e / e.cummax() - 1
    led = res["ledger"]
    led = led[led["kind"] != "deposit"]
    cost = -led.loc[led["kind"] == "cost", "usd"].sum()
    return {"start": str(e.index[0].date()), "end": str(e.index[-1].date()), "years": round(years, 2),
            "ann_return": (e.iloc[-1] / e.iloc[0]) ** (1 / years) - 1,
            "ann_vol": r.std() * np.sqrt(DAYS_YEAR), "sharpe": r.mean() / r.std() * np.sqrt(DAYS_YEAR) if r.std() > 0 else np.nan,
            "max_drawdown": dd.min(), "worst_day": r.min(), "worst_week": e.resample("7D").last().pct_change().min(),
            "costs_usd_per_year_pct": cost / res["capital_usd"] / years,
            "max_abs_delta_pct": (res["hist"]["delta_usd"].abs() / res["hist"]["equity_usd"]).max(),
            "corr_daily_vs_btc": r.corr(res["hist"]["S"].resample("1D").last().pct_change().reindex(r.index)),
            "hedger_trades": res["hedger_trades"]}


def by_year(res):
    e = daily(res)
    y = e.groupby(e.index.year)
    base = y.last().shift(1).fillna(e.iloc[0])  # previous year's close (first year: the start)
    out = pd.DataFrame({"return": y.last() / base - 1, "days": y.size()})
    # cash flows that are P&L components on their own (USD at the time of the flow, / capital)
    led = res["ledger"]
    led = led[led["kind"].isin(["funding", "cost"])]
    led_y = led.groupby([led["t"].dt.year, led["book"] + "_" + led["kind"]])["usd"].sum().unstack(fill_value=0.0)
    out = out.join((led_y / res["capital_usd"]).add_prefix("flow_"), how="left")
    out["return_ann"] = (1 + out["return"]) ** (DAYS_YEAR / out["days"]) - 1
    return out
