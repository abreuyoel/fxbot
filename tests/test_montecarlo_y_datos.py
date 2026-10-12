import numpy as np
import pandas as pd
import pytest

from fxbot.data.loaders import daily_bars, load_ohlc_csv, resample_ohlc, validate_ohlc
from fxbot.lab.metrics import compute_metrics, max_drawdown_pct
from fxbot.lab.montecarlo import monte_carlo
from fxbot.regime.vol_proxy import align_daily_to_bars, band_for


def test_monte_carlo_reproducible_y_coherente():
    r = np.array([1.5, -1, -1, 2, -1, 1.5, -1, 0.5] * 20)
    a, b = monte_carlo(r, seed=1), monte_carlo(r, seed=1)
    assert a.as_dict() == b.as_dict()
    assert a.drawdown_p50 <= a.drawdown_p95 <= a.drawdown_p99
    assert a.final_return_p5 <= a.final_return_p50 <= a.final_return_p95


def test_monte_carlo_casos_extremos():
    assert monte_carlo(np.array([1.0, 0.5]), seed=0).prob_ruin_pct == 0.0
    ruin = monte_carlo(np.array([-1.0, -1.0, 0.1]), risk_pct=5, ruin_drawdown_pct=20, trades_per_sim=50, seed=0)
    assert ruin.prob_ruin_pct > 90


def test_permutacion_conserva_el_resultado_final():
    r = np.array([1.0, -1.0, 2.0, -0.5])
    mc = monte_carlo(r, method="permutation", simulations=200)
    assert mc.final_return_p5 == pytest.approx(mc.final_return_p95)  # mismo producto en cualquier orden


def test_carga_exportacion_manual_de_mt5(tmp_path):
    f = tmp_path / "EURUSD_H1.csv"
    f.write_text("<DATE>\t<TIME>\t<OPEN>\t<HIGH>\t<LOW>\t<CLOSE>\t<TICKVOL>\t<VOL>\t<SPREAD>\n"
                 "2024.01.02\t10:00:00\t1.1000\t1.1010\t1.0990\t1.1005\t1200\t0\t3\n"
                 "2024.01.02\t11:00:00\t1.1005\t1.1015\t1.1000\t1.1010\t900\t0\t2\n")
    df = load_ohlc_csv(f, tz="Etc/GMT-2", point_to_pip=0.1)   # servidor del broker en UTC+2
    assert str(df.index[0]) == "2024-01-02 08:00:00+00:00"
    assert df["spread_pips"].tolist() == pytest.approx([0.3, 0.2])
    assert validate_ohlc(df).ok


def test_carga_csv_del_script_mt5_y_detecta_problemas(tmp_path):
    f = tmp_path / "x.csv"
    f.write_text("time,open,high,low,close,tick_volume,spread_pips\n"
                 "1704189600,1.1,1.101,1.099,1.1005,10,0.2\n"
                 "1704193200,1.1,1.0990,1.099,1.1005,10,0.2\n")  # high < close
    df = load_ohlc_csv(f)
    rep = validate_ohlc(df)
    assert not rep.ok and "incoherente" in rep.problems[0]


def test_velas_diarias_cierran_a_las_17_de_nueva_york():
    idx = pd.date_range("2024-01-07 22:00", "2024-01-09 21:00", freq="h", tz="UTC")  # domingo 22:00 → martes
    df = pd.DataFrame({"open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1.0}, index=idx)
    d = daily_bars(df)
    assert [str(x.date()) for x in d.index] == ["2024-01-08", "2024-01-09"]   # el domingo se suma al lunes
    assert d["volume"].tolist() == [24.0, 24.0]
    # H4 alineado a UTC: las 2 horas del domingo forman su propia vela (20:00-24:00)
    assert len(resample_ohlc(df, "4h")) == 13


def test_valor_diario_solo_se_ve_al_dia_siguiente():
    daily = pd.DataFrame({"x": [1.0, 2.0]}, index=pd.DatetimeIndex(["2024-01-08", "2024-01-09"], tz="UTC"))
    bars = pd.date_range("2024-01-08", periods=48, freq="h", tz="UTC")
    al = align_daily_to_bars(daily, bars)
    assert al["x"].iloc[:24].isna().all()          # el lunes todavía no se conoce el valor del lunes
    assert (al["x"].iloc[24:] == 1.0).all()


def test_bandas_vix_proxy_y_metricas():
    assert [band_for(p) for p in (10, 50, 80, 95)] == ["letargo", "optimo", "tension", "panico"]
    eq = pd.Series([100, 120, 90, 130], index=pd.date_range("2024-01-01", periods=4, freq="D", tz="UTC"))
    assert max_drawdown_pct(eq) == pytest.approx(25.0)
    m = compute_metrics(pd.DataFrame(), eq, 100)
    assert m["retorno_total_pct"] == pytest.approx(30.0)
