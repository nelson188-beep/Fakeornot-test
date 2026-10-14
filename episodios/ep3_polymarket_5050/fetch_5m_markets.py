"""Sample resolved BTC 5-minute 'Up or Down' markets (one every 20 min, last 30 days) from public Gamma + CLOB APIs.
Saves outcome and the Up-token price history (≈1-minute points) for each market."""

import json
import os
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

os.chdir(os.path.dirname(os.path.abspath(__file__)))


def g(u):
    for k in range(5):
        try:
            return json.load(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=30))
        except Exception:
            time.sleep(2 + 3 * k)
    return None


END = 1791634500 - 3600  # 2026-10-10 07:15 ET, well resolved
STARTS = [END - i * 1200 for i in range(1, 30 * 72 + 1)]  # every 20 min for 30 days


def one(t):
    e = g(f"https://gamma-api.polymarket.com/events?slug=btc-updown-5m-{t}")
    if not e:
        return None
    m = e[0]["markets"][0]
    if not m.get("closed"):
        return None
    tok = json.loads(m["clobTokenIds"])
    op = json.loads(m["outcomePrices"])
    h = g(f"https://clob.polymarket.com/prices-history?market={tok[0]}&startTs={t - 120}&endTs={t + 300}&fidelity=1")
    time.sleep(0.25)
    return {
        "t": t,
        "slug": m["slug"],
        "q": m["question"],
        "up_won": op[0] == "1",
        "outcomePrices": op,
        "volume": m.get("volumeNum"),
        "feeSchedule": m.get("feeSchedule"),
        "up_hist": (h or {}).get("history", []),
    }


with ThreadPoolExecutor(3) as ex:
    res = list(ex.map(one, STARTS))
res = [r for r in res if r]
json.dump(res, open("data/btc5m_sample.json", "w"))
print("markets", len(res))
