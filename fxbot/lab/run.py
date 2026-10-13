"""Laboratorio de la Fase 1: backtest + what-if + Monte Carlo + walk-forward + veredicto.

Uso:
    python -m fxbot.lab.run --muestra                                   # datos de ejemplo (prueba técnica)
    python -m fxbot.lab.run --csv datos/EURUSD_H1.csv --walkforward
    python -m fxbot.lab.run --csv datos/*_H1.csv --walkforward          # varios pares: se juntan los resultados

El símbolo se toma del nombre del archivo (EURUSD_H1.csv → EURUSD).
"""
from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, replace
from pathlib import Path

import numpy as np
import pandas as pd

from fxbot.data.loaders import daily_bars, load_ohlc_csv, load_sample_eurusd_h1, resample_ohlc, validate_ohlc
from fxbot.instruments import INSTRUMENTS
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
        "cuenta estándar (sin comisión, spread ×6)": replace(cfg, costs=cfg.costs.scaled(
            commission_per_lot_rt=0.0, spread_mult=cfg.costs.spread_mult + 5)),
        "sin lote mínimo forzado": replace(cfg, limits=replace(cfg.limits, min_lot_max_risk_pct=0.0)),
        "apalancamiento 1:5": replace(cfg, leverage=5.0),
        "riesgo 0.5 %": replace(cfg, limits=replace(cfg.limits, risk_pct=0.5)),
        "riesgo 2 %": replace(cfg, limits=replace(cfg.limits, risk_pct=2.0)),
    }
    rows = {}
    for name, c in scenarios.items():
        r = run_backtest(df, sig, c)
        m = compute_metrics(r.trades, r.equity, c.initial_capital)
        rows[name] = {k: m.get(k) for k in ("operaciones", "retorno_total_pct", "max_drawdown_pct",
                                            "profit_factor", "expectancy_r", "mensual_promedio_pct")}
        rows[name]["descartadas"] = r.skipped_small + r.skipped_margin
        rows[name]["apagado_por_dd"] = r.halted_at is not None
    return pd.DataFrame(rows).T


def profit_factor_r(trades: pd.DataFrame) -> float | None:
    """Profit factor en múltiplos de R: no depende del capital, sirve para juntar varios pares."""
    if trades.empty:
        return None
    r = trades["r_multiple"]
    loss = -r[r < 0].sum()
    return round(float(r[r > 0].sum() / loss), 2) if loss > 0 else None


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


def symbol_from_path(path: str) -> str:
    name = Path(path).stem.upper()
    for sym in sorted(INSTRUMENTS, key=len, reverse=True):
        if re.match(rf"^{sym}(\b|_|$)", name):
            return sym
    raise SystemExit(f"No reconozco el símbolo en '{Path(path).name}'. Usa nombres como EURUSD_H1.csv "
                     f"o pasa --simbolo (conocidos: {', '.join(INSTRUMENTS)})")


def to_timeframe(raw: pd.DataFrame, tf: str) -> pd.DataFrame:
    tf = tf.lower()
    if tf in ("1h", "h1"):
        return raw
    if tf in ("d", "1d", "d1"):
        return daily_bars(raw)
    return resample_ohlc(raw, tf)


def run_symbol(symbol: str, raw: pd.DataFrame, a, verbose: bool) -> dict:
    rep = validate_ohlc(raw)
    print(f"\n######## {symbol} — {rep.rows} velas, {rep.start} → {rep.end}")
    for p in rep.problems:
        print(f"  ⚠ {p}")
    df = to_timeframe(raw, a.tf)
    print(f"Temporalidad {a.tf}: {len(df)} velas")

    cfg = BacktestConfig(symbol=symbol, initial_capital=a.capital, leverage=a.apalancamiento,
                         costs=CostModel(commission_per_lot_rt=a.comision),
                         limits=RiskLimits(risk_pct=a.riesgo, max_drawdown_pct=a.dd_max,
                                           min_lot_max_risk_pct=a.riesgo_tope))
    strat = TrendEmaAdx()
    ctx = daily_context(df)
    sig = strat.signals(df, ctx)
    res = run_backtest(df, sig, cfg)
    m = compute_metrics(res.trades, res.equity, cfg.initial_capital)

    print(f"\n== Backtest completo (EN muestra, optimista) — {strat.name} ==")
    _print_metrics(m)
    forced = int((res.trades["risk_pct"] > a.riesgo * 1.001).sum()) if len(res.trades) else 0
    if forced:
        print(f"  ⚠ {forced} operaciones con el lote mínimo arriesgando más de {a.riesgo} % "
              f"(tope {a.riesgo_tope} %): capital chico para estos stops")
    if res.skipped_small:
        print(f"  ⚠ {res.skipped_small} señales descartadas: ni el lote mínimo cabía en el tope de {a.riesgo_tope} %")
    if res.skipped_margin or res.reduced_margin:
        print(f"  ⚠ Apalancamiento 1:{a.apalancamiento:g}: {res.skipped_margin} señales sin margen y "
              f"{res.reduced_margin} operaciones achicadas para caber en el margen")
    if res.skipped_limits:
        print(f"  {res.skipped_limits} señales bloqueadas por el stop diario/semanal")
    if res.halted_at is not None:
        print(f"  ⛔ El bot se habría APAGADO el {res.halted_at} por llegar al drawdown máximo")

    if len(res.trades) and verbose:
        print("\n== Por banda del VIX proxy (volatilidad al entrar) ==")
        print(breakdown(res.trades, "vol_band").to_string())
        print("\n== Por régimen de mercado ==")
        print(breakdown(res.trades, "regime").to_string())
        print("\n== What-if ==")
        print(what_if(df, sig, cfg).to_string())

    out = {"simbolo": symbol, "metricas": m, "forzadas_lote_minimo": forced,
           "descartadas": res.skipped_small, "sin_margen": res.skipped_margin, "trades": res.trades.assign(symbol=symbol), "equity": res.equity}
    if a.walkforward:
        print("\n== Walk-forward (solo cuenta lo que pasa fuera de muestra) ==")
        wf = walk_forward(df, cfg, train=pd.DateOffset(months=a.wf_entreno_meses),
                          test=pd.DateOffset(months=a.wf_prueba_meses), min_trades=5 if a.muestra else 20)
        cols = [c for c in ("test_start", "params", "train_score", "train_score_pico", "oos_trades",
                            "oos_expectancy_r") if c in wf.windows]
        print(wf.windows[cols].to_string() if len(wf.windows) else "  Datos insuficientes para una ventana.")
        out["wf_windows"] = wf.windows.assign(symbol=symbol)
        out["oos"] = wf.oos_trades.assign(symbol=symbol) if len(wf.oos_trades) else wf.oos_trades
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Laboratorio de backtesting (Fase 1)")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--csv", nargs="+", help="uno o varios CSV de velas (ver fxbot/data/loaders.py)")
    src.add_argument("--muestra", action="store_true", help="EURUSD H1 de ejemplo (no sirve para validar)")
    ap.add_argument("--tz", default="UTC", help="zona horaria del CSV (los del script de MT5 ya vienen en UTC)")
    ap.add_argument("--simbolo", default=None, help="solo con un CSV cuyo nombre no indica el par")
    ap.add_argument("--tf", default="1h", help="temporalidad de trabajo: 1h, 4h, D")
    ap.add_argument("--capital", type=float, default=500.0)
    ap.add_argument("--riesgo", type=float, default=1.0, help="% del capital por operación")
    ap.add_argument("--riesgo-tope", type=float, default=1.5,
                    help="% máximo aceptado cuando solo cabe el lote mínimo (0 = descartar la señal)")
    ap.add_argument("--dd-max", type=float, default=20.0, help="% de caída que apaga el bot")
    ap.add_argument("--apalancamiento", type=float, default=30.0,
                    help="apalancamiento de la cuenta (1:N). Solo limita el margen; el riesgo lo fija el stop")
    ap.add_argument("--comision", type=float, default=7.0, help="USD por lote ida y vuelta")
    ap.add_argument("--walkforward", action="store_true", help="optimización walk-forward (tarda más)")
    ap.add_argument("--wf-entreno-meses", type=int, default=24)
    ap.add_argument("--wf-prueba-meses", type=int, default=6)
    ap.add_argument("--salida", default="resultados")
    a = ap.parse_args(argv)

    if a.muestra:
        datasets = [("EURUSD", load_sample_eurusd_h1())]
    else:
        if a.simbolo and len(a.csv) > 1:
            raise SystemExit("--simbolo solo se puede usar con un único CSV")
        datasets = [(a.simbolo.upper() if a.simbolo else symbol_from_path(f), load_ohlc_csv(f, tz=a.tz))
                    for f in a.csv]

    results = [run_symbol(sym, raw, a, verbose=True) for sym, raw in datasets]

    if a.walkforward:
        oos = pd.concat([r["oos"] for r in results if len(r.get("oos", []))], ignore_index=True) \
            if any(len(r.get("oos", [])) for r in results) else pd.DataFrame()
        label = f"walk-forward FUERA de muestra ({', '.join(r['simbolo'] for r in results)})"
    else:
        oos = pd.concat([r["trades"] for r in results], ignore_index=True)
        label = "backtest completo (EN muestra: optimista)"

    print(f"\n######## Monte Carlo sobre {label}")
    mc = None
    if len(oos) >= 2:
        # Riesgo efectivo: con capital chico el lote mínimo puede arriesgar más que --riesgo
        eff_risk = max(a.riesgo, float(np.nanmean(oos["risk_pct"]))) if "risk_pct" in oos else a.riesgo
        mc = monte_carlo(oos["r_multiple"], risk_pct=eff_risk, ruin_drawdown_pct=a.dd_max)
        print(f"  riesgo efectivo promedio por operación: {eff_risk:.2f} %")
        for k, v in mc.as_dict().items():
            print(f"  {k:<20} {v}")
        k = kelly_from_trades(oos["r_multiple"].to_numpy())
        print(f"  Kelly de la estrategia: {k * 100:.1f} % → tope sano (¼ Kelly): {k * 25:.2f} % por operación")
        if len(results) > 1:
            print("\n  Por par:")
            print(breakdown(oos, "symbol").to_string())
    else:
        print("  No hay suficientes operaciones.")

    pf = profit_factor_r(oos)
    if a.walkforward:
        ok, why = verdict(len(oos), pf, mc.prob_ruin_pct if mc else 100.0)
    else:
        ok, why = False, ["falta correr con --walkforward (sin validación fuera de muestra no hay veredicto)"]
    print("\n######## Veredicto Fase 1")
    print(f"  operaciones: {len(oos)}   profit factor (R): {pf}")
    print("  ✅ APROBADA: puede pasar a demo" if ok else "  ❌ NO APROBADA:\n    - " + "\n    - ".join(why))
    if a.muestra:
        print("  (Con los datos de muestra el veredicto no significa nada: son ~10 meses.)")

    out = Path(a.salida)
    out.mkdir(parents=True, exist_ok=True)
    pd.concat([r["trades"] for r in results], ignore_index=True).to_csv(out / "operaciones.csv", index=False)
    for r in results:
        r["equity"].to_csv(out / f"equity_{r['simbolo']}.csv")
    if a.walkforward:
        pd.concat([r["wf_windows"] for r in results], ignore_index=True).to_csv(
            out / "walkforward_ventanas.csv", index=False)
        oos.to_csv(out / "walkforward_operaciones.csv", index=False)
    summary = {
        "parametros": {k: v for k, v in vars(a).items() if k != "csv"},
        "archivos": a.csv,
        "por_simbolo": {r["simbolo"]: {"metricas": r["metricas"], "forzadas_lote_minimo": r["forzadas_lote_minimo"],
                                       "descartadas": r["descartadas"], "sin_margen": r["sin_margen"]}
                        for r in results},
        "fuera_de_muestra": {"operaciones": len(oos), "profit_factor_r": pf,
                             "expectancy_r": round(float(oos["r_multiple"].mean()), 3) if len(oos) else None},
        "montecarlo": mc.as_dict() if mc else None,
        "aprobada": ok, "motivos": why,
        "estrategia": {"nombre": TrendEmaAdx().name, **asdict(TrendEmaAdx())},
    }
    (out / "resumen.json").write_text(json.dumps(summary, indent=2, default=str, ensure_ascii=False))
    print(f"\nArchivos en {out}/  ← manda resumen.json para revisarlo")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
