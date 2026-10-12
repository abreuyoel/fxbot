"""Monte Carlo sobre los resultados de las operaciones.

Pregunta que responde: "si el futuro se parece al pasado pero las operaciones salen en
otro orden (o algunas se repiten y otras no), ¿qué tan mal me puede ir?". Un backtest es
UNA sola historia; esto genera miles de historias posibles con las mismas operaciones.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class MonteCarloResult:
    simulations: int
    trades_per_sim: int
    ruin_threshold_pct: float
    prob_ruin_pct: float               # % de historias que tocaron el drawdown de apagado
    drawdown_p50: float
    drawdown_p95: float
    drawdown_p99: float
    final_return_p5: float
    final_return_p50: float
    final_return_p95: float
    prob_loss_pct: float               # % de historias que terminaron perdiendo dinero
    losing_streak_p95: int

    def as_dict(self) -> dict:
        return self.__dict__.copy()


def monte_carlo(r_multiples, risk_pct: float = 1.0, simulations: int = 5000,
                trades_per_sim: int | None = None, ruin_drawdown_pct: float = 20.0,
                method: str = "bootstrap", seed: int = 42) -> MonteCarloResult:
    """r_multiples: resultado de cada operación en múltiplos de R (pnl / riesgo).
    method: "bootstrap" (con reemplazo: también cambia QUÉ operaciones salen) o
            "permutation" (mismas operaciones en otro orden).
    """
    r = np.asarray(r_multiples, float)
    if len(r) < 2:
        raise ValueError("Hacen falta al menos 2 operaciones")
    n = trades_per_sim or len(r)
    rng = np.random.default_rng(seed)
    if method == "permutation":
        n = len(r)
        sample = np.array([rng.permutation(r) for _ in range(simulations)])
    else:
        sample = r[rng.integers(0, len(r), size=(simulations, n))]

    growth = np.maximum(1 + sample * risk_pct / 100, 0.0)
    equity = np.cumprod(growth, axis=1)
    equity = np.concatenate([np.ones((simulations, 1)), equity], axis=1)
    peak = np.maximum.accumulate(equity, axis=1)
    dd = ((peak - equity) / peak).max(axis=1) * 100
    final = (equity[:, -1] - 1) * 100

    streak = np.zeros(simulations, int)
    best = np.zeros(simulations, int)
    for j in range(n):
        streak = np.where(sample[:, j] < 0, streak + 1, 0)
        best = np.maximum(best, streak)

    p = lambda a, q: round(float(np.percentile(a, q)), 2)  # noqa: E731
    return MonteCarloResult(
        simulations=simulations, trades_per_sim=n, ruin_threshold_pct=ruin_drawdown_pct,
        prob_ruin_pct=round(float((dd >= ruin_drawdown_pct).mean() * 100), 2),
        drawdown_p50=p(dd, 50), drawdown_p95=p(dd, 95), drawdown_p99=p(dd, 99),
        final_return_p5=p(final, 5), final_return_p50=p(final, 50), final_return_p95=p(final, 95),
        prob_loss_pct=round(float((final < 0).mean() * 100), 2),
        losing_streak_p95=int(np.percentile(best, 95)),
    )
