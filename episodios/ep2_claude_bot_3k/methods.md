# Fake or Not — Claude $3K/month bot (paper backtest)

Claim source: Instagram @hypertech carousel + Ray Fu guide
https://www.raycfu.com/guides/claude-fable-trading-bot

## Faithfulness vs guide

| Guide | This test |
|-------|-----------|
| SPY/QQQ mean reversion on **15-min** bars | **Daily** bars (free 15-min only ~60 days) |
| BTC momentum on **1-hour** | **Daily** (Yahoo BTC-USD; Binance.com blocked 451 from this network) |
| GLD/USO trend on **4-hour** 50/200 EMA | **Daily** 50/200 EMA (standard trend timeframe; free 4h not stored) |
| BTC "go short" on breakdown | **Long-only + exit** (Alpaca crypto is not shortable; matches live constraint) |
| Slippage 0.05%, commission $0 | Stocks/ETFs **0.01% per side** (~0.02% RT incl. spread); BTC **0.25% taker per side** |
| 6 months of Alpaca history | (a) last ~6 months to 2026-10-07; (b) 2019-01-01 → 2026-10-07 |

## Rules implemented

- Mean reversion SPY (k=1.5) / QQQ (k=1.8): long if close < SMA20 − k·std20; short if close > SMA20 + k·std20; exit when close crosses back to SMA20.
- BTC momentum: long if close > prior 20-day high AND volume ≥ 1.5× SMA20(volume); exit if close < prior 20-day low (same vol filter) OR trailing stop 2×ATR14.
- GLD/USO trend: long on 50 EMA cross above 200 EMA; reverse/exit on cross below; trailing stop 3×ATR14.
- Position size: shares = (1% equity) / ATR14; hard stop at entry ± 1×ATR14 (1% equity risk).
- Correlation filter: no new BTC long if SPY and QQQ are both currently long.
- Kill switch: if equity ≤ 90% of peak, flatten all and stop trading.
- Signal on day t close → fill at day t+1 open (cost applied). Stops checked vs day high/low.

Starting capital: $10,000. Benchmark: buy-and-hold SPY, same start date, same costs on initial buy.
