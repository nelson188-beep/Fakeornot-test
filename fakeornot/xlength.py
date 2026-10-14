"""Longitud ponderada de un post de X: URLs cuentan 23, emoji/no latinos cuentan 2."""

import re

LIMIT = 280


def weighted_length(text: str) -> int:
    text = re.sub(r"https?://\S+", "U" * 23, text)
    n = 0
    for ch in text:
        c = ord(ch)
        n += 1 if (c <= 4351 or 8192 <= c <= 8205 or 8208 <= c <= 8223 or 8242 <= c <= 8247) else 2
    return n


def fits(text: str, limit: int = LIMIT) -> bool:
    return weighted_length(text) <= limit
