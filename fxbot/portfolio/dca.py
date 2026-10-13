"""Calculadora de compra mensual (DCA) para el núcleo de ETF.

Cada mes aportas una cantidad fija. La calculadora decide cuánto comprar de cada ETF para
acercarte a tus porcentajes objetivo SIN VENDER nada (vender genera costos y, en algunos
países, impuestos). Lo que está por debajo de su objetivo recibe más.

Uso:
    python -m fxbot.portfolio.dca --aporte 50 \\
        --objetivo SPYB=70 SMH=30 \\
        --tenencias SPYB=0.10 SMH=0 \\
        --precios SPYB=777.76 SMH=310.50

Los precios y tenencias los copias de la app (Binance, Quantfury...). La calculadora no se
conecta a ninguna cuenta ni compra nada.
"""
from __future__ import annotations

import argparse


def plan_dca(contribution: float, targets: dict[str, float], holdings: dict[str, float],
             prices: dict[str, float], min_order: float = 5.0) -> dict[str, float]:
    """USD a comprar de cada activo este mes.

    targets: pesos objetivo (se normalizan, pueden venir en % o en fracción).
    holdings: unidades que ya tienes. prices: precio actual por unidad.
    min_order: compras más chicas que esto se juntan en el activo más atrasado
        (órdenes diminutas pagan más en comisión mínima y spread).
    """
    if contribution <= 0:
        raise ValueError("El aporte debe ser mayor que 0")
    total_w = sum(targets.values())
    if total_w <= 0:
        raise ValueError("Los pesos objetivo deben sumar más que 0")
    weights = {k: v / total_w for k, v in targets.items()}
    missing = [k for k in weights if k not in prices or prices[k] <= 0]
    if missing:
        raise ValueError(f"Falta el precio de: {', '.join(missing)}")

    values = {k: holdings.get(k, 0.0) * prices[k] for k in weights}
    total_after = sum(values.values()) + contribution
    deficits = {k: max(0.0, weights[k] * total_after - values[k]) for k in weights}
    gap = sum(deficits.values())
    # Si el aporte no alcanza para cerrar todos los déficits, se reparte en proporción a ellos.
    # Si sobra (no pasa cuando solo se compra), lo que sobra va según los pesos.
    if gap >= contribution:
        buys = {k: contribution * d / gap for k, d in deficits.items()}
    else:
        rest = contribution - gap
        buys = {k: deficits[k] + rest * weights[k] for k in weights}

    small = [k for k, v in buys.items() if 0 < v < min_order]
    if small and len(small) < len(buys):
        leftover = sum(buys[k] for k in small)
        for k in small:
            buys[k] = 0.0
        laggard = max((k for k in buys if k not in small), key=lambda k: deficits[k])
        buys[laggard] += leftover
    return {k: round(v, 2) for k, v in buys.items()}


def _pairs(items: list[str], name: str) -> dict[str, float]:
    out = {}
    for it in items or []:
        if "=" not in it:
            raise SystemExit(f"{name}: usa el formato ACTIVO=valor (recibí '{it}')")
        k, v = it.split("=", 1)
        out[k.strip().upper()] = float(v.replace(",", "."))
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Compra mensual (DCA) hacia tus pesos objetivo, sin vender")
    ap.add_argument("--aporte", type=float, required=True, help="USD que vas a invertir este mes")
    ap.add_argument("--objetivo", nargs="+", required=True, help="pesos objetivo, p. ej. SPYB=70 SMH=30")
    ap.add_argument("--precios", nargs="+", required=True, help="precio actual, p. ej. SPYB=777.76")
    ap.add_argument("--tenencias", nargs="*", default=[], help="unidades que ya tienes, p. ej. SPYB=0.1")
    ap.add_argument("--orden-minima", type=float, default=5.0, help="USD mínimos por compra")
    a = ap.parse_args(argv)

    targets, prices, holdings = _pairs(a.objetivo, "--objetivo"), _pairs(a.precios, "--precios"), \
        _pairs(a.tenencias, "--tenencias")
    buys = plan_dca(a.aporte, targets, holdings, prices, a.orden_minima)
    total_w = sum(targets.values())
    now = {k: holdings.get(k, 0.0) * prices[k] for k in targets}
    after = {k: now[k] + buys[k] for k in targets}
    tot_now, tot_after = sum(now.values()), sum(after.values())
    print(f"{'Activo':<8}{'Objetivo':>10}{'Hoy':>10}{'Comprar':>11}{'Unidades':>12}{'Después':>10}")
    for k in targets:
        pct_now = now[k] / tot_now * 100 if tot_now else 0.0
        print(f"{k:<8}{targets[k] / total_w * 100:>9.1f}%{pct_now:>9.1f}%{buys[k]:>10.2f}$"
              f"{buys[k] / prices[k]:>12.6f}{after[k] / tot_after * 100:>9.1f}%")
    print(f"\nTotal a invertir: {sum(buys.values()):.2f} USD. Compra a mercado en horario de la bolsa de EE. UU. "
          f"(9:30–16:00 NY), cuando el precio del token está más pegado al real.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
