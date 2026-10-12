"""Walk-forward: optimizar en una ventana, validar en la siguiente que NUNCA se vio.

    [---- entrenamiento ----][- prueba -]
                 [---- entrenamiento ----][- prueba -]
                              [---- entrenamiento ----][- prueba -]

Solo cuentan los resultados de las ventanas de PRUEBA (fuera de muestra). Si la
estrategia solo gana en entrenamiento, está sobreajustada y no sirve.
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass, replace

import numpy as np
import pandas as pd

from fxbot.lab.backtest import BacktestConfig, run_backtest
from fxbot.strategies.base import daily_context
from fxbot.strategies.trend_ema_adx import TrendEmaAdx

DEFAULT_GRID = {
    "fast": [10, 20],
    "slow": [50, 100],
    "adx_min": [15.0, 20.0, 25.0],
    "atr_mult": [1.5, 2.5],
    "rr": [1.5, 2.0],
}


@dataclass
class WalkForwardResult:
    windows: pd.DataFrame         # una fila por ventana: parámetros elegidos y resultado fuera de muestra
    oos_trades: pd.DataFrame      # todas las operaciones fuera de muestra, juntas


def _score(trades: pd.DataFrame, min_trades: int) -> float:
    if len(trades) < min_trades:
        return -np.inf
    r = trades["r_multiple"]
    return float(r.mean() * np.sqrt(len(r)))  # premia ventaja consistente, no 3 operaciones con suerte


def walk_forward(df: pd.DataFrame, cfg: BacktestConfig, grid: dict | None = None,
                 train: pd.DateOffset = pd.DateOffset(years=2), test: pd.DateOffset = pd.DateOffset(months=6),
                 min_trades: int = 20) -> WalkForwardResult:
    grid = grid or DEFAULT_GRID
    keys = list(grid)
    combos = [dict(zip(keys, vals)) for vals in itertools.product(*grid.values())]
    ctx = daily_context(df)
    cache = {i: TrendEmaAdx(**p).signals(df, ctx) for i, p in enumerate(combos)}

    def run(i: int, start, end):
        mask = (df.index >= start) & (df.index < end)
        c = replace(cfg, entry_start=None, entry_end=df.index[mask][-1] + pd.Timedelta(seconds=1))
        return run_backtest(df[mask], cache[i][mask], c)

    rows, oos = [], []
    start = df.index[0]
    while True:
        tr_end = start + train
        te_end = tr_end + test
        if te_end > df.index[-1] + pd.Timedelta(days=1):
            break
        scores = [_score(run(i, start, tr_end).trades, min_trades) for i in range(len(combos))]
        best = int(np.argmax(scores))
        if not np.isfinite(scores[best]):
            rows.append({"train_start": start, "test_start": tr_end, "test_end": te_end, "params": None,
                         "train_score": None, "oos_trades": 0, "oos_expectancy_r": None, "oos_pnl_usd": 0.0})
        else:
            res = run(best, tr_end, te_end)
            t = res.trades
            if len(t):
                oos.append(t.assign(window=tr_end))
            rows.append({"train_start": start, "test_start": tr_end, "test_end": te_end, "params": combos[best],
                         "train_score": round(scores[best], 3), "oos_trades": len(t),
                         "oos_expectancy_r": round(float(t["r_multiple"].mean()), 3) if len(t) else None,
                         "oos_pnl_usd": round(float(t["pnl_usd"].sum()), 2) if len(t) else 0.0})
        start = start + test
    return WalkForwardResult(pd.DataFrame(rows), pd.concat(oos, ignore_index=True) if oos else pd.DataFrame())
