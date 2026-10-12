"""Tamaño de posición y límites de riesgo.

Estas reglas son DURAS: ni la IA ni la optimización de parámetros pueden cambiarlas.
Solo tú, editando la configuración a mano.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from fxbot.instruments import Instrument


@dataclass(frozen=True)
class RiskLimits:
    risk_pct: float = 1.0           # % del capital arriesgado por operación
    daily_loss_pct: float = 2.0     # pérdida del día que bloquea nuevas entradas hasta mañana
    weekly_loss_pct: float = 5.0    # pérdida de la semana que bloquea hasta el lunes
    max_drawdown_pct: float = 20.0  # caída desde el máximo que APAGA el bot (reactivación manual)
    # Con capital chico, a veces ni el lote mínimo (0.01) cabe en risk_pct. Si el lote mínimo
    # arriesga como mucho este %, se opera con él (y queda marcado); si no, se descarta la señal.
    min_lot_max_risk_pct: float = 1.5


def position_size(equity: float, risk_pct: float, sl_dist: float, price: float,
                  inst: Instrument, extra_cost_per_lot: float = 0.0, min_lot_max_risk_pct: float = 0.0) -> float:
    """Lotes tales que, si salta el stop, se pierde como mucho risk_pct % del capital.

    extra_cost_per_lot: comisión + spread + deslizamiento esperados por lote, en USD.
    min_lot_max_risk_pct: si ni el lote mínimo cabe en risk_pct, se acepta el lote mínimo
        siempre que su riesgo no pase de este % (0 = nunca).
    Devuelve 0 si no se puede operar sin pasar los límites (con capital chico: mejor no operar).
    """
    if equity <= 0 or sl_dist <= 0 or risk_pct <= 0:
        return 0.0
    risk_usd = equity * risk_pct / 100
    loss_per_lot = sl_dist / inst.pip_size * inst.pip_value_per_lot(price) + extra_cost_per_lot
    lots = inst.round_lots(risk_usd / loss_per_lot)
    if lots >= inst.min_lot:
        return lots
    min_lot_risk_pct = inst.min_lot * loss_per_lot / equity * 100
    return inst.min_lot if min_lot_risk_pct <= min_lot_max_risk_pct else 0.0


def kelly_from_trades(r_multiples: np.ndarray) -> float:
    """Kelly a partir de los resultados de la estrategia, en múltiplos de R.

    f* = p − (1 − p) / b, con p = % de ganadoras y b = ganancia media / pérdida media.
    Se usa como TOPE de sanidad (nunca arriesgar más de ¼ de Kelly), no como objetivo.
    """
    r = np.asarray(r_multiples, float)
    wins, losses = r[r > 0], r[r < 0]
    if not len(wins) or not len(losses):
        return 0.0
    p = len(wins) / len(r)
    b = wins.mean() / abs(losses.mean())
    return float(max(0.0, p - (1 - p) / b))
