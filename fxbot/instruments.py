"""Especificación de instrumentos: tamaño de pip, contrato y lotaje.

La cuenta se asume en USD. El valor del pip depende de la divisa de cotización:
- XXX/USD (EURUSD, GBPUSD, XAUUSD): el pip ya está en USD.
- USD/XXX (USDJPY): el pip está en la otra divisa y se convierte dividiendo por el precio.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Instrument:
    symbol: str
    pip_size: float              # 0.0001 en EURUSD, 0.01 en USDJPY
    contract_size: float = 100_000
    min_lot: float = 0.01
    lot_step: float = 0.01
    usd_is_base: bool = False    # True en USDJPY, USDCHF, USDCAD
    # Spread típico en pips para una cuenta "raw/ECN" fuera de noticias. Es solo un valor por
    # defecto: si el CSV trae la columna spread_pips se usa la real de cada vela.
    typical_spread_pips: float = 0.2

    def pip_value_per_lot(self, price: float) -> float:
        """Valor en USD de 1 pip para 1 lote estándar."""
        value = self.contract_size * self.pip_size
        if self.usd_is_base:
            value /= price
        return value

    def margin_per_lot(self, price: float, leverage: float) -> float:
        """Margen en USD que el broker retiene por 1 lote: valor nominal ÷ apalancamiento."""
        notional = self.contract_size if self.usd_is_base else self.contract_size * price
        return notional / leverage

    def round_lots(self, lots: float) -> float:
        """Redondea HACIA ABAJO al paso del broker (nunca arriesgar más de lo calculado)."""
        steps = int(lots / self.lot_step + 1e-9)
        return round(steps * self.lot_step, 8)


INSTRUMENTS: dict[str, Instrument] = {
    "EURUSD": Instrument("EURUSD", 0.0001, typical_spread_pips=0.2),
    "GBPUSD": Instrument("GBPUSD", 0.0001, typical_spread_pips=0.5),
    "AUDUSD": Instrument("AUDUSD", 0.0001, typical_spread_pips=0.3),
    "USDJPY": Instrument("USDJPY", 0.01, usd_is_base=True, typical_spread_pips=0.3),
    "USDCHF": Instrument("USDCHF", 0.0001, usd_is_base=True, typical_spread_pips=0.4),
    "USDCAD": Instrument("USDCAD", 0.0001, usd_is_base=True, typical_spread_pips=0.5),
    # Oro: 1 lote = 100 onzas; "pip" = 0.10 USD → 10 USD por pip y lote.
    "XAUUSD": Instrument("XAUUSD", 0.1, contract_size=100, typical_spread_pips=1.5),
}


def get_instrument(symbol: str) -> Instrument:
    try:
        return INSTRUMENTS[symbol.upper()]
    except KeyError:
        raise KeyError(f"Instrumento desconocido: {symbol}. Agrégalo en fxbot/instruments.py") from None
