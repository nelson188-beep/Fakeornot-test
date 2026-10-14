"""Indicadores técnicos simples usados en los backtests (papel, sin dinero real)."""

import pandas as pd


def ema(s: pd.Series, n: int) -> pd.Series:
    """Media móvil exponencial."""
    return s.ewm(span=n, adjust=False).mean()


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    """Average True Range (media simple de n barras)."""
    prev = df["Close"].shift(1)
    tr = pd.concat(
        [(df["High"] - df["Low"]).abs(), (df["High"] - prev).abs(), (df["Low"] - prev).abs()],
        axis=1,
    ).max(axis=1)
    return tr.rolling(n).mean()


def max_drawdown(equity: pd.Series) -> float:
    """Caída máxima desde el pico, en fracción negativa (p. ej. -0.12)."""
    return float((equity / equity.cummax() - 1).min())
