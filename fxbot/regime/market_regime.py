"""Régimen de mercado multi-timeframe (alcista / bajista / lateral / volátil).

Port de calcMarketRegime() de Caracas-Portafolio. Nota honesta: allá se llama
"Gaussian HMM", pero no es un modelo oculto de Markov entrenado. Es una regla
ponderada: tendencia de 5/20/60 velas (pesos 0.25/0.50/0.25), con un umbral que baja
cuando el volumen confirma y un filtro de volatilidad. Funciona como heurística; un HMM
real (hmmlearn) puede probarse después en el laboratorio contra esta versión.

Hay dos calibraciones:
- "bvc": los umbrales originales (vol5 > 60 %, tendencia ±1.5/2.5 %), pensados para la BVC.
- "fx" (por defecto): los mismos pasos, pero los umbrales se expresan en desviaciones
  típicas del propio par. Con los umbrales de la BVC, EURUSD saldría "lateral" casi siempre.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

LABELS = ("alcista", "bajista", "lateral", "volatil")


def _regime_at(close: np.ndarray, volume: np.ndarray, calibration: str, periods_per_year: int) -> str:
    n = min(len(close), 60)
    if n < 10:
        return "lateral"
    c = close[-n:]
    v = volume[-n:]
    rets = np.diff(c) / np.where(c[:-1] == 0, 1, c[:-1])
    if not len(rets):
        return "lateral"

    def rstd(w):
        s = rets[-min(w, len(rets)):]
        return s.std() if len(s) >= 2 else 0.0

    vol5 = rstd(5) * np.sqrt(periods_per_year) * 100
    vol20 = rstd(20) * np.sqrt(periods_per_year) * 100

    trend5 = rets[-5:].sum() * 100 / 5
    last20 = c[max(0, len(c) - 20)]
    trend20 = (c[-1] - last20) / (last20 or 1) * 100
    trend60 = (c[-1] - c[0]) / (c[0] or 1) * 100
    avg10 = v[-10:].sum() / 10
    m = min(30, n)
    avg30 = v[-m:].sum() / m
    vol_part = avg10 / avg30 if avg30 > 0 else 1.0
    weighted = trend5 * 0.25 + trend20 * 0.50 + trend60 * 0.25

    if calibration == "bvc":
        if vol5 > 60 or (vol5 > 40 and vol5 / (vol20 or 1) > 1.8):
            return "volatil"
        threshold = 1.5 if vol_part > 1.2 else 2.5
    else:
        # Volátil: la vol de 5 velas casi duplica la de 20 (mismo criterio relativo del original)
        if vol20 > 0 and vol5 / vol20 > 1.8:
            return "volatil"
        sigma20 = rstd(20) * np.sqrt(20) * 100  # movimiento "normal" en 20 velas, en %
        threshold = sigma20 * (0.6 if vol_part > 1.2 else 1.0)
    if weighted > threshold:
        return "alcista"
    if weighted < -threshold:
        return "bajista"
    return "lateral"


def market_regime(df: pd.DataFrame, calibration: str = "fx", periods_per_year: int = 252) -> pd.Series:
    """Régimen vela por vela (cada valor usa solo las 60 velas previas e incluida la actual)."""
    close = df["close"].to_numpy(float)
    volume = df["volume"].to_numpy(float) if "volume" in df else np.ones(len(df))
    out = [_regime_at(close[: i + 1], volume[: i + 1], calibration, periods_per_year) for i in range(len(df))]
    return pd.Series(out, index=df.index, name="regime")
