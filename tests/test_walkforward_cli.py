import json

import numpy as np
import pandas as pd
import pytest

from fxbot.lab.backtest import BacktestConfig
from fxbot.lab.walkforward import robust_scores, walk_forward


def synthetic_h4(years=4, seed=5):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2019-01-01", periods=int(years * 365 * 6), freq="4h", tz="UTC")
    idx = idx[idx.dayofweek < 5]
    trend = np.sin(np.arange(len(idx)) / 400) * 0.0006
    close = 1.15 * np.exp(np.cumsum(trend + rng.normal(0, 0.0025, len(idx))))
    open_ = np.r_[close[0], close[:-1]]
    high = np.maximum(open_, close) * (1 + np.abs(rng.normal(0, 0.001, len(idx))))
    low = np.minimum(open_, close) * (1 - np.abs(rng.normal(0, 0.001, len(idx))))
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close,
                         "volume": rng.integers(100, 1000, len(idx)).astype(float)}, index=idx)


def test_walk_forward_solo_cuenta_operaciones_fuera_de_muestra():
    df = synthetic_h4()
    grid = {"fast": [10, 20], "slow": [50], "adx_min": [15.0], "atr_mult": [2.0], "rr": [1.5]}
    wf = walk_forward(df, BacktestConfig(initial_capital=10_000), grid=grid,
                      train=pd.DateOffset(years=1), test=pd.DateOffset(months=6), min_trades=5)
    assert len(wf.windows) >= 4
    assert not wf.oos_trades.empty
    for _, w in wf.windows.iterrows():
        t = wf.oos_trades[wf.oos_trades["window"] == w.test_start]
        assert (t["entry_time"] >= w.test_start).all() and (t["entry_time"] < w.test_end).all()


def test_cli_con_datos_de_muestra(tmp_path, capsys):
    pytest.importorskip("backtesting")
    from fxbot.lab.run import main

    assert main(["--muestra", "--salida", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "Veredicto Fase 1" in out and "NO APROBADA" in out
    summary = json.loads((tmp_path / "resumen.json").read_text())
    assert summary["aprobada"] is False
    assert (tmp_path / "operaciones.csv").exists()


def test_meseta_castiga_un_pico_aislado():
    grid = {"a": [1, 2, 3, 4, 5, 6, 7, 8]}
    combos = [{"a": v} for v in grid["a"]]
    #              pico aislado ↓        meseta ↓
    scores = [0.0, 0.0, 6.0, 0.0, 0.0, 2.0, 2.0, 2.0]
    robust = robust_scores(scores, combos, grid)
    assert int(np.argmax(scores)) == 2          # el pico gana en crudo...
    assert int(np.argmax(robust)) in (5, 6, 7)  # ...pero la meseta gana en robusto
    assert robust[2] == 0.0


def test_cli_varios_pares_junta_resultados(tmp_path, capsys):
    from fxbot.lab.run import main

    paths = []
    for i, sym in enumerate(("EURUSD", "GBPUSD")):
        df = synthetic_h4(years=3, seed=10 + i)
        f = tmp_path / f"{sym}_H4.csv"
        df.assign(time=(df.index - pd.Timestamp("1970-01-01", tz="UTC")) // pd.Timedelta(seconds=1)) \
          .rename(columns={"volume": "tick_volume"}).to_csv(f, index=False)
        paths.append(str(f))
    out = tmp_path / "res"
    assert main(["--csv", *paths, "--tf", "4h", "--capital", "10000", "--walkforward",
                 "--wf-entreno-meses", "12", "--wf-prueba-meses", "6", "--salida", str(out)]) == 0
    summary = json.loads((out / "resumen.json").read_text())
    assert set(summary["por_simbolo"]) == {"EURUSD", "GBPUSD"}
    oos = pd.read_csv(out / "walkforward_operaciones.csv")
    assert set(oos["symbol"]) <= {"EURUSD", "GBPUSD"}
    assert summary["fuera_de_muestra"]["operaciones"] == len(oos)


@pytest.mark.parametrize("module", ["fxbot.lab.run", "fxbot.portfolio.dca"])
def test_la_ayuda_de_la_linea_de_comandos_no_falla(module, capsys):
    # Python 3.14 valida los textos de ayuda al crear las opciones: un "%" sin escapar rompe el arranque
    import importlib

    with pytest.raises(SystemExit) as e:
        importlib.import_module(module).main(["--help"])
    assert e.value.code == 0
    assert "usage" in capsys.readouterr().out
