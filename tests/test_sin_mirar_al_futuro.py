"""Ningún indicador ni señal puede usar datos de velas futuras (look-ahead bias).

Método: se calcula todo con N velas y con las primeras K. Los valores de las primeras K
deben ser idénticos; si cambian, algo está mirando al futuro.
"""
import numpy as np
import pandas as pd

from fxbot.indicators.core import all_indicators
from fxbot.strategies.base import daily_context
from fxbot.strategies.trend_ema_adx import TrendEmaAdx


def synthetic_h1(n=24 * 200, seed=3):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2022-01-03", periods=n, freq="h", tz="UTC")
    idx = idx[idx.dayofweek < 5][: n // 2]
    r = rng.normal(0, 0.0012, len(idx)) + np.sin(np.arange(len(idx)) / 300) * 0.0003
    close = 1.1 * np.exp(np.cumsum(r))
    open_ = np.r_[close[0], close[:-1]]
    high = np.maximum(open_, close) * (1 + np.abs(rng.normal(0, 0.0005, len(idx))))
    low = np.minimum(open_, close) * (1 - np.abs(rng.normal(0, 0.0005, len(idx))))
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close,
                         "volume": rng.integers(100, 1000, len(idx)).astype(float)}, index=idx)


def test_indicadores_no_cambian_al_agregar_velas():
    df = synthetic_h1()
    k = len(df) * 2 // 3
    full, part = all_indicators(df).iloc[:k], all_indicators(df.iloc[:k])
    pd.testing.assert_frame_equal(full, part, check_exact=False, rtol=1e-9, atol=1e-12)


def test_contexto_diario_no_mira_al_futuro():
    df = synthetic_h1()
    k = len(df) * 2 // 3
    full, part = daily_context(df).iloc[:k], daily_context(df.iloc[:k])
    pd.testing.assert_frame_equal(full, part)


def test_senales_no_cambian_al_agregar_velas():
    df = synthetic_h1()
    k = len(df) * 2 // 3
    s = TrendEmaAdx()
    pd.testing.assert_frame_equal(s.signals(df).iloc[:k], s.signals(df.iloc[:k]))
