# deltaNeutral

Study of yield-like strategies with low or no market risk (carry, arbitrage, delta-neutral premium) on Deribit's
BTC inverse instruments: options, dated futures and the perpetual. Backtested on hourly history.

Start with [documents/README.md](documents/README.md): plan, idea catalogue, backtest framework, test designs and
data notes.

Data is read in place from the shared, read-only `C:\ClaudeSandbox\shared-data\` (option chain, Deribit futures and
funding). Derived panels go to `data/cache/` (git-ignored).
