import pytest

from fxbot.portfolio.dca import main, plan_dca

PRICES = {"SPYB": 800.0, "SMH": 300.0}


def test_primer_mes_reparte_segun_pesos():
    buys = plan_dca(100, {"SPYB": 70, "SMH": 30}, {}, PRICES)
    assert buys == {"SPYB": 70.0, "SMH": 30.0}


def test_compra_mas_lo_que_quedo_atrasado_sin_vender():
    # SMH subió mucho: ya pesa más que su 30 %, así que todo el aporte va a SPYB
    holdings = {"SPYB": 0.25, "SMH": 0.5}          # 200 USD y 150 USD → SMH 43 %
    buys = plan_dca(50, {"SPYB": 70, "SMH": 30}, holdings, PRICES)
    assert buys["SMH"] == 0.0 and buys["SPYB"] == pytest.approx(50.0)
    assert all(v >= 0 for v in buys.values())


def test_suma_siempre_el_aporte_y_junta_ordenes_chicas():
    holdings = {"SPYB": 0.2, "SMH": 0.18}          # SMH apenas por debajo de su objetivo
    buys = plan_dca(50, {"SPYB": 70, "SMH": 30}, holdings, PRICES, min_order=5)
    assert sum(buys.values()) == pytest.approx(50.0)
    assert all(v == 0 or v >= 5 for v in buys.values())


def test_errores_claros():
    with pytest.raises(ValueError, match="precio"):
        plan_dca(50, {"SPYB": 70, "VGT": 30}, {}, {"SPYB": 800.0})
    with pytest.raises(ValueError):
        plan_dca(0, {"SPYB": 1}, {}, PRICES)


def test_cli(capsys):
    assert main(["--aporte", "50", "--objetivo", "SPYB=70", "SMH=30", "--precios", "SPYB=777,76", "SMH=310.5"]) == 0
    out = capsys.readouterr().out
    assert "SPYB" in out and "Total a invertir: 50.00" in out
