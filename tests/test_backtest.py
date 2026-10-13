"""Mecánica del motor: precios de entrada/salida, costos, stops, gaps y límites de riesgo."""
import numpy as np
import pandas as pd
import pytest

from fxbot.instruments import get_instrument
from fxbot.lab.backtest import BacktestConfig, run_backtest
from fxbot.lab.costs import CostModel, rollover_nights
from fxbot.risk.sizing import RiskLimits, kelly_from_trades, position_size

EURUSD = get_instrument("EURUSD")
NO_COSTS = CostModel(spread_pips=0.0, commission_per_lot_rt=0.0, slippage_pips=0.0,
                     swap_long_pips=0.0, swap_short_pips=0.0)


def bars(rows, start="2024-01-08 00:00"):
    """rows = [(open, high, low, close), ...] en velas H1 de lunes."""
    idx = pd.date_range(start, periods=len(rows), freq="h", tz="UTC")
    df = pd.DataFrame(rows, columns=["open", "high", "low", "close"], index=idx)
    df["volume"] = 100.0
    return df


def signal_at(df, i, side, sl, tp, mult=1.0):
    s = pd.DataFrame({"signal": 0, "sl_dist": 0.0, "tp_dist": 0.0, "size_mult": 1.0}, index=df.index)
    s.iloc[i, s.columns.get_loc("signal")] = side
    s.iloc[i, s.columns.get_loc("sl_dist")] = sl
    s.iloc[i, s.columns.get_loc("tp_dist")] = tp
    s.iloc[i, s.columns.get_loc("size_mult")] = mult
    return s


def cfg(costs=NO_COSTS, capital=10_000.0, leverage=30.0, **lim):
    return BacktestConfig("EURUSD", capital, costs, RiskLimits(**lim), leverage=leverage)


def test_compra_que_llega_al_objetivo_gana_exactamente_lo_esperado():
    df = bars([(1.1000, 1.1005, 1.0995, 1.1000), (1.1000, 1.1010, 1.0995, 1.1008), (1.1008, 1.1030, 1.1000, 1.1025)])
    r = run_backtest(df, signal_at(df, 0, 1, 0.0010, 0.0020), cfg())
    t = r.trades.iloc[0]
    # riesgo 1 % de 10.000 = 100 USD; stop 10 pips → 1 lote (10 USD/pip)
    assert t.lots == pytest.approx(1.0)
    assert t.entry == pytest.approx(1.1000) and t.exit == pytest.approx(1.1020)
    assert t.pnl_usd == pytest.approx(200.0) and t.r_multiple == pytest.approx(2.0)
    assert t.exit_reason == "objetivo"


def test_si_la_vela_toca_stop_y_objetivo_se_asume_stop():
    df = bars([(1.1, 1.1, 1.1, 1.1), (1.1000, 1.1030, 1.0980, 1.1000)])
    t = run_backtest(df, signal_at(df, 0, 1, 0.0010, 0.0020), cfg()).trades.iloc[0]
    assert t.exit_reason == "stop" and t.pnl_usd == pytest.approx(-100.0)


def test_gap_por_debajo_del_stop_sale_a_la_apertura_peor():
    df = bars([(1.1, 1.1, 1.1, 1.1), (1.1000, 1.1002, 1.0998, 1.1000), (1.0970, 1.0975, 1.0960, 1.0965)])
    t = run_backtest(df, signal_at(df, 0, 1, 0.0010, 0.0020), cfg()).trades.iloc[0]
    assert t.exit_reason == "stop (gap)" and t.exit == pytest.approx(1.0970)
    assert t.r_multiple == pytest.approx(-3.0)   # el gap hace perder 3R: por eso existe el Monte Carlo


def test_venta_paga_spread_al_salir_y_comision():
    costs = NO_COSTS.scaled(spread_pips=1.0, commission_per_lot_rt=7.0)
    df = bars([(1.1, 1.1, 1.1, 1.1), (1.1000, 1.1002, 1.0990, 1.0995), (1.0995, 1.0996, 1.0975, 1.0980)])
    t = run_backtest(df, signal_at(df, 0, -1, 0.0010, 0.0020), cfg(costs)).trades.iloc[0]
    # entra vendiendo al bid 1.1000; el objetivo 1.0980 se alcanza cuando el ASK (bid+1 pip) llega ahí
    assert t.entry == pytest.approx(1.1000) and t.exit == pytest.approx(1.0980)
    assert t.commission_usd == pytest.approx(7.0 * t.lots)
    assert t.pnl_usd == pytest.approx(20 * 10 * t.lots - 7.0 * t.lots)


def test_el_tamano_incluye_costos_y_respeta_el_riesgo():
    costs = CostModel(spread_pips=0.5, commission_per_lot_rt=7.0, slippage_pips=0.2)
    df = bars([(1.1, 1.1, 1.1, 1.1), (1.1000, 1.1002, 1.0985, 1.0990)])
    t = run_backtest(df, signal_at(df, 0, 1, 0.0010, 0.0020), cfg(costs)).trades.iloc[0]
    assert t.exit_reason == "stop"
    assert -t.pnl_usd <= 100.0 + 1e-6        # nunca pierde más del 1 % planeado
    assert t.risk_usd <= 100.0 + 1e-6


def test_capital_chico_descarta_la_senal_si_el_lote_minimo_pasa_el_tope():
    df = bars([(1.1, 1.1, 1.1, 1.1), (1.1, 1.1, 1.1, 1.1)])
    # stop de 200 pips: 0.01 lotes arriesgan $20 = 4 % de $500 (> tope 1.5 %)
    r = run_backtest(df, signal_at(df, 0, 1, 0.0200, 0.0300), cfg(capital=500.0))
    assert r.trades.empty and r.skipped_small == 1


def test_capital_chico_usa_el_lote_minimo_si_cabe_en_el_tope():
    df = bars([(1.1, 1.1, 1.1, 1.1), (1.1000, 1.1002, 1.0930, 1.0940)])
    # stop de 60 pips: 0.01 lotes arriesgan $6 = 1.2 % de $500 (> 1 % pero ≤ tope 1.5 %)
    r = run_backtest(df, signal_at(df, 0, 1, 0.0060, 0.0090), cfg(capital=500.0))
    t = r.trades.iloc[0]
    assert t.lots == pytest.approx(0.01) and t.risk_pct == pytest.approx(1.2)
    assert t.pnl_usd == pytest.approx(-6.0)
    sin_tope = run_backtest(df, signal_at(df, 0, 1, 0.0060, 0.0090), cfg(capital=500.0, min_lot_max_risk_pct=0.0))
    assert sin_tope.trades.empty and sin_tope.skipped_small == 1


def test_tension_reduce_el_riesgo_25_por_ciento():
    df = bars([(1.1, 1.1, 1.1, 1.1), (1.1000, 1.1002, 1.0985, 1.0990)])
    t = run_backtest(df, signal_at(df, 0, 1, 0.0010, 0.0020, mult=0.75), cfg()).trades.iloc[0]
    assert t.lots == pytest.approx(0.75)


def test_drawdown_maximo_apaga_el_bot():
    rows = [(1.1, 1.1, 1.1, 1.1)]
    for _ in range(30):  # cada operación pierde 10 %
        rows += [(1.1000, 1.1001, 1.0980, 1.0985), (1.1, 1.1, 1.1, 1.1)]
    df = bars(rows)
    s = pd.DataFrame({"signal": 1, "sl_dist": 0.0010, "tp_dist": 0.0050, "size_mult": 1.0}, index=df.index)
    # 10 % de riesgo con stop de 10 pips = 10 lotes: hace falta apalancamiento alto para el margen
    r = run_backtest(df, s, cfg(leverage=500, risk_pct=10.0, max_drawdown_pct=25.0, daily_loss_pct=100,
                                weekly_loss_pct=100))
    assert r.halted_at is not None
    assert len(r.trades) == 3                # 10 % + 10 % + 10 % ≥ 25 % → apagado, no hay 4.ª
    assert r.equity.iloc[-1] == pytest.approx(10_000 * 0.9 ** 3)


def test_stop_diario_bloquea_nuevas_entradas():
    rows = [(1.1, 1.1, 1.1, 1.1)] + [(1.1000, 1.1001, 1.0980, 1.0985), (1.1, 1.1, 1.1, 1.1)] * 3
    df = bars(rows)
    s = pd.DataFrame({"signal": 1, "sl_dist": 0.0010, "tp_dist": 0.0050, "size_mult": 1.0}, index=df.index)
    # dos pérdidas de 1 % compuestas = −1.99 %: con límite diario de 1.5 % la tercera no entra
    r = run_backtest(df, s, cfg(risk_pct=1.0, daily_loss_pct=1.5))
    assert len(r.trades) == 2 and r.skipped_limits > 0


def test_noches_de_swap_y_miercoles_triple():
    utc = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731
    # 17:00 NY = 21:00 UTC en verano (EDT)
    assert rollover_nights(utc("2024-07-01 20:00"), utc("2024-07-01 22:00")) == 1   # lunes
    assert rollover_nights(utc("2024-07-03 20:00"), utc("2024-07-03 22:00")) == 3   # miércoles
    assert rollover_nights(utc("2024-07-01 10:00"), utc("2024-07-08 10:00")) == 7   # semana: 1+1+3+1+1
    assert rollover_nights(utc("2024-07-01 10:00"), utc("2024-07-01 15:00")) == 0


def test_position_size_y_kelly():
    assert position_size(10_000, 1.0, 0.0010, 1.1, EURUSD) == pytest.approx(1.0)
    usdjpy = get_instrument("USDJPY")
    # 1 pip de USDJPY a 150 = 1000 JPY = 6.67 USD por lote
    assert usdjpy.pip_value_per_lot(150.0) == pytest.approx(1000 / 150)
    assert position_size(500, 1.0, 0.0060, 1.1, EURUSD) == 0.0
    assert kelly_from_trades(np.array([2.0, -1.0] * 10)) == pytest.approx(0.25)
    assert kelly_from_trades(np.array([1.0, 1.0])) == 0.0


def test_apalancamiento_bajo_limita_el_tamano_por_margen():
    df = bars([(1.1, 1.1, 1.1, 1.1), (1.1000, 1.1030, 1.0995, 1.1025)])
    sig = signal_at(df, 0, 1, 0.0010, 0.0020)       # stop de 10 pips: el riesgo pide 0.05 lotes con $500
    holgado = run_backtest(df, sig, BacktestConfig("EURUSD", 500.0, NO_COSTS, RiskLimits(), leverage=30))
    assert holgado.trades.iloc[0].lots == pytest.approx(0.05)
    # 1:5 → 1 lote de EURUSD a 1.10 retiene 22.000 USD de margen; con $500 caben 0.02 lotes
    apretado = run_backtest(df, sig, BacktestConfig("EURUSD", 500.0, NO_COSTS, RiskLimits(), leverage=5))
    assert apretado.trades.iloc[0].lots == pytest.approx(0.02) and apretado.reduced_margin == 1
    # 1:1 → ni 0.01 lotes (1.100 USD de margen) caben en $500
    sin = run_backtest(df, sig, BacktestConfig("EURUSD", 500.0, NO_COSTS, RiskLimits(), leverage=1))
    assert sin.trades.empty and sin.skipped_margin == 1 and sin.skipped_small == 0
