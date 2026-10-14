"""Paper simulation: is buying the ~50/50 band (41-59c) in BTC 5-minute Up/Down markets an edge by itself?
Data: 2,160 resolved markets sampled every 20 min, Sep 10 - Oct 10, 2026 (data/btc5m_sample.json, public Gamma + CLOB price history).
Fill = as-of price at entry minute + slippage; taker fee = shares x 0.07 x p x (1-p) (Polymarket docs, crypto).
$10 per trade, hold to resolution."""

import json
import os
import random

import numpy as np

os.chdir(os.path.dirname(os.path.abspath(__file__)))

D = json.load(open("data/btc5m_sample.json"))
FEE = 0.07
STAKE = 10.0


def asof(h, ts):
    p = None
    for x in h:
        if x["t"] <= ts:
            p = x["p"]
        else:
            break
    return p


def trade(price, won, slip):
    fill = min(price + slip, 0.999)
    fee_ps = FEE * fill * (1 - fill)
    sh = STAKE / (fill + fee_ps)
    return (sh if won else 0) - STAKE


rules = {
    "always_up": lambda up, rnd: "up",
    "always_down": lambda up, rnd: "down",
    "coin_flip": lambda up, rnd: "up" if rnd < 0.5 else "down",
    "favorite": lambda up, rnd: "up" if up >= 0.5 else "down",
    "underdog": lambda up, rnd: "down" if up >= 0.5 else "up",
}
out = {"n_markets": len(D), "window": [min(d["t"] for d in D), max(d["t"] for d in D)], "fee_rate": FEE, "stake": STAKE, "runs": {}}
for minute in [1, 2]:
    for slip in [0.0, 0.01]:
        for name, f in rules.items():
            rng = random.Random(7)
            pnl = []
            wins = 0
            prices = []
            for d in D:
                h = sorted(d["up_hist"], key=lambda x: x["t"])
                up = asof(h, d["t"] + 60 * minute)
                r = rng.random()
                if up is None:
                    continue
                side = f(up, r)
                p = up if side == "up" else 1 - up
                if not (0.41 <= p <= 0.59):
                    continue
                won = d["up_won"] if side == "up" else not d["up_won"]
                pnl.append(trade(p, won, slip))
                wins += won
                prices.append(p)
            pnl = np.array(pnl)
            n = len(pnl)
            bs = np.random.default_rng(1).choice(pnl, (2000, n)).sum(1) if n else np.array([0])
            out["runs"][f"{name}|min{minute}|slip{int(slip * 100)}c"] = dict(
                n=n,
                win_pct=round(100 * wins / n, 1),
                avg_price=round(float(np.mean(prices)), 3),
                total_pnl=round(float(pnl.sum()), 2),
                roi_pct=round(100 * pnl.sum() / (STAKE * n), 2),
                ci95_total=[round(float(np.percentile(bs, 2.5)), 2), round(float(np.percentile(bs, 97.5)), 2)],
            )
# break-even win rate at 50c
for p in [0.41, 0.50, 0.59]:
    for slip in [0, 0.01]:
        fill = p + slip
        out[f"breakeven_win_pct@{int(p * 100)}c_slip{int(slip * 100)}c"] = round(100 * (fill + FEE * fill * (1 - fill)), 2)
# buying BOTH sides as a taker at a 50/50 market
fill = 0.5
out["both_sides_taker_cost_per_$1_payout"] = {
    "slip0": round(2 * (fill + FEE * fill * (1 - fill)), 4),
    "slip1c": round(2 * (fill + 0.01 + FEE * (fill + 0.01) * (1 - fill - 0.01)), 4),
}
# tails: buy the side priced <= 4c at minute 3 or 4
for minute in [3, 4]:
    pnl = []
    wins = 0
    for d in D:
        h = sorted(d["up_hist"], key=lambda x: x["t"])
        up = asof(h, d["t"] + 60 * minute)
        if up is None:
            continue
        for side, p in [("up", up), ("down", 1 - up)]:
            if 0 < p <= 0.04:
                won = d["up_won"] if side == "up" else not d["up_won"]
                pnl.append(trade(p, won, 0.0))
                wins += won
    pnl = np.array(pnl)
    out[f"tails_le4c_min{minute}"] = dict(
        n=len(pnl),
        wins=int(wins),
        win_pct=round(100 * wins / max(len(pnl), 1), 2),
        total_pnl=round(float(pnl.sum()), 2),
        roi_pct=round(100 * pnl.sum() / (STAKE * max(len(pnl), 1)), 1),
    )
out["up_won_pct"] = round(100 * np.mean([d["up_won"] for d in D]), 1)
json.dump(out, open("results/sim_summary.json", "w"), indent=1)
print(json.dumps(out, indent=1))
