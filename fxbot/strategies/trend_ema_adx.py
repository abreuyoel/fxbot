"""Estrategia base: cruce de EMAs filtrado por ADX, stops por ATR.

Es deliberadamente simple y conocida. Su papel en la Fase 1 es servir de LÍNEA BASE para
probar que el laboratorio mide bien (costos, Monte Carlo, walk-forward). Esperar que
gane mucho sería ingenuo; si una idea más compleja no le gana a esta fuera de muestra,
no vale la pena.

Reglas (evaluadas al cierre de cada vela):
    Compra: EMA rápida cruza por encima de la lenta, ADX > adx_min y +DI > −DI.
    Venta:  EMA rápida cruza por debajo de la lenta, ADX > adx_min y −DI > +DI.
    Stop:   atr_mult × ATR(14).   Objetivo: rr × stop.
    VIX proxy: en "pánico" (y opcionalmente "letargo") no se abre; en "tensión" se
    arriesga 25 % menos (la misma regla de la tarjeta de Caracas-Portafolio).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from fxbot.indicators.core import adx, atr, ema
from fxbot.strategies.base import daily_context


@dataclass
class TrendEmaAdx:
    fast: int = 20
    slow: int = 50
    adx_min: float = 20.0
    atr_mult: float = 2.0
    rr: float = 1.5
    blocked_bands: tuple[str, ...] = ("panico",)
    tension_size_mult: float = 0.75
    name: str = field(default="tendencia_ema_adx", init=False)

    def signals(self, df: pd.DataFrame, context: pd.DataFrame | None = None) -> pd.DataFrame:
        f, s = ema(df["close"], self.fast), ema(df["close"], self.slow)
        d = adx(df)
        a = atr(df)
        above = f > s
        cross_up = above & ~above.shift(1, fill_value=False) & s.shift(1).notna()
        cross_dn = ~above & above.shift(1, fill_value=False) & f.notna() & s.notna()
        trending = d["adx"] > self.adx_min
        long_ = cross_up & trending & (d["plus_di"] > d["minus_di"])
        short = cross_dn & trending & (d["minus_di"] > d["plus_di"])

        ctx = context if context is not None else daily_context(df)
        band = ctx["vol_band"].fillna("sin_datos")
        allowed = ~band.isin(self.blocked_bands)
        sig = np.where(long_ & allowed, 1, np.where(short & allowed, -1, 0))
        sig = np.where(a.notna(), sig, 0)

        out = pd.DataFrame(index=df.index)
        out["signal"] = sig.astype(int)
        out["sl_dist"] = (a * self.atr_mult).where(out["signal"] != 0, 0.0)
        out["tp_dist"] = out["sl_dist"] * self.rr
        out["size_mult"] = np.where(band == "tension", self.tension_size_mult, 1.0)
        out["vol_band"] = band
        out["regime"] = ctx["regime"].fillna("sin_datos")
        out["adx"] = d["adx"]
        return out
