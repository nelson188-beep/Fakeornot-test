import math
from datetime import datetime

import pandas as pd
import pytest

from fakeornot import checks, indicators, polymarket, xlength


def test_ema_constant():
    assert indicators.ema(pd.Series([5.0] * 10), 3).iloc[-1] == pytest.approx(5.0)


def test_atr_and_drawdown():
    df = pd.DataFrame({"High": [11.0] * 20, "Low": [9.0] * 20, "Close": [10.0] * 20})
    assert indicators.atr(df, 14).iloc[-1] == pytest.approx(2.0)
    assert indicators.max_drawdown(pd.Series([100, 120, 90, 130])) == pytest.approx(-0.25)


def test_polymarket_math():
    assert polymarket.taker_fee_per_share(0.5) == pytest.approx(0.0175)
    assert polymarket.trade_pnl(0.5, False) == -10.0
    assert polymarket.trade_pnl(0.5, True) == pytest.approx(10 / 0.5175 - 10)
    assert polymarket.breakeven_win_pct(0.5) == pytest.approx(51.75)
    h = [{"t": 1, "p": 0.4}, {"t": 5, "p": 0.6}]
    assert polymarket.asof(h, 3) == 0.4
    assert polymarket.asof(h, 0) is None


def test_xlength():
    assert xlength.weighted_length("hola") == 4
    assert xlength.weighted_length("ver https://x.com/abc") == 4 + 23
    assert xlength.weighted_length("🔥") == 2
    assert not xlength.fits("a" * 281)


def test_checks():
    assert checks.created_after_claim(datetime(2026, 10, 12), datetime(2026, 10, 10))
    flags = checks.red_flags({"monthly_return_pct": 30, "asks_for_seed": True})
    assert len(flags) == 4
    assert checks.red_flags({"wallet": "x", "tx_links": ["t"]}) == []
    assert checks.top_share([50, 30, 20], 1) == pytest.approx(50)
    assert math.isnan(checks.top_share([-1.0]))
