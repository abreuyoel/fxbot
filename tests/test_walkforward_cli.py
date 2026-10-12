import json

import numpy as np
import pandas as pd
import pytest

from fxbot.lab.backtest import BacktestConfig
from fxbot.lab.walkforward import walk_forward


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
