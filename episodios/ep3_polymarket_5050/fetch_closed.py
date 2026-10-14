"""Download all closed positions (per-market realized PnL) for a wallet from the public Polymarket Data API."""

import json
import os
import sys
import time
import urllib.request

os.chdir(os.path.dirname(os.path.abspath(__file__)))

addr, tag = sys.argv[1], sys.argv[2]
out, off, L = [], 0, 50
while True:
    url = f"https://data-api.polymarket.com/closed-positions?user={addr}&limit={L}&offset={off}&sortBy=TIMESTAMP&sortDirection=DESC"
    for k in range(4):
        try:
            r = json.load(urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=30))
            break
        except Exception as e:
            print("retry", off, e, file=sys.stderr)
            time.sleep(2 + 3 * k)
    else:
        print("FAILED at", off, file=sys.stderr)
        break
    if not isinstance(r, list) or not r:
        break
    out += r
    off += L
    if off % 2000 == 0:
        print(tag, off, len(out), file=sys.stderr)
    time.sleep(0.12)
json.dump(out, open(f"data/closed_{tag}.json", "w"))
print(tag, "rows", len(out), "unique cond", len({x["conditionId"] for x in out}))
