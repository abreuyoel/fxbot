"""Laboratorio de la Fase 1: backtest + what-if + Monte Carlo + walk-forward + veredicto.

Uso:
    python -m fxbot.lab.run --muestra                          # datos de ejemplo (solo prueba técnica)
    python -m fxbot.lab.run --csv datos/EURUSD_H1.csv --tf 4h   # tus datos reales
    python -m fxbot.lab.run --csv datos/EURUSD_H1.csv --walkforward
"""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict, replace
from pathlib import Path

import pandas as pd

from fxbot.data.loaders import daily_bars, load_ohlc_csv, load_sample_eurusd_h1, resample_ohlc, validate_ohlc
from fxbot.lab.backtest import BacktestConfig, run_backtest
from fxbot.lab.costs import CostModel
from fxbot.lab.metrics import EXPLAIN, breakdown, compute_metrics
from fxbot.lab.montecarlo import monte_carlo
from fxbot.lab.walkforward import walk_forward
from fxbot.risk.sizing import RiskLimits, kelly_from_trades
from fxbot.strategies.base import daily_context
from fxbot.strategies.trend_ema_adx import TrendEmaAdx

# Criterios para aprobar la Fase 1 (ver docs/PROMPT_MAESTRO.md)
GATE = {"min_trades": 300, "min_pf_oos": 1.3, "max_ruin_pct": 5.0}


def what_if(df: pd.DataFrame, sig: pd.DataFrame, cfg: BacktestConfig) -> pd.DataFrame:
    scenarios = {
        "base": cfg,
        "spread x2": replace(cfg, costs=cfg.costs.scaled(spread_mult=cfg.costs.spread_mult * 2)),
        "deslizamiento x3": replace(cfg, costs=cfg.costs.scaled(slippage_pips=cfg.costs.slippage_pips * 3)),
        "cuenta estándar (sin comisión, spread ×6)": replace(cfg, costs=cfg.costs.scaled(commission_per_lot_rt=0.0,
                                                                           spread_mult=cfg.costs.spread_mult + 5)),
        "riesgo 0.5 %": replace(cfg, limits=replace(cfg.limits, risk_pct=0.5)),
        "riesgo 2 %": replace(cfg, limits=replace(cfg.limits, risk_pct=2.0)),
    }
    rows = {}
    for name, c in scenarios.items():
        r = run_backtest(df, sig, c)
        m = compute_metrics(r.trades, r.equity, c.initial_capital)
        rows[name] = {k: m.get(k) for k in ("operaciones", "retorno_total_pct", "max_drawdown_pct",
                                            "profit_factor", "expectancy_r", "mensual_promedio_pct")}
        rows[name]["apagado_por_dd"] = r.halted_at is not None
    return pd.DataFrame(rows).T


def verdict(n_trades: int, pf_oos: float | None, ruin: float) -> tuple[bool, list[str]]:
    reasons = []
    if n_trades < GATE["min_trades"]:
        reasons.append(f"solo {n_trades} operaciones fuera de muestra (se piden ≥ {GATE['min_trades']})")
    if pf_oos is None or pf_oos < GATE["min_pf_oos"]:
        reasons.append(f"profit factor fuera de muestra {pf_oos} (< {GATE['min_pf_oos']})")
    if ruin >= GATE["max_ruin_pct"]:
        reasons.append(f"probabilidad de ruina {ruin} % (≥ {GATE['max_ruin_pct']} %)")
    return not reasons, reasons


def _print_metrics(m: dict) -> None:
    for k, v in m.items():
        hint = EXPLAIN.get(k)
        print(f"  {k:<24} {v!s:>10}" + (f"   ← {hint}" if hint else ""))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Laboratorio de backtesting (Fase 1)")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--csv", help="CSV de velas (ver fxbot/data/loaders.py)")
    src.add_argument("--muestra", action="store_true", help="EURUSD H1 de ejemplo (no sirve para validar)")
    ap.add_argument("--tz", default="UTC", help="zona horaria del CSV (MT5 suele ser Etc/GMT-2 o Etc/GMT-3)")
    ap.add_argument("--simbolo", default="EURUSD")
    ap.add_argument("--tf", default="4h", help="temporalidad de trabajo: 1h, 4h, D")
    ap.add_argument("--capital", type=float, default=500.0)
    ap.add_argument("--riesgo", type=float, default=1.0, help="% del capital por operación")
    ap.add_argument("--dd-max", type=float, default=20.0, help="% de caída que apaga el bot")
    ap.add_argument("--comision", type=float, default=7.0, help="USD por lote ida y vuelta")
    ap.add_argument("--walkforward", action="store_true", help="optimización walk-forward (tarda más)")
    ap.add_argument("--wf-entreno-meses", type=int, default=24)
    ap.add_argument("--wf-prueba-meses", type=int, default=6)
    ap.add_argument("--salida", default="resultados")
    a = ap.parse_args(argv)

    raw = load_sample_eurusd_h1() if a.muestra else load_ohlc_csv(a.csv, tz=a.tz)
    rep = validate_ohlc(raw)
    print(f"Datos: {rep.rows} velas, {rep.start} → {rep.end}")
    for p in rep.problems:
        print(f"  ⚠ {p}")
    tf = a.tf.lower()
    df = raw if tf in ("1h", "h1") else daily_bars(raw) if tf in ("d", "1d", "d1") else resample_ohlc(raw, a.tf)
    print(f"Temporalidad {a.tf}: {len(df)} velas")

    cfg = BacktestConfig(symbol=a.simbolo, initial_capital=a.capital,
                         costs=CostModel(commission_per_lot_rt=a.comision),
                         limits=RiskLimits(risk_pct=a.riesgo, max_drawdown_pct=a.dd_max))
    strat = TrendEmaAdx()
    ctx = daily_context(df)
    sig = strat.signals(df, ctx)
    res = run_backtest(df, sig, cfg)
    m = compute_metrics(res.trades, res.equity, cfg.initial_capital)

    print(f"\n== Backtest completo — {strat.name} {asdict(strat)} ==")
    _print_metrics(m)
    if res.skipped_small:
        print(f"  ⚠ {res.skipped_small} señales descartadas: con este capital ni 0.01 lotes cabía en el riesgo")
    if res.skipped_limits:
        print(f"  {res.skipped_limits} señales bloqueadas por el stop diario/semanal")
    if res.halted_at is not None:
        print(f"  ⛔ El bot se habría APAGADO el {res.halted_at} por llegar al drawdown máximo")

    if len(res.trades):
        print("\n== Por banda del VIX proxy (volatilidad al entrar) ==")
        print(breakdown(res.trades, "vol_band").to_string())
        print("\n== Por régimen de mercado ==")
        print(breakdown(res.trades, "regime").to_string())
        print("\n== What-if ==")
        print(what_if(df, sig, cfg).to_string())

    oos = res.trades
    label = "backtest completo (EN muestra: optimista)"
    wf = None
    if a.walkforward:
        print("\n== Walk-forward (solo cuenta lo que pasa fuera de muestra) ==")
        wf = walk_forward(df, cfg, train=pd.DateOffset(months=a.wf_entreno_meses),
                          test=pd.DateOffset(months=a.wf_prueba_meses), min_trades=5 if a.muestra else 20)
        print(wf.windows.to_string())
        oos, label = wf.oos_trades, "walk-forward (FUERA de muestra)"

    print(f"\n== Monte Carlo sobre {label} ==")
    mc = None
    if len(oos) >= 2:
        mc = monte_carlo(oos["r_multiple"], risk_pct=a.riesgo, ruin_drawdown_pct=a.dd_max)
        for k, v in mc.as_dict().items():
            print(f"  {k:<20} {v}")
        k = kelly_from_trades(oos["r_multiple"].to_numpy())
        print(f"  Kelly de la estrategia: {k * 100:.1f} % → tope sano (¼ Kelly): {k * 25:.2f} % por operación")
    else:
        print("  No hay suficientes operaciones.")

    pf_oos = None
    if len(oos):
        w, lo = oos.loc[oos.pnl_usd > 0, "pnl_usd"].sum(), oos.loc[oos.pnl_usd < 0, "pnl_usd"].sum()
        pf_oos = round(float(w / abs(lo)), 2) if lo else None
    if a.walkforward:
        ok, why = verdict(len(oos), pf_oos, mc.prob_ruin_pct if mc else 100.0)
    else:
        ok, why = False, ["falta correr con --walkforward (sin validación fuera de muestra no hay veredicto)"]
    print("\n== Veredicto Fase 1 ==")
    print("  ✅ APROBADA: puede pasar a demo" if ok else "  ❌ NO APROBADA:\n    - " + "\n    - ".join(why))
    if a.muestra:
        print("  (Con los datos de muestra el veredicto no significa nada: son ~10 meses.)")

    out = Path(a.salida)
    out.mkdir(parents=True, exist_ok=True)
    res.trades.to_csv(out / "operaciones.csv", index=False)
    res.equity.to_csv(out / "equity.csv")
    if wf is not None:
        wf.windows.to_csv(out / "walkforward_ventanas.csv", index=False)
        wf.oos_trades.to_csv(out / "walkforward_operaciones.csv", index=False)
    summary = {"metricas": m, "montecarlo": mc.as_dict() if mc else None, "aprobada": ok, "motivos": why,
               "estrategia": {"nombre": strat.name, **asdict(strat)}}
    (out / "resumen.json").write_text(json.dumps(summary, indent=2, default=str, ensure_ascii=False))
    print(f"\nArchivos en {out}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
