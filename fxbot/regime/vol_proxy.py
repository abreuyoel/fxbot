""""VIX proxy" para forex: volatilidad realizada y su percentil histórico.

Port de realized_vol_stats() de Caracas-Portafolio (backend/app/api/stocks.py):
desviación estándar MUESTRAL de los log-retornos de las últimas `window` sesiones,
anualizada con sqrt(252), y percentil de ese valor frente a todas las ventanas
anteriores.

Diferencia importante con la Bolsa de Caracas: allá las bandas son absolutas
(<18 % letargo, 18-30 óptimo, 30-50 tensión, >50 pánico) porque el IBC es muy volátil.
EURUSD se mueve ~5-10 % anual, así que esas cifras nunca se alcanzarían. Para forex las
bandas se definen por PERCENTIL (qué tan alta está la volatilidad frente a la historia
del propio par), que es lo que tu tarjeta ya muestra como "Percentil 71".
"""
from __future__ import annotations

import bisect

import numpy as np
import pandas as pd

BANDS = (  # (percentil máximo, etiqueta, consejo)
    (20.0, "letargo", "Mercado anormalmente quieto: rupturas poco fiables."),
    (70.0, "optimo", "Volatilidad sana: stops por ATR funcionan bien."),
    (90.0, "tension", "Riesgo de gaps alto: reducir tamaño 25 %, nunca sin stop."),
    (100.0, "panico", "Volatilidad extrema: solo gestionar posiciones abiertas."),
)


def realized_vol(close: pd.Series, window: int = 30, periods_per_year: int = 252,
                 max_abs_log_ret: float = 1.5) -> pd.Series:
    """Volatilidad realizada anualizada en % (ventana móvil de log-retornos, ddof=1)."""
    c = close.where(close > 0)
    r = np.log(c / c.shift(1))
    r = r.where(r.abs() <= max_abs_log_ret)  # saltos imposibles (redenominaciones) fuera
    return (r.rolling(window, min_periods=window).std(ddof=1) * np.sqrt(periods_per_year) * 100).rename("rvol")


def expanding_percentile(x: pd.Series, min_history: int = 20) -> pd.Series:
    """Percentil del valor actual frente a TODOS los valores previos y él mismo (sin futuro)."""
    hist: list[float] = []
    out = np.full(len(x), np.nan)
    for i, v in enumerate(x.to_numpy(float)):
        if np.isnan(v):
            continue
        bisect.insort(hist, v)
        if len(hist) >= min_history:
            out[i] = bisect.bisect_right(hist, v + 1e-12) / len(hist) * 100
    return pd.Series(out, index=x.index, name="rvol_pct")


def band_for(percentile: float) -> str:
    if np.isnan(percentile):
        return "sin_datos"
    for top, name, _ in BANDS:
        if percentile <= top:
            return name
    return "panico"


def daily_vol_proxy(daily_close: pd.Series, window: int = 30) -> pd.DataFrame:
    """VIX proxy diario: vol realizada, percentil y banda."""
    rv = realized_vol(daily_close, window)
    pct = expanding_percentile(rv)
    return pd.DataFrame({"rvol": rv, "rvol_pct": pct, "vol_band": pct.map(band_for)})


def align_daily_to_bars(daily: pd.DataFrame, bars_index: pd.DatetimeIndex) -> pd.DataFrame:
    """Lleva valores diarios a velas intradía SIN mirar al futuro.

    El valor del día D solo se conoce cuando D cierra, así que una vela H4 del día D ve el
    valor del día D-1 (o el último disponible antes).
    """
    known_from = daily.copy()
    known_from.index = known_from.index + pd.Timedelta(days=1)
    return known_from.reindex(bars_index, method="ffill")
