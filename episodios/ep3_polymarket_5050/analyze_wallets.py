"""Fake or Not #3: verify the two viral Polymarket claims from public data.
Inputs: data/closed_{F,H}.json (Data API /closed-positions), data/positions_{F,H}.json (/positions),
data/lb_*.json (/v1/leaderboard), data/pnl_daily_*.json (user-pnl-api, the profile chart), raw/pm_profile_*.html (profile stats).
F = the '50/50' trader (claim: +$93.8K, 1.8% of $5.2M volume). H = the 'lottery ticket' trader (claim: one $55 bet = 62% of profit)."""

import collections
import datetime as dt
import json
import os
import re

import numpy as np

os.chdir(os.path.dirname(os.path.abspath(__file__)))

R = {}


def prof(path):
    t = open(path).read().replace('\\"', '"')
    m = re.search(
        r'"data":\{"trades":(\d+),"largestWin":([\d.]+),"views":\d+,"joinDate":"([^"]+)","volume":([\d.]+),"headlinePnl":([\d.-]+),"takerRebateEarned":([\d.]+)',
        t,
    )
    return dict(
        markets_traded=int(m[1]),
        largest_win_stat=float(m[2]),
        join_date=m[3],
        volume=float(m[4]),
        headline_pnl=float(m[5]),
        taker_rebate_earned=float(m[6]),
    )


for n, wallet in [("F", "0xd84403efd50b49a1d8a7181627e00307e6ea5908"), ("H", "0x8ff04326388b1c024c45d7a7ffdd12cdedd0a0ed")]:
    P = prof(f"raw/pm_profile_{'fvm' if n == 'F' else 'hell'}.html")
    lb = {k: json.load(open(f"data/lb_{k}_{n}.json"))[0] for k in ["all", "month"]}
    closed = {}
    for x in json.load(open(f"data/closed_{n}.json")):
        closed[(x["conditionId"], x["asset"])] = x
    closed = list(closed.values())
    opn = json.load(open(f"data/positions_{n}.json"))
    lost_unredeemed = [x for x in opn if x["curPrice"] == 0 and x["redeemable"]]
    still_open = [x for x in opn if x["curPrice"] > 0]
    # per-market net = realized on closed sides + cash PnL of resolved-at-$0 sides never redeemed
    mk = collections.defaultdict(float)
    sides = collections.defaultdict(set)
    title = {}
    for x in closed:
        mk[x["conditionId"]] += x["realizedPnl"]
        sides[x["conditionId"]].add(x["outcome"])
        title[x["conditionId"]] = x["title"]
    for x in lost_unredeemed:
        mk[x["conditionId"]] += x["cashPnl"] + x["realizedPnl"]
        sides[x["conditionId"]].add(x["outcome"])
        title[x["conditionId"]] = x["title"]
    net = np.array(list(mk.values()))
    keys = list(mk.keys())
    order = np.argsort(-net)
    top = [(title[keys[i]], round(net[i], 2)) for i in order[:5]]
    rebuild = net.sum()
    cost = np.array([x["avgPrice"] * x["totalBought"] for x in closed] + [x["initialValue"] for x in lost_unredeemed])
    avgp = np.array([x["avgPrice"] for x in closed] + [x["avgPrice"] for x in lost_unredeemed])
    bands = {}
    for lo, hi in [(0, 0.05), (0.05, 0.2), (0.2, 0.41), (0.41, 0.595), (0.595, 0.8), (0.8, 1.01)]:
        m = (avgp >= lo) & (avgp < hi)
        bands[f"{lo:.2f}-{hi:.2f}"] = dict(n_sides=int(m.sum()), cost_share_pct=round(100 * cost[m].sum() / cost.sum(), 1))
    head = P["headline_pnl"]
    R[n] = dict(
        wallet=wallet,
        profile=P,
        leaderboard_all=dict(pnl=lb["all"]["pnl"], vol=lb["all"]["vol"], rank=lb["all"]["rank"]),
        leaderboard_month=dict(pnl=lb["month"]["pnl"], vol=lb["month"]["vol"]),
        n_closed_sides=len(closed),
        n_lost_unredeemed_sides=len(lost_unredeemed),
        lost_unredeemed_pnl=round(sum(x["cashPnl"] + x["realizedPnl"] for x in lost_unredeemed), 2),
        n_still_open=len(still_open),
        closed_realized_sum=round(sum(x["realizedPnl"] for x in closed), 2),
        rebuild_net_pnl=round(rebuild, 2),
        n_markets=len(net),
        market_win_rate_pct=round(100 * (net > 0).mean(), 1),
        markets_both_sides=sum(len(v) > 1 for v in sides.values()),
        both_sides_pct=round(100 * sum(len(v) > 1 for v in sides.values()) / len(sides), 1),
        top5_markets=top,
        top1_pnl=round(net[order[0]], 2),
        top3_pnl=round(net[order[:3]].sum(), 2),
        top1_share_of_headline_pct=round(100 * net[order[0]] / head, 1),
        top3_share_of_headline_pct=round(100 * net[order[:3]].sum() / head, 1),
        top1_share_of_rebuild_pct=round(100 * net[order[0]] / rebuild, 1),
        headline_without_top1=round(head - net[order[0]], 2),
        rebuild_without_top1=round(rebuild - net[order[0]], 2),
        margin_headline_pct=round(100 * head / P["volume"], 2),
        margin_leaderboard_pct=round(100 * lb["all"]["pnl"] / lb["all"]["vol"], 2),
        margin_rebuild_pct=round(100 * rebuild / P["volume"], 2),
        entry_price_bands=bands,
        first_ts=dt.datetime.fromtimestamp(min(x["timestamp"] for x in closed), dt.UTC).isoformat(),
        last_ts=dt.datetime.fromtimestamp(max(x["timestamp"] for x in closed), dt.UTC).isoformat(),
    )
    if n == "H":
        tails = [x for x in closed if x["avgPrice"] <= 0.05] + [x for x in lost_unredeemed if x["avgPrice"] <= 0.05]
        tw = [x for x in tails if (x.get("curPrice") == 1 or x["realizedPnl"] > 0)]
        R[n]["tail_bets_le5c"] = dict(
            n=len(tails),
            n_won=len(tw),
            win_pct=round(100 * len(tw) / len(tails), 1),
            pnl=round(sum(x["realizedPnl"] + (x["cashPnl"] if x in lost_unredeemed else 0) for x in tails), 2),
        )
        b = max(closed, key=lambda x: x["realizedPnl"])
        R[n]["best_trade"] = {k: b[k] for k in ["title", "outcome", "avgPrice", "totalBought", "realizedPnl", "endDate"]} | {
            "cost": round(b["avgPrice"] * b["totalBought"], 2)
        }
    # pnl chart value on the day the post was written
    s = json.load(open(f"data/pnl_daily_{n}.json"))
    R[n]["chart"] = {
        dt.datetime.fromtimestamp(x["t"], dt.UTC).date().isoformat(): round(x["p"], 2)
        for x in s
        if dt.datetime.fromtimestamp(x["t"], dt.UTC).date().isoformat()
        in ("2026-10-05", "2026-10-06", "2026-10-08", "2026-10-09", "2026-10-10")
    }
json.dump(R, open("results/wallets_summary.json", "w"), indent=1, default=float)
print(json.dumps(R, indent=1, default=float))
