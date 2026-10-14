#!/usr/bin/env python3
"""Paper backtest of Ray Fu / @hypertech Claude trading-bot claim. Daily bars."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent
RAW = ROOT / "raw"
OUT = ROOT / "results"
CHARTS = ROOT / "charts"
OUT.mkdir(exist_ok=True)
CHARTS.mkdir(exist_ok=True)

BG, CARD, FG, MUTED, GREEN, RED, GRID = ("#0D1117", "#161B22", "#F0F3F6", "#8B949E", "#2FD47A", "#FF4D5E", "#30363D")
START_CAP = 10_000.0
STOCK_FEE = 0.0001  # per side
BTC_FEE = 0.0025  # per side
RISK_PCT = 0.01
KILL = 0.10


def load(sym: str) -> pd.DataFrame:
    path = RAW / f"{sym}_1d.csv"
    df = pd.read_csv(path, parse_dates=["Date"]).sort_values("Date").set_index("Date")
    return df[["Open", "High", "Low", "Close", "Volume"]].astype(float)


def ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False).mean()


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    prev = df["Close"].shift(1)
    tr = pd.concat(
        [
            (df["High"] - df["Low"]).abs(),
            (df["High"] - prev).abs(),
            (df["Low"] - prev).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.rolling(n).mean()


def prepare() -> dict[str, pd.DataFrame]:
    data = {
        "SPY": load("SPY"),
        "QQQ": load("QQQ"),
        "GLD": load("GLD"),
        "USO": load("USO"),
        "BTC": load("BTCUSD"),
    }
    for sym, df in data.items():
        df = df.copy()
        df["SMA20"] = df["Close"].rolling(20).mean()
        df["STD20"] = df["Close"].rolling(20).std(ddof=0)
        df["ATR14"] = atr(df, 14)
        df["EMA50"] = ema(df["Close"], 50)
        df["EMA200"] = ema(df["Close"], 200)
        df["HH20"] = df["High"].rolling(20).max().shift(1)  # prior 20-bar high
        df["LL20"] = df["Low"].rolling(20).min().shift(1)
        df["VOL20"] = df["Volume"].rolling(20).mean()
        data[sym] = df
    return data


@dataclass
class Pos:
    sym: str
    side: int  # +1 long, -1 short
    shares: float
    entry: float
    stop: float
    trail_mult: float | None
    atr_entry: float
    entry_date: pd.Timestamp


@dataclass
class State:
    cash: float = START_CAP
    peak: float = START_CAP
    killed: bool = False
    positions: dict[str, Pos] = field(default_factory=dict)
    trades: list = field(default_factory=list)
    equity_rows: list = field(default_factory=list)


def fee_rate(sym: str) -> float:
    return BTC_FEE if sym == "BTC" else STOCK_FEE


def mark_equity(st: State, data: dict, day: pd.Timestamp) -> float:
    eq = st.cash
    for sym, p in st.positions.items():
        if day not in data[sym].index:
            # use last available close
            px = data[sym].loc[:day, "Close"]
            if px.empty:
                continue
            c = float(px.iloc[-1])
        else:
            c = float(data[sym].loc[day, "Close"])
        eq += p.shares * c * p.side + (p.shares * p.entry if p.side < 0 else 0)
        # For longs: cash already reduced by cost; equity += shares*close
        # Wait - accounting: for long we deduct cash at entry; equity = cash + shares*mark
        # for short we credit cash at entry; equity = cash - shares*mark (liability)
    # Recalculate cleanly:
    eq = st.cash
    for sym, p in st.positions.items():
        px_s = data[sym].loc[:day, "Close"]
        if px_s.empty:
            continue
        c = float(px_s.iloc[-1])
        if p.side > 0:
            eq += p.shares * c
        else:
            # short: cash includes short proceeds; liability is shares*c
            eq -= p.shares * c
    return eq


def open_pos(st: State, day: pd.Timestamp, sym: str, side: int, px: float, atr_v: float, trail_mult: float | None, equity: float) -> bool:
    if atr_v <= 0 or np.isnan(atr_v) or px <= 0:
        return False
    risk_dollars = equity * RISK_PCT
    shares = risk_dollars / atr_v
    fr = fee_rate(sym)
    if side > 0:
        cost = shares * px * (1 + fr)
        if cost > st.cash * 0.99:
            shares = (st.cash * 0.99) / (px * (1 + fr))
            cost = shares * px * (1 + fr)
        if shares * px < 5:
            return False
        st.cash -= cost
        stop = px - atr_v
    else:
        # short: credit net proceeds; require cash >= notional (conservative PDT-like buffer)
        if shares * px > st.cash * 0.99:
            shares = (st.cash * 0.99) / px
        if shares * px < 5:
            return False
        st.cash += shares * px * (1 - fr)
        stop = px + atr_v
    st.positions[sym] = Pos(sym, side, shares, px, stop, trail_mult, atr_v, day)
    return True


def close_pos(st: State, day: pd.Timestamp, sym: str, px: float, reason: str):
    p = st.positions.pop(sym)
    fr = fee_rate(sym)
    if p.side > 0:
        st.cash += p.shares * px * (1 - fr)
        pnl = p.shares * ((px * (1 - fr)) - (p.entry * (1 + fr)))
    else:
        st.cash -= p.shares * px * (1 + fr)
        pnl = p.shares * ((p.entry * (1 - fr)) - (px * (1 + fr)))
    st.trades.append(
        {
            "exit_date": str(day.date()),
            "entry_date": str(p.entry_date.date()),
            "sym": sym,
            "side": "long" if p.side > 0 else "short",
            "shares": round(p.shares, 6),
            "entry": round(p.entry, 6),
            "exit": round(px, 6),
            "pnl": round(pnl, 4),
            "reason": reason,
        }
    )


def pending_signals(data: dict, day: pd.Timestamp, st: State) -> list[tuple]:
    """Return list of (sym, side, trail_mult) signals based on day close. side 0 = exit flat."""
    sigs = []
    # Mean reversion SPY / QQQ
    for sym, k in [("SPY", 1.5), ("QQQ", 1.8)]:
        if day not in data[sym].index:
            continue
        r = data[sym].loc[day]
        if np.isnan(r["SMA20"]) or np.isnan(r["STD20"]) or r["STD20"] == 0:
            continue
        upper = r["SMA20"] + k * r["STD20"]
        lower = r["SMA20"] - k * r["STD20"]
        pos = st.positions.get(sym)
        if pos is None:
            if r["Close"] < lower:
                sigs.append((sym, 1, None, "mr_entry"))
            elif r["Close"] > upper:
                sigs.append((sym, -1, None, "mr_entry"))
        else:
            # exit when price returns to MA
            if pos.side > 0 and r["Close"] >= r["SMA20"]:
                sigs.append((sym, 0, None, "mr_exit"))
            elif pos.side < 0 and r["Close"] <= r["SMA20"]:
                sigs.append((sym, 0, None, "mr_exit"))

    # BTC momentum — long only
    sym = "BTC"
    if day in data[sym].index:
        r = data[sym].loc[day]
        pos = st.positions.get(sym)
        if not np.isnan(r["HH20"]) and not np.isnan(r["VOL20"]) and r["VOL20"] > 0:
            vol_ok = r["Volume"] >= 1.5 * r["VOL20"]
            if pos is None:
                if r["Close"] > r["HH20"] and vol_ok:
                    # correlation filter
                    spy_long = "SPY" in st.positions and st.positions["SPY"].side > 0
                    qqq_long = "QQQ" in st.positions and st.positions["QQQ"].side > 0
                    if not (spy_long and qqq_long):
                        sigs.append((sym, 1, 2.0, "mom_entry"))
            else:
                if r["Close"] < r["LL20"] and vol_ok:
                    sigs.append((sym, 0, None, "mom_exit"))

    # Trend GLD / USO
    for sym in ("GLD", "USO"):
        if day not in data[sym].index:
            continue
        r = data[sym].loc[day]
        prev_days = data[sym].loc[:day].iloc[:-1]
        if len(prev_days) < 1 or np.isnan(r["EMA50"]) or np.isnan(r["EMA200"]):
            continue
        prev = prev_days.iloc[-1]
        if np.isnan(prev["EMA50"]) or np.isnan(prev["EMA200"]):
            continue
        cross_up = prev["EMA50"] <= prev["EMA200"] and r["EMA50"] > r["EMA200"]
        cross_dn = prev["EMA50"] >= prev["EMA200"] and r["EMA50"] < r["EMA200"]
        pos = st.positions.get(sym)
        if cross_up:
            if pos and pos.side < 0:
                sigs.append((sym, 0, None, "trend_exit_short"))
            if pos is None or pos.side < 0:
                sigs.append((sym, 1, 3.0, "trend_entry"))
        elif cross_dn:
            if pos and pos.side > 0:
                sigs.append((sym, 0, None, "trend_exit_long"))
            if pos is None or pos.side > 0:
                sigs.append((sym, -1, 3.0, "trend_entry"))
    return sigs


def run(data: dict, start: str, end: str, label: str) -> dict:
    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(end)
    # calendar = union of all dates in range
    idx = sorted(set().union(*[set(df.loc[start_ts:end_ts].index) for df in data.values()]))
    idx = [d for d in idx if start_ts <= d <= end_ts]
    st = State()
    pending: list[tuple] = []  # execute next day

    # Warm-up: need indicators; first trade day after start when ATR ready
    for i, day in enumerate(idx):
        # 1) manage stops / trails on open positions using today's H/L
        if not st.killed:
            for sym in list(st.positions.keys()):
                if day not in data[sym].index:
                    continue
                r = data[sym].loc[day]
                p = st.positions[sym]
                atr_v = r["ATR14"]
                # update trailing
                if p.trail_mult and not np.isnan(atr_v):
                    if p.side > 0:
                        new_stop = float(r["High"]) - p.trail_mult * atr_v
                        p.stop = max(p.stop, new_stop)
                    else:
                        new_stop = float(r["Low"]) + p.trail_mult * atr_v
                        p.stop = min(p.stop, new_stop)
                # hard / trail stop hit
                if p.side > 0 and float(r["Low"]) <= p.stop:
                    # fill at stop (or open if gapped)
                    fill = min(p.stop, float(r["Open"]))
                    close_pos(st, day, sym, fill, "stop")
                elif p.side < 0 and float(r["High"]) >= p.stop:
                    fill = max(p.stop, float(r["Open"]))
                    close_pos(st, day, sym, fill, "stop")

        # 2) execute pending signals at today's open
        if not st.killed and pending:
            eq = mark_equity(st, data, day)
            for sym, side, trail, reason in pending:
                if day not in data[sym].index:
                    continue
                o = float(data[sym].loc[day, "Open"])
                atr_v = float(data[sym].loc[day, "ATR14"])
                if side == 0:
                    if sym in st.positions:
                        close_pos(st, day, sym, o, reason)
                else:
                    if sym in st.positions:
                        continue
                    if reason == "mom_entry":
                        spy_long = "SPY" in st.positions and st.positions["SPY"].side > 0
                        qqq_long = "QQQ" in st.positions and st.positions["QQQ"].side > 0
                        if spy_long and qqq_long:
                            continue
                    open_pos(st, day, sym, side, o, atr_v, trail, eq)
            pending = []

        # 3) mark equity, kill switch
        eq = mark_equity(st, data, day)
        st.peak = max(st.peak, eq)
        if not st.killed and eq <= st.peak * (1 - KILL):
            # flatten at close
            for sym in list(st.positions.keys()):
                if day in data[sym].index:
                    close_pos(st, day, sym, float(data[sym].loc[day, "Close"]), "kill_switch")
            st.killed = True
            eq = mark_equity(st, data, day)

        st.equity_rows.append({"date": day, "equity": eq, "killed": st.killed, "n_pos": len(st.positions)})

        # 4) new signals on close → pending for next open
        if not st.killed:
            pending = pending_signals(data, day, st)

    # flatten at end
    if idx:
        last = idx[-1]
        for sym in list(st.positions.keys()):
            if last in data[sym].index:
                close_pos(st, last, sym, float(data[sym].loc[last, "Close"]), "period_end")
        eq = mark_equity(st, data, last)
        if st.equity_rows:
            st.equity_rows[-1]["equity"] = eq

    eq_df = pd.DataFrame(st.equity_rows).set_index("date")
    trades = pd.DataFrame(st.trades)

    # SPY buy & hold
    spy = data["SPY"].loc[start_ts:end_ts]
    if spy.empty:
        spy_eq = pd.Series(dtype=float)
        spy_final = START_CAP
    else:
        entry = float(spy.iloc[0]["Open"]) * (1 + STOCK_FEE)
        shares = START_CAP / entry
        spy_eq = shares * spy["Close"] * (1 - STOCK_FEE)  # mark approx; final exit fee at end
        spy_eq.iloc[-1] = shares * float(spy.iloc[-1]["Close"]) * (1 - STOCK_FEE)
        spy_final = float(spy_eq.iloc[-1])

    final = float(eq_df["equity"].iloc[-1]) if len(eq_df) else START_CAP
    ret = final / START_CAP - 1
    days = max((eq_df.index[-1] - eq_df.index[0]).days, 1) if len(eq_df) else 1
    months = days / 30.4375
    monthly_avg_ret = (final / START_CAP) ** (1 / max(months, 1e-9)) - 1 if months >= 1 else ret
    monthly_avg_dollars = (final - START_CAP) / max(months, 1e-9)

    dd = eq_df["equity"] / eq_df["equity"].cummax() - 1
    max_dd = float(dd.min()) if len(dd) else 0.0

    rets = eq_df["equity"].pct_change().dropna()
    sharpe = float(rets.mean() / rets.std() * np.sqrt(252)) if len(rets) > 2 and rets.std() > 0 else float("nan")

    n_trades = len(trades)
    win_rate = float((trades["pnl"] > 0).mean()) if n_trades else float("nan")

    # capital for $3k/month at achieved monthly avg dollar rate scaled
    # If monthly_avg_dollars on 10k, scale: need 3000 / (monthly_avg_dollars/10000) = 3000 * 10000 / monthly_avg_dollars
    if monthly_avg_dollars > 0:
        cap_for_3k = 3000.0 * START_CAP / monthly_avg_dollars
    else:
        cap_for_3k = float("inf")

    # monthly pnl bars
    m = eq_df["equity"].resample("ME").last().dropna()
    monthly_pnl = m.diff()
    monthly_pnl.iloc[0] = m.iloc[0] - START_CAP

    summary = {
        "label": label,
        "start": str(eq_df.index[0].date()) if len(eq_df) else start,
        "end": str(eq_df.index[-1].date()) if len(eq_df) else end,
        "start_capital": START_CAP,
        "final_equity": round(final, 2),
        "total_return_pct": round(ret * 100, 2),
        "total_pnl_dollars": round(final - START_CAP, 2),
        "months": round(months, 2),
        "monthly_avg_return_pct": round(monthly_avg_ret * 100, 3),
        "monthly_avg_pnl_dollars": round(monthly_avg_dollars, 2),
        "max_drawdown_pct": round(max_dd * 100, 2),
        "n_trades": n_trades,
        "win_rate_pct": round(win_rate * 100, 1) if n_trades else None,
        "sharpe": round(sharpe, 3) if sharpe == sharpe else None,
        "killed": bool(st.killed),
        "spy_bh_final": round(spy_final, 2),
        "spy_bh_return_pct": round((spy_final / START_CAP - 1) * 100, 2),
        "capital_for_3k_month": None if cap_for_3k == float("inf") else round(cap_for_3k, 0),
        "capital_for_3k_note": (
            "n/a — strategy lost money or zero avg monthly gain"
            if cap_for_3k == float("inf")
            else f"~${cap_for_3k:,.0f} at this period's average monthly $ P&L rate (not a forecast)"
        ),
    }

    eq_df.to_csv(OUT / f"equity_{label}.csv")
    trades.to_csv(OUT / f"trades_{label}.csv", index=False)
    monthly_pnl.to_csv(OUT / f"monthly_pnl_{label}.csv", header=["pnl"])
    spy_eq.to_csv(OUT / f"spy_bh_{label}.csv", header=["spy_equity"])

    return {
        "summary": summary,
        "equity": eq_df,
        "trades": trades,
        "monthly_pnl": monthly_pnl,
        "spy_eq": spy_eq,
    }


def make_charts(long_res: dict, short_res: dict):
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "text.color": FG,
            "axes.edgecolor": GRID,
            "axes.labelcolor": MUTED,
            "xtick.color": MUTED,
            "ytick.color": MUTED,
            "axes.facecolor": BG,
            "figure.facecolor": BG,
        }
    )

    # Chart 1: equity vs SPY (long period)
    fig, ax = plt.subplots(figsize=(10, 5.5), dpi=140)
    eq = long_res["equity"]["equity"]
    spy = long_res["spy_eq"]
    ax.plot(eq.index, eq.values, color=GREEN, lw=2, label="Claude bot (paper)")
    if len(spy):
        # align
        spy_a = spy.reindex(eq.index, method="ffill")
        ax.plot(spy_a.index, spy_a.values, color="#58A6FF", lw=1.8, label="Buy & hold SPY")
    ax.axhline(START_CAP, color=MUTED, lw=0.8, ls="--")
    ax.set_title("Equity curve · 2019–2026 paper backtest · $10k start", color=FG, loc="left", fontsize=13, pad=12)
    ax.set_ylabel("Equity ($)")
    ax.grid(True, color=GRID, alpha=0.5)
    ax.legend(facecolor=CARD, edgecolor=GRID)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()
    fig.savefig(CHARTS / "1_equity_vs_spy.png", facecolor=BG)
    plt.close(fig)

    # Chart 2: monthly $ P&L bars (long period)
    fig, ax = plt.subplots(figsize=(10, 5.5), dpi=140)
    mp = long_res["monthly_pnl"].dropna()
    colors = [GREEN if v >= 0 else RED for v in mp.values]
    ax.bar(mp.index, mp.values, width=20, color=colors, align="center")
    ax.axhline(0, color=MUTED, lw=0.8)
    ax.axhline(3000, color=RED, lw=1, ls="--", label="$3,000/month claim")
    ax.set_title("Monthly P&L ($) · 2019–2026 · dashed line = $3K claim", color=FG, loc="left", fontsize=13, pad=12)
    ax.set_ylabel("P&L ($)")
    ax.grid(True, color=GRID, alpha=0.5, axis="y")
    ax.legend(facecolor=CARD, edgecolor=GRID)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()
    fig.savefig(CHARTS / "2_monthly_pnl.png", facecolor=BG)
    plt.close(fig)

    # Also a compact 6-month equity overlay chart? Task asked for 2 charts only.


def main():
    data = prepare()
    end = "2026-10-07"
    short = run(data, "2026-04-07", end, "6m")
    long = run(data, "2019-01-01", end, "long")
    make_charts(long, short)

    # per-symbol trade stats
    def by_sym(tr: pd.DataFrame):
        if tr.empty:
            return {}
        g = tr.groupby("sym").agg(n=("pnl", "count"), win=("pnl", lambda s: float((s > 0).mean())), pnl=("pnl", "sum"))
        return {k: {"n": int(v["n"]), "win_rate": round(v["win"] * 100, 1), "pnl": round(v["pnl"], 2)} for k, v in g.iterrows()}

    out = {
        "6m": {**short["summary"], "by_symbol": by_sym(short["trades"])},
        "long": {**long["summary"], "by_symbol": by_sym(long["trades"])},
        "assumptions_file": "methods.md",
    }
    with open(OUT / "summary.json", "w") as f:
        json.dump(out, f, indent=2)
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
