"""Métricas de rendimiento, con su explicación en lenguaje simple."""
from __future__ import annotations

import numpy as np
import pandas as pd

EXPLAIN = {
    "operaciones": "Cuántas operaciones hizo. Con menos de ~100 los resultados son casi puro azar.",
    "win_rate_pct": "% de operaciones ganadoras. Solo no dice nada: puedes ganar con 35 % si las ganadoras son grandes.",
    "profit_factor": "Ganancias totales ÷ pérdidas totales. >1 gana; >1.3 fuera de muestra es una ventaja seria.",
    "expectancy_r": "Cuánto gana en promedio cada operación, en múltiplos del riesgo (R). 0.1R = por cada $10 arriesgados, $1 de ganancia media.",
    "retorno_total_pct": "Cuánto creció (o cayó) la cuenta en todo el período.",
    "cagr_pct": "Rendimiento anual compuesto equivalente.",
    "mensual_promedio_pct": "Rendimiento mensual promedio (la meta realista es 1-3 %).",
    "meses_positivos_pct": "% de meses que cerraron en ganancia.",
    "max_drawdown_pct": "La peor caída desde un máximo. Es lo que vas a SENTIR: prepárate para verla en real.",
    "sharpe": "Rendimiento por unidad de volatilidad (anualizado). >1 bueno, >2 sospechoso de sobreajuste.",
    "sortino": "Como Sharpe pero solo castiga la volatilidad a la baja.",
    "peor_racha_perdedora": "Máximo de pérdidas seguidas. Si te asusta, el bot no es para ti (o arriesga menos).",
    "costos_usd": "Comisiones + swaps pagados. Compáralo con la ganancia bruta.",
}


def max_drawdown_pct(equity: pd.Series) -> float:
    e = equity.dropna()
    if e.empty:
        return 0.0
    dd = (e.cummax() - e) / e.cummax()
    return float(dd.max() * 100)


def longest_losing_streak(pnl: np.ndarray) -> int:
    best = cur = 0
    for x in pnl:
        cur = cur + 1 if x < 0 else 0
        best = max(best, cur)
    return best


def compute_metrics(trades: pd.DataFrame, equity: pd.Series, initial_capital: float) -> dict:
    m: dict = {"operaciones": int(len(trades))}
    e = equity.dropna()
    final = float(e.iloc[-1]) if len(e) else initial_capital
    m["capital_final"] = round(final, 2)
    m["retorno_total_pct"] = round((final / initial_capital - 1) * 100, 2)
    m["max_drawdown_pct"] = round(max_drawdown_pct(e), 2)

    if len(e) > 1:
        days = (e.index[-1] - e.index[0]).total_seconds() / 86400
        m["cagr_pct"] = round(((final / initial_capital) ** (365.25 / days) - 1) * 100, 2) if days > 30 and final > 0 else None
        daily = e.resample("D").last().dropna()
        rets = daily.pct_change().dropna()
        rets = rets[daily.index[1:].dayofweek < 5] if len(rets) else rets
        sd = rets.std()
        m["sharpe"] = round(float(rets.mean() / sd * np.sqrt(252)), 2) if sd and sd > 0 else None
        downside = rets[rets < 0]
        dsd = np.sqrt((downside ** 2).mean()) if len(downside) else 0
        m["sortino"] = round(float(rets.mean() / dsd * np.sqrt(252)), 2) if dsd > 0 else None
        monthly = pd.concat([pd.Series([initial_capital], index=[e.index[0] - pd.Timedelta(seconds=1)]),
                             e.resample("ME").last()]).pct_change().dropna()
        m["mensual_promedio_pct"] = round(float(monthly.mean() * 100), 2) if len(monthly) else None
        m["meses_positivos_pct"] = round(float((monthly > 0).mean() * 100), 1) if len(monthly) else None
    if len(trades):
        pnl = trades["pnl_usd"].to_numpy()
        wins, losses = pnl[pnl > 0], pnl[pnl < 0]
        m["win_rate_pct"] = round(len(wins) / len(pnl) * 100, 1)
        m["profit_factor"] = round(float(wins.sum() / abs(losses.sum())), 2) if len(losses) else None
        m["expectancy_r"] = round(float(trades["r_multiple"].mean()), 3)
        m["ganancia_media_usd"] = round(float(wins.mean()), 2) if len(wins) else 0.0
        m["perdida_media_usd"] = round(float(losses.mean()), 2) if len(losses) else 0.0
        m["peor_racha_perdedora"] = longest_losing_streak(pnl)
        m["costos_usd"] = round(float(trades["commission_usd"].sum() - trades["swap_usd"].sum()), 2)
        m["duracion_media_velas"] = round(float(trades["bars"].mean()), 1)
    return m


def breakdown(trades: pd.DataFrame, by: str) -> pd.DataFrame:
    """Resultados agrupados (por banda de volatilidad, régimen, lado, hora...)."""
    if trades.empty or by not in trades:
        return pd.DataFrame()
    g = trades.groupby(by)
    out = pd.DataFrame({
        "operaciones": g.size(),
        "win_rate_pct": g["pnl_usd"].apply(lambda s: (s > 0).mean() * 100).round(1),
        "expectancy_r": g["r_multiple"].mean().round(3),
        "pnl_usd": g["pnl_usd"].sum().round(2),
    })
    return out.sort_values("operaciones", ascending=False)
