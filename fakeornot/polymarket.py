"""Matemática de mercados binarios de Polymarket (comisión taker, P&L, punto de equilibrio)."""

FEE_RATE = 0.07  # tasa taker documentada para mercados cripto


def taker_fee_per_share(price: float, rate: float = FEE_RATE) -> float:
    """Comisión por acción: rate * p * (1 - p)."""
    return rate * price * (1 - price)


def trade_pnl(price: float, won: bool, stake: float = 10.0, slip: float = 0.0, rate: float = FEE_RATE) -> float:
    """P&L de comprar `stake` dólares a `price` (+slippage) y mantener hasta la resolución."""
    fill = min(price + slip, 0.999)
    shares = stake / (fill + taker_fee_per_share(fill, rate))
    return (shares if won else 0.0) - stake


def breakeven_win_pct(price: float, slip: float = 0.0, rate: float = FEE_RATE) -> float:
    """Porcentaje de aciertos necesario para no perder dinero."""
    fill = price + slip
    return 100 * (fill + taker_fee_per_share(fill, rate))


def asof(history: list[dict], ts: int) -> float | None:
    """Último precio con t <= ts en un historial [{'t': ..., 'p': ...}] ordenado."""
    p = None
    for x in history:
        if x["t"] <= ts:
            p = x["p"]
        else:
            break
    return p
