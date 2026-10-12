"""Contrato de una estrategia.

Una estrategia mira las velas CERRADAS y devuelve, por vela, si hay señal. El motor de
backtest (y luego el bot en vivo) entra al precio de APERTURA de la vela siguiente:
nunca se opera con un precio que todavía no existía.

Columnas que debe devolver signals():
    signal     +1 compra, -1 venta, 0 nada
    sl_dist    distancia del stop loss en precio (> 0 cuando hay señal)
    tp_dist    distancia del take profit en precio (> 0 cuando hay señal)
    size_mult  multiplicador del riesgo (1.0 normal; 0.75 en "tensión", etc.)
    + columnas de contexto opcionales (regime, vol_band, ...) que se copian a cada operación
"""
from __future__ import annotations

from typing import Protocol

import pandas as pd

from fxbot.data.loaders import daily_bars
from fxbot.regime.market_regime import market_regime
from fxbot.regime.vol_proxy import align_daily_to_bars, daily_vol_proxy

REQUIRED = ("signal", "sl_dist", "tp_dist", "size_mult")


class Strategy(Protocol):
    name: str

    def signals(self, df: pd.DataFrame) -> pd.DataFrame: ...


def daily_context(df: pd.DataFrame) -> pd.DataFrame:
    """VIX proxy (banda de volatilidad) y régimen diarios, alineados a las velas sin mirar al futuro."""
    daily = daily_bars(df)
    ctx = daily_vol_proxy(daily["close"])
    ctx["regime"] = market_regime(daily, calibration="fx")
    return align_daily_to_bars(ctx, df.index)
