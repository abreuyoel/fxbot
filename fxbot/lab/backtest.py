"""Motor de backtest vela a vela, con costos y reglas de riesgo.

Supuestos (conservadores a propósito):
- Las velas son precios BID (como MetaTrader). Comprar paga el ASK = bid + spread.
- La señal de la vela t se ejecuta a la APERTURA de la vela t+1.
- Si en una misma vela se tocan el stop y el objetivo, se asume que saltó el STOP.
- Si el precio abre más allá del stop (gap de fin de semana o noticia), se sale a la
  apertura, peor que el stop. El objetivo es una orden límite: sin deslizamiento.
- Una posición a la vez por instrumento. Las señales con una posición abierta se ignoran.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from fxbot.instruments import Instrument, get_instrument
from fxbot.lab.costs import CostModel, rollover_nights
from fxbot.risk.sizing import RiskLimits, position_size

CONTEXT_SKIP = {"signal", "sl_dist", "tp_dist", "size_mult"}


@dataclass
class BacktestConfig:
    symbol: str = "EURUSD"
    initial_capital: float = 500.0
    costs: CostModel = field(default_factory=CostModel)
    limits: RiskLimits = field(default_factory=RiskLimits)
    entry_start: pd.Timestamp | None = None   # solo se abren operaciones dentro de esta ventana
    entry_end: pd.Timestamp | None = None


@dataclass
class BacktestResult:
    trades: pd.DataFrame
    equity: pd.Series
    config: BacktestConfig
    skipped_small: int = 0     # señales descartadas porque ni 0.01 lotes cabía en el riesgo
    skipped_limits: int = 0    # señales bloqueadas por el stop diario/semanal
    halted_at: pd.Timestamp | None = None  # cuándo se apagó el bot por drawdown máximo


def _spread_series(df: pd.DataFrame, inst: Instrument, costs: CostModel) -> np.ndarray:
    if costs.spread_pips is not None:
        pips = np.full(len(df), costs.spread_pips)
    elif "spread_pips" in df:
        pips = df["spread_pips"].fillna(inst.typical_spread_pips).to_numpy(float)
    else:
        pips = np.full(len(df), inst.typical_spread_pips)
    return pips * costs.spread_mult * inst.pip_size


def run_backtest(df: pd.DataFrame, signals: pd.DataFrame, cfg: BacktestConfig) -> BacktestResult:
    inst = get_instrument(cfg.symbol)
    c, lim = cfg.costs, cfg.limits
    idx = df.index
    o, h, l, cl = (df[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    spr = _spread_series(df, inst, c)
    slip = c.slippage_pips * inst.pip_size
    sig = signals["signal"].to_numpy(int)
    sl_d = signals["sl_dist"].to_numpy(float)
    tp_d = signals["tp_dist"].to_numpy(float)
    smult = signals["size_mult"].to_numpy(float)
    ctx_cols = [k for k in signals.columns if k not in CONTEXT_SKIP]

    # claves de día y semana precalculadas: crear un Timestamp por vela era lo más lento del bucle
    day_keys = idx.floor("D").asi8
    iso = idx.isocalendar()
    week_keys = (iso["year"].to_numpy() * 100 + iso["week"].to_numpy()).astype(np.int64)

    start_i = 0 if cfg.entry_start is None else int(idx.searchsorted(cfg.entry_start))
    end_i = len(df) if cfg.entry_end is None else int(idx.searchsorted(cfg.entry_end))

    cash = cfg.initial_capital
    peak = cash
    day_key = week_key = None
    day_start_eq = week_start_eq = cash
    pos: dict | None = None
    trades: list[dict] = []
    eq = np.full(len(df), np.nan)
    skipped_small = skipped_limits = 0
    halted_at = None

    def close_pos(i: int, price: float, reason: str) -> None:
        nonlocal cash, pos
        p = pos
        pnl_price = (price - p["entry"]) * p["side"]
        pip_val = inst.pip_value_per_lot(price)
        gross = pnl_price / inst.pip_size * pip_val * p["lots"]
        nights = rollover_nights(p["entry_time"], idx[i])
        swap_pips = c.swap_long_pips if p["side"] > 0 else c.swap_short_pips
        swap = swap_pips * pip_val * p["lots"] * nights
        commission = c.commission_per_lot_rt * p["lots"]
        net = gross + swap - commission
        cash += net
        trades.append({
            "entry_time": p["entry_time"], "exit_time": idx[i], "side": "compra" if p["side"] > 0 else "venta",
            "lots": p["lots"], "entry": p["entry"], "exit": price, "sl": p["sl"], "tp": p["tp"],
            "gross_usd": gross, "commission_usd": commission, "swap_usd": swap, "pnl_usd": net,
            "risk_usd": p["risk_usd"], "risk_pct": p["risk_pct"],
            "r_multiple": net / p["risk_usd"] if p["risk_usd"] > 0 else 0.0,
            "exit_reason": reason, "bars": i - p["entry_i"] + 1, "equity_after": cash, **p["ctx"],
        })
        pos = None

    def check_exit(i: int) -> None:
        p = pos
        s = spr[i]
        if p["side"] > 0:   # largo: sale vendiendo al BID
            if o[i] <= p["sl"]:
                close_pos(i, o[i] - slip, "stop (gap)")
            elif o[i] >= p["tp"]:
                close_pos(i, o[i], "objetivo (gap)")
            elif l[i] <= p["sl"]:
                close_pos(i, p["sl"] - slip, "stop")
            elif h[i] >= p["tp"]:
                close_pos(i, p["tp"], "objetivo")
        else:               # corto: sale comprando al ASK = bid + spread
            if o[i] + s >= p["sl"]:
                close_pos(i, o[i] + s + slip, "stop (gap)")
            elif o[i] + s <= p["tp"]:
                close_pos(i, o[i] + s, "objetivo (gap)")
            elif h[i] + s >= p["sl"]:
                close_pos(i, p["sl"] + slip, "stop")
            elif l[i] + s <= p["tp"]:
                close_pos(i, p["tp"], "objetivo")

    for i in range(len(df)):
        dk, wk = day_keys[i], week_keys[i]
        if dk != day_key:
            day_key, day_start_eq = dk, cash
        if wk != week_key:
            week_key, week_start_eq = wk, cash

        # 1) entrada pendiente de la señal de la vela anterior
        if pos is None and halted_at is None and i > 0 and start_i <= i < end_i and sig[i - 1] != 0:
            side = int(sig[i - 1])
            day_dd = (cash - day_start_eq) / day_start_eq * 100
            week_dd = (cash - week_start_eq) / week_start_eq * 100
            if day_dd <= -lim.daily_loss_pct or week_dd <= -lim.weekly_loss_pct:
                skipped_limits += 1
            else:
                entry = o[i] + spr[i] + slip if side > 0 else o[i] - slip
                pip_val = inst.pip_value_per_lot(entry)
                extra = c.commission_per_lot_rt + (spr[i] / inst.pip_size + 2 * c.slippage_pips) * pip_val
                lots = position_size(cash, lim.risk_pct * smult[i - 1], sl_d[i - 1], entry, inst, extra,
                                     lim.min_lot_max_risk_pct * smult[i - 1])
                if lots == 0:
                    skipped_small += 1
                else:
                    sl = entry - side * sl_d[i - 1]
                    tp = entry + side * tp_d[i - 1]
                    risk_usd = lots * (sl_d[i - 1] / inst.pip_size * pip_val + extra)
                    pos = {"side": side, "entry": entry, "sl": sl, "tp": tp, "lots": lots, "entry_i": i,
                           "entry_time": idx[i], "risk_usd": risk_usd, "risk_pct": risk_usd / cash * 100,
                           "ctx": {k: signals[k].iat[i - 1] for k in ctx_cols}}

        # 2) salida dentro de la vela (incluida la vela de entrada)
        if pos is not None:
            check_exit(i)

        # 3) valor de la cuenta al cierre y apagado por drawdown máximo
        mtm = cash
        if pos is not None:
            px = cl[i] if pos["side"] > 0 else cl[i] + spr[i]
            mtm += (px - pos["entry"]) * pos["side"] / inst.pip_size * inst.pip_value_per_lot(px) * pos["lots"]
        peak = max(peak, mtm)
        if halted_at is None and (peak - mtm) / peak * 100 >= lim.max_drawdown_pct:
            if pos is not None:
                close_pos(i, cl[i] if pos["side"] > 0 else cl[i] + spr[i], "apagado por drawdown")
            mtm = cash
            halted_at = idx[i]
        eq[i] = mtm

        # 4) fin de la ventana: se cierra lo abierto
        if i == end_i - 1 and pos is not None and cfg.entry_end is not None:
            close_pos(i, cl[i] if pos["side"] > 0 else cl[i] + spr[i], "fin de ventana")
            eq[i] = cash
        if cfg.entry_end is not None and i >= end_i - 1:
            eq[i + 1:] = cash
            break

    if pos is not None:
        last = len(df) - 1
        close_pos(last, cl[last] if pos["side"] > 0 else cl[last] + spr[last], "fin de datos")
        eq[last] = cash

    equity = pd.Series(eq, index=idx, name="equity").iloc[start_i:]
    trades_df = pd.DataFrame(trades)
    return BacktestResult(trades_df, equity.ffill(), cfg, skipped_small, skipped_limits, halted_at)
