"""Costos reales de operar. Un backtest sin costos es una fantasía.

Valores por defecto pensados para una cuenta "raw/ECN" (spread bajo + comisión). Si tu
broker cobra distinto, cámbialos: el resultado puede pasar de ganador a perdedor.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from zoneinfo import ZoneInfo

import pandas as pd

NY = ZoneInfo("America/New_York")


@dataclass(frozen=True)
class CostModel:
    spread_pips: float | None = None      # None: usa la columna spread_pips del CSV o el típico del par
    spread_mult: float = 1.0              # para el what-if "¿y si el spread se duplica?"
    commission_per_lot_rt: float = 7.0    # USD por lote estándar, ida y vuelta
    slippage_pips: float = 0.2            # en entradas a mercado y en stops (no en take profit)
    swap_long_pips: float = -0.8          # pips por lote y noche (negativo = pagas)
    swap_short_pips: float = -0.2

    def scaled(self, **kw) -> "CostModel":
        return replace(self, **kw)


def rollover_nights(entry: pd.Timestamp, exit: pd.Timestamp) -> int:
    """Noches de swap entre entrada y salida. El rollover es a las 17:00 de Nueva York;
    el del miércoles cuenta triple (cubre el fin de semana)."""
    if exit <= entry:
        return 0
    start, end = entry.tz_convert(NY), exit.tz_convert(NY)
    t = start.normalize() + pd.Timedelta(hours=17)
    if t <= start:
        t += pd.Timedelta(days=1)
    nights = 0
    while t <= end:
        wd = t.weekday()
        if wd < 5:
            nights += 3 if wd == 2 else 1
        t += pd.Timedelta(days=1)
    return nights
