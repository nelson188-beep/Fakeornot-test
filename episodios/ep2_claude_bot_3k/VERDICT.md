# Verdict — Claude bot "$3K/month" claim

**Fake or Not: Not supported (misleading).**

On $10,000 paper capital, the guide's rules (daily-bar approximation) **lost money** and hit the **10% drawdown kill switch** in both windows:

| Window | Bot | SPY buy&hold | Trades | Win rate | Kill switch |
|--------|-----|--------------|--------|----------|-------------|
| Last ~6 months (2026-04-07 → 2026-10-07) | **−10.0%** (−$1,002) | **+19.2%** | 13 | 7.7% | 2026-06-02 (~56 days) |
| 2019-01-01 → 2026-10-07 | **−6.9%** (−$685) | **+254.9%** | 31 | 22.6% | 2019-07-02 (~182 days) |

After the kill switch, the bot held cash. The long-window calendar return is mostly "stopped early," not seven years of alpha.

**$3K/month math:** at this strategy's average monthly P&L, capital required is **n/a** (negative edge). Even buy-and-hold SPY over 2019–2026 averaged ~$274/month on $10k — you'd need on the order of **~$110k in SPY** for $3k/month at that historical rate, not a $10k bot.

**Main drag:** daily mean-reversion shorts on SPY/QQQ in uptrends (guide specified 15-minute bars; free history forced daily — stated in methods.md). Trend sleeves barely traded (rare 50/200 crosses). BTC long-only was roughly flat.

See `methods.md`, `results/summary.json`, `charts/*.png`.
