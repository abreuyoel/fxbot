"""Descarga velas históricas desde tu terminal MetaTrader 5 (cuenta DEMO sirve) a CSV.

Requisitos (solo Windows):
    1. MetaTrader 5 instalado y con sesión iniciada en tu broker (p. ej. FP Markets demo).
    2. En MT5: Herramientas → Opciones → Gráficos → "Máx. barras en el gráfico" = Unlimited.
    3. pip install MetaTrader5 pandas

Uso:
    python scripts/descargar_datos_mt5.py --simbolos EURUSD GBPUSD USDJPY --desde 2012-01-01
    python scripts/descargar_datos_mt5.py --simbolos EURUSD --sufijo .r      (si tu broker usa EURUSD.r)

Hora del servidor: MetaTrader guarda las velas en la hora del servidor del broker, no en UTC.
Casi todos los brokers de forex usan "Nueva York + 7 h" (UTC+2 en invierno, UTC+3 en verano),
así el día cierra a las 17:00 de NY. Es el valor por defecto (--servidor ny+7). Si tu broker
usa otra hora fija, pásala, p. ej. --servidor utc+2.

Salida: datos/<SIMBOLO>_H1.csv con columnas time (UTC, epoch s), open, high, low, close,
tick_volume, spread_pips. Es el formato que lee fxbot.data.loaders.load_ohlc_csv.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

TIMEFRAMES = {"M15": "TIMEFRAME_M15", "H1": "TIMEFRAME_H1", "H4": "TIMEFRAME_H4", "D1": "TIMEFRAME_D1"}


def server_to_utc(epoch_server: pd.Series, servidor: str) -> pd.DatetimeIndex:
    naive = pd.to_datetime(epoch_server, unit="s")
    if servidor == "ny+7":
        ny = pd.DatetimeIndex(naive - pd.Timedelta(hours=7))
        return ny.tz_localize("America/New_York", ambiguous="NaT", nonexistent="shift_forward").tz_convert("UTC")
    if servidor.startswith("utc"):
        hours = int(servidor[3:] or 0)
        return pd.DatetimeIndex(naive - pd.Timedelta(hours=hours)).tz_localize("UTC")
    raise SystemExit(f"--servidor no reconocido: {servidor} (usa ny+7 o utc+N)")


def find_symbol(mt5, base: str, sufijo: str | None) -> str | None:
    """Nombre del símbolo en tu broker. FP Markets y otros a veces usan EURUSD.r, EURUSD-ECN, etc."""
    if sufijo is not None:
        return base + sufijo if mt5.symbol_info(base + sufijo) else None
    if mt5.symbol_info(base):
        return base
    candidates = [x.name for x in (mt5.symbols_get(f"{base}*") or [])
                  if x.name.upper().startswith(base) and len(x.name) <= len(base) + 6]
    return min(candidates, key=len) if candidates else None


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--simbolos", nargs="+", default=["EURUSD", "GBPUSD", "USDJPY"])
    ap.add_argument("--sufijo", default=None, help="sufijo de los símbolos (.r, -ECN...); por defecto se detecta solo")
    ap.add_argument("--tf", default="H1", choices=sorted(TIMEFRAMES))
    ap.add_argument("--desde", default="2012-01-01")
    ap.add_argument("--hasta", default=None, help="por defecto: ahora")
    ap.add_argument("--servidor", default="ny+7", help="hora del servidor del broker: ny+7 o utc+N")
    ap.add_argument("--salida", default="datos")
    a = ap.parse_args()

    import MetaTrader5 as mt5  # solo existe en Windows

    if not mt5.initialize():
        raise SystemExit(f"No pude conectar con MetaTrader 5: {mt5.last_error()}. ¿Está abierto y con sesión iniciada?")
    acc = mt5.account_info()
    if acc is not None:
        kind = "DEMO" if acc.trade_mode == mt5.ACCOUNT_TRADE_MODE_DEMO else "REAL"
        print(f"Conectado a {acc.server} (cuenta {kind}). Este script solo LEE precios: no abre operaciones.")
    out = Path(a.salida)
    out.mkdir(parents=True, exist_ok=True)
    start = datetime.fromisoformat(a.desde).replace(tzinfo=timezone.utc)
    end = datetime.fromisoformat(a.hasta).replace(tzinfo=timezone.utc) if a.hasta else datetime.now(timezone.utc)
    tf = getattr(mt5, TIMEFRAMES[a.tf])
    try:
        for base in a.simbolos:
            base = base.upper()
            sym = find_symbol(mt5, base, a.sufijo)
            if sym is None or not mt5.symbol_select(sym, True):
                print(f"✗ {base}: no lo encuentro en tu broker. Mira el nombre exacto en 'Observación del mercado'"
                      f" y pásalo con --sufijo")
                continue
            info = mt5.symbol_info(sym)
            pip = info.point * (10 if info.digits in (3, 5) else 1)
            rates = mt5.copy_rates_range(sym, tf, start, end)
            if rates is None or len(rates) == 0:
                print(f"✗ {sym}: sin datos ({mt5.last_error()}). Revisa 'Máx. barras en el gráfico'.")
                continue
            df = pd.DataFrame(rates)
            utc = server_to_utc(df["time"], a.servidor)
            keep = utc.notna()   # la hora repetida del cambio de horario de otoño se descarta
            df, utc = df[keep].copy(), utc[keep]
            df["time"] = (utc - pd.Timestamp("1970-01-01", tz="UTC")) // pd.Timedelta(seconds=1)
            df["spread_pips"] = df["spread"] * info.point / pip
            df = df[["time", "open", "high", "low", "close", "tick_volume", "spread_pips"]]
            path = out / f"{base}_{a.tf}.csv"
            df.to_csv(path, index=False)
            first, last = utc.min(), utc.max()
            print(f"✓ {sym}: {len(df)} velas {first:%Y-%m-%d} → {last:%Y-%m-%d}, "
                  f"spread mediano {df['spread_pips'].median():.2f} pips → {path}")
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    main()
