"""Chequeos de "¿es verificable?" que usamos en cada episodio.

Solo lectura de datos públicos: este módulo no compra, no vende ni firma nada.
"""

from datetime import datetime


def created_after_claim(token_created: datetime, claim_date: datetime) -> bool:
    """True si el token se creó DESPUÉS de la fecha en que alguien dice haberlo operado."""
    return token_created > claim_date


def red_flags(claim: dict) -> list[str]:
    """Lista de señales de alerta en una promesa de rendimiento.

    `claim` puede tener: wallet, tx_links, monthly_return_pct, guaranteed, asks_for_seed.
    """
    flags = []
    if not claim.get("wallet"):
        flags.append("sin dirección de wallet: es una historia, no un historial")
    if not claim.get("tx_links"):
        flags.append("sin enlaces a transacciones")
    if claim.get("monthly_return_pct", 0) >= 20:
        flags.append("rendimiento mensual irreal (>=20%)")
    if claim.get("guaranteed"):
        flags.append("promete ganancias garantizadas")
    if claim.get("asks_for_seed"):
        flags.append("pide frase semilla o clave privada: estafa segura")
    return flags


def top_share(pnls: list[float], k: int = 1) -> float:
    """Porcentaje de la ganancia total que viene de las k mejores operaciones."""
    total = sum(pnls)
    if total <= 0:
        return float("nan")
    return 100 * sum(sorted(pnls, reverse=True)[:k]) / total
