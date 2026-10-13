"""El bot calcula los indicadores EXACTAMENTE igual que caracasportafolio.com.

La referencia (tests/fixtures/paridad_caracas.json) se generó ejecutando el código
original de Caracas-Portafolio con tools/paridad/generar_referencia.py.
Además, como la referencia usa solo las primeras L velas y aquí se calcula la serie
completa, cada comparación también prueba que el indicador no mira al futuro.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from fxbot.indicators import core as ind
from fxbot.regime.market_regime import market_regime
from fxbot.regime.vol_proxy import expanding_percentile, realized_vol

FIX = json.loads((Path(__file__).parent / "fixtures" / "paridad_caracas.json").read_text())
DF = pd.DataFrame(FIX["candles"]).set_index("time")
LENGTHS = FIX["lengths"]


@pytest.fixture(scope="module")
def series():
    c = DF["close"]
    adr = ind.adr_pct(DF)
    return {
        "obv": ind.obv(DF), "ad_line": ind.ad_line(DF), "chaikin": ind.chaikin(DF), "aroon": ind.aroon(DF),
        "adx": ind.adx(DF)["adx"], "atr_pct": ind.atr_pct(DF), "adr": adr["adr_pct"], "adr_used": adr["adr_used_pct"],
        "bbw": ind.bbw(c), "dmi": ind.adx(DF)[["plus_di", "minus_di"]], "stoch": ind.stoch_k(DF), "mfi": ind.mfi(DF),
        "regime": market_regime(DF, calibration="bvc"), "cvd": ind.cvd(DF), "pct252": ind.price_percentile(c),
        "value_z": ind.value_zone_z(c), "kelly": ind.kelly_half(c), "autocorr": ind.autocorr(c),
        "liquidity_z": ind.liquidity_z(DF), "momentum": ind.momentum(c), "rsi14": ind.rsi(c), "ema20": ind.ema(c, 20),
    }


def ref(L):
    return FIX["ts"][str(L)]


@pytest.mark.parametrize("L", LENGTHS)
def test_volumen(series, L):
    i = L - 1
    assert series["obv"].iat[i] == pytest.approx(ref(L)["obv"])
    assert series["ad_line"].iat[i] == pytest.approx(ref(L)["ad_line"], abs=1e-6)
    assert series["chaikin"].iat[i] == pytest.approx(ref(L)["chaikin"], abs=1e-6)
    assert round(series["cvd"]["cvd"].iat[i]) == pytest.approx(ref(L)["cvd"]["cumulative"], abs=1)
    assert round(series["cvd"]["cvd_delta"].iat[i]) == pytest.approx(ref(L)["cvd"]["lastDelta"], abs=1)
    if L >= 15:
        assert series["mfi"].iat[i] == pytest.approx(ref(L)["mfi"], abs=1e-9)
    if L >= 21:
        assert series["liquidity_z"].iat[i] == pytest.approx(ref(L)["liquidity_z"], abs=0.006)


@pytest.mark.parametrize("L", LENGTHS)
def test_tendencia(series, L):
    i, r = L - 1, ref(L)
    if L > 25:
        assert series["aroon"]["aroon_up"].iat[i] == pytest.approx(r["aroon"]["up"])
        assert series["aroon"]["aroon_down"].iat[i] == pytest.approx(r["aroon"]["down"])
    if L >= 28:
        assert series["adx"].iat[i] == pytest.approx(r["adx"], rel=1e-9)
    if L >= 15:
        assert series["rsi14"].iat[i] == pytest.approx(r["rsi14"], abs=0.006)
    if L >= 20:
        assert series["ema20"].iat[i] == pytest.approx(r["ema20"], abs=1e-8)
    if L >= 21:
        assert series["momentum"].iat[i] == pytest.approx(r["momentum"], abs=0.006)
    if L >= 15:   # DMI de Wilder: +DI / −DI
        assert series["dmi"]["plus_di"].iat[i] == pytest.approx(r["dmi"]["plus"], rel=1e-9, abs=1e-9)
        assert series["dmi"]["minus_di"].iat[i] == pytest.approx(r["dmi"]["minus"], rel=1e-9, abs=1e-9)
    assert series["regime"].iat[i] == r["regime"]
    if L >= 10:
        assert series["autocorr"].iat[i] == pytest.approx(r["autocorr"], abs=0.0006)
    assert series["kelly"].iat[i] == pytest.approx(r["kelly"], abs=1e-9)


@pytest.mark.parametrize("L", LENGTHS)
def test_volatilidad_y_posicion(series, L):
    i, r = L - 1, ref(L)
    if L >= 15:
        assert series["atr_pct"].iat[i] == pytest.approx(r["atr_pct"], rel=1e-9)
    if L >= 14:
        assert series["stoch"].iat[i] == pytest.approx(r["stoch"], abs=1e-9)
    assert round(series["adr"].iat[i], 3) == pytest.approx(r["adr"]["adr"], abs=1e-9)
    assert round(series["adr_used"].iat[i], 1) == pytest.approx(r["adr"]["usedPct"], abs=0.051)
    if L >= 20:
        assert round(series["bbw"].iat[i], 3) == pytest.approx(r["bbw"]["width"], abs=1e-9)
    if L >= 21:
        delta = series["bbw"].iat[i] - series["bbw"].iat[i - 1]
        trend = "neutral" if abs(delta) < 0.01 else ("contracting" if delta < 0 else "expanding")
        assert trend == r["bbw"]["trend"]
    if L >= 5:
        assert series["pct252"].iat[i] == r["pct252"]
    if L >= 20:
        z = series["value_z"].iat[i]
        assert round(z, 2) == pytest.approx(r["value_zone"]["score"], abs=1e-9)
        assert ind.value_zone_label(z) == r["value_zone"]["label"]


@pytest.mark.parametrize("L", [L for L in LENGTHS if L >= 5])
def test_volume_profile(L):
    vp = ind.volume_profile(DF.iloc[:L])
    assert vp["poc"] == pytest.approx(ref(L)["vp"]["poc"], abs=1e-8)
    assert vp["lvn"] == pytest.approx(ref(L)["vp"]["lvn"], abs=1e-8)


def test_regimen_en_todas_las_velas(series):
    expected = FIX["ts"]["regimes"]
    assert list(series["regime"]) == expected
    assert {"alcista", "bajista", "lateral", "volatil"} <= set(expected)  # el fixture cubre los 4 casos


def test_kelly_medio_igual_a_la_web():
    k = pd.DataFrame(FIX["kelly_candles"])["close"]
    ours = ind.kelly_half(k)
    expected = FIX["ts"]["kelly_mid"]
    for n, e in zip((100, 200, 300), expected):
        assert ours.iat[n - 1] == pytest.approx(e, abs=1e-9)
    assert any(0 < e < 1 for e in expected)   # al menos un caso fuera de los topes 0 / 100 %


def test_vix_proxy_igual_al_backend():
    closes = pd.Series(FIX["vol_closes"])
    rv = realized_vol(closes, 30)
    pct = expanding_percentile(rv, min_history=20)
    for L, expected in zip((40, 60, 120, 200, 320), FIX["vol_proxy"]):
        assert round(rv.iat[L - 1], 2) == pytest.approx(expected["vol"])
        if expected["percentile"] is None:
            assert np.isnan(pct.iat[L - 1])
        else:
            assert round(pct.iat[L - 1], 1) == pytest.approx(expected["percentile"])
