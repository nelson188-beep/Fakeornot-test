# Fake Or Not — pruebas

Código abierto con el que **Fake Or Not** ([@FakeOrNotlab](https://x.com/FakeOrNotlab)) verifica promesas virales de trading ("mi bot gana $3K al mes", "compro a 50/50 en Polymarket y gano"...) usando **solo datos públicos** y simulaciones en papel.

> ⚠️ **No es asesoría financiera.** Todo es educativo. Las simulaciones usan dinero ficticio; resultados pasados no predicen resultados futuros. Este repositorio **no compra, no vende, no firma transacciones y no necesita claves ni wallets.**

## Contenido

| Carpeta | Qué hay |
|---|---|
| `fakeornot/` | Librería reutilizable: indicadores (EMA, ATR, drawdown), matemática de Polymarket (comisión, P&L, punto de equilibrio), longitud de posts de X y chequeos de señales de alerta. |
| `episodios/ep2_claude_bot_3k/` | Backtest del "bot de Claude que gana $3K/mes" (barras diarias de SPY, QQQ, GLD, USO, BTC). |
| `episodios/ep3_polymarket_5050/` | Descarga de datos públicos de Polymarket, análisis de dos wallets virales y simulación de la estrategia 50/50. |
| `episodios/ep5_0xboan/`, `episodios/zylen_scanner/` | Veredictos (verificación manual en DexScreener, GeckoTerminal y la cadena de Solana). |
| `tests/` | Pruebas con pytest. |

## Cómo correrlo

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest -q          # pruebas
ruff check .       # lint
```

Episodio 3 (descarga datos públicos a `data/`, sin claves):

```bash
cd episodios/ep3_polymarket_5050
mkdir -p data results
python fetch_5m_markets.py
python simulate_5050.py
```

El episodio 2 espera CSV diarios (`raw/SPY_1d.csv`, etc., columnas Date/Open/High/Low/Close/Volume) de cualquier fuente pública. Los datos crudos no se incluyen en el repo.

## English

Open-source code behind **Fake Or Not** (@FakeOrNotlab): we fact-check viral trading claims with public data and paper simulations. Install with `pip install -e ".[dev]"`, run `pytest` and `ruff check .`. Each folder in `episodios/` holds the scripts and verdict for one episode.

**Disclaimer: not financial advice.** Educational only; simulations use fake money and past results do not predict future ones. This code never trades, signs transactions or needs API keys or wallets.

## Licencia

MIT — ver [LICENSE](LICENSE).
