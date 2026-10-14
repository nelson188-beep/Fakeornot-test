# Fake or Not #3: methods (Polymarket "50/50" claims)

Data pulled Oct 10, 2026 (about 8:15 to 8:30 AM CT). Public data only; no account, no wallet, no money.

## Sources of the claims (X)
- Post A, Oct 9, 2026 04:22 AM CT: https://x.com/PolyDekos/status/2108488365762875870 ("He buys Bitcoin Up or Down contracts at 41-59¢ and closes them at $1. In just 2 months of trading, he earned $93,771.04 ... Math: $93.8K / $5.2M ≈ 1.8% of trading volume ≈ $5.2 average profit per trade"). Links to polymarket.com/@fairvaluemachine?via=OsnO.
- Post B, Oct 8, 2026 12:04 PM CT: https://x.com/PolyDekos/status/2108242171245797486 ("The most extreme strategy in crypto made this guy $85,676.80 ... A single $55 trade brought in over 62% of his total profit"). Links to polymarket.com/@hellsangelx?via=OsnO.
- Raw JSON: raw/x_polydekos_posts.json (x connector, search_posts_all from:PolyDekos). Screenshots attached to the posts: raw/x_fvm_post_img.jpg, raw/x_hell_post_img.jpg.
- Note: the X account @hellsangelx is unrelated to the Polymarket user "HellsAngelx". The source is the @PolyDekos post.

## Handle → wallet (public)
- gamma-api.polymarket.com/public-search?q=<name>&search_profiles=true
- Trader A (FairValueMachine): proxy wallet 0xd84403efd50b49a1d8a7181627e00307e6ea5908
- Trader B (HellsAngelx): proxy wallet 0x8ff04326388b1c024c45d7a7ffdd12cdedd0a0ed

## Wallet data (analyze_wallets.py → results/wallets_summary.json)
- Profile stats (headline PnL, volume, markets traded, join date, taker rebates): the user-stats block embedded in polymarket.com/@<name> (raw/pm_profile_*.html).
- Leaderboard: data-api.polymarket.com/v1/leaderboard?timePeriod=ALL|MONTH&orderBy=PNL&user=<wallet> (data/lb_*.json).
- Profile PnL chart: user-pnl-api.polymarket.com/user-pnl?user_address=<wallet>&interval=all&fidelity=1d (data/pnl_daily_*.json).
- Per-market positions: data-api.polymarket.com/closed-positions (fetch_closed.py, all pages) and /positions?sizeThreshold=0 (resolved-at-$0 sides that were never redeemed show up here with curPrice 0, redeemable true).
- Rebuild: per market, net = realized PnL of closed sides + cash PnL of resolved-at-$0 sides never redeemed. 27 (A) and 1 (B) still-open positions are ignored (tiny).
- "Both sides" = the wallet held both Up and Down of the same market at some point.
- Entry-price bands use each side's average buy price, weighted by cost.

## Paper simulation (simulate_5050.py → results/sim_summary.json)
- Sample: 2,160 resolved "Bitcoin Up or Down" 5-minute markets, one every 20 minutes, Sep 10 2026 06:15 AM CT to Oct 10 2026 05:55 AM CT (fetch_5m_markets.py; gamma events by slug btc-updown-5m-<ts>, outcome from outcomePrices; Up-token price history from clob.polymarket.com/prices-history, fidelity=1).
- Entry: as-of price at minute 1 or 2 after the window opens; Down price = 1 − Up price.
- Rule filter: only trade if the chosen side costs 0.41-0.59. Rules: always Up, always Down, coin flip (seed 7), follow the favorite (side ≥ 50¢), back the underdog.
- Fill = price + slippage (0¢ or 1¢). Taker fee = shares × 0.07 × p × (1 − p) (docs.polymarket.com/trading/fees; the sampled markets carry feeSchedule rate 0.07, takerOnly). $10 per trade, held to resolution.
- 95% interval: bootstrap of total PnL (2,000 resamples).
- Tails check: buy any side priced ≤ 4¢ at minute 3 or 4.

## Limitations
- Polymarket's own public numbers disagree for Trader A (profile headline vs leaderboard). The rebuild matches the leaderboard within 1%, but there is no official reconciliation.
- Price history points are about 1 minute apart; as-of fills can be stale (optimistic for the "favorite" rule). No order-book depth modeled.
- One month of 5-minute markets only; Trader A also trades ETH and 15-minute markets.
- Wallet data can change after Oct 10, 2026.
