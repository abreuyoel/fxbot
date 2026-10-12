"""Carga y validación de velas OHLC.

Formato interno (lo que espera todo el resto del bot):
    índice  DatetimeIndex en UTC, ordenado, sin duplicados (apertura de la vela)
    open, high, low, close   precios BID (como los entrega MetaTrader)
    volume                   tick volume (en forex spot no existe volumen real)
    spread_pips              opcional: spread de la vela en pips

Formatos de entrada soportados:
    - CSV de scripts/descargar_datos_mt5.py (time, open, high, low, close, tick_volume, spread_pips)
    - Exportación manual de MetaTrader 5 (<DATE> <TIME> <OPEN> ... <TICKVOL> <VOL> <SPREAD>, separado por tabs)
    - CSV genérico con columnas fecha/open/high/low/close[/volume] (p. ej. Dukascopy o histdata convertidos)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

OHLC = ["open", "high", "low", "close"]


def _from_mt5_manual_export(raw: pd.DataFrame, point: float | None) -> pd.DataFrame:
    cols = {c: c.strip("<>").lower() for c in raw.columns}
    raw = raw.rename(columns=cols)
    ts = pd.to_datetime(raw["date"].astype(str) + " " + raw.get("time", "00:00:00").astype(str),
                        format="mixed")
    out = raw[["open", "high", "low", "close"]].copy()
    out.index = ts
    out["volume"] = raw["tickvol"].to_numpy() if "tickvol" in raw else 0.0
    if "spread" in raw and point:
        # MT5 exporta el spread en "points" (1 pip = 10 points en pares de 5 decimales)
        out["spread_pips"] = raw["spread"].to_numpy() * point
    return out


def load_ohlc_csv(path: str | Path, *, tz: str = "UTC", point_to_pip: float | None = None) -> pd.DataFrame:
    """Lee un CSV de velas y lo normaliza al formato interno.

    tz: zona horaria en la que vienen las fechas del archivo. MetaTrader usa la hora del
        servidor del broker (normalmente UTC+2/UTC+3); pásala para convertir a UTC
        (p. ej. tz="Etc/GMT-2" significa UTC+2 en notación POSIX).
    point_to_pip: solo para exportaciones manuales de MT5 con columna <SPREAD> en points;
        en pares de 5 decimales es 0.1 (10 points = 1 pip).
    """
    path = Path(path)
    sep = "\t" if path.read_text(errors="ignore").split("\n", 1)[0].count("\t") >= 3 else ","
    raw = pd.read_csv(path, sep=sep)

    if any(str(c).startswith("<") for c in raw.columns):
        df = _from_mt5_manual_export(raw, point_to_pip)
    else:
        raw.columns = [str(c).strip().lower() for c in raw.columns]
        time_col = next((c for c in ("time", "datetime", "date", "timestamp", "gmt time", "unnamed: 0")
                         if c in raw.columns), None)
        if time_col is None:
            raise ValueError(f"{path.name}: no encuentro la columna de fecha ({list(raw.columns)})")
        ts = raw[time_col]
        if pd.api.types.is_numeric_dtype(ts):
            idx = pd.to_datetime(ts, unit="s")
        else:
            idx = pd.to_datetime(ts, format="mixed", dayfirst=False)
        missing = [c for c in OHLC if c not in raw.columns]
        if missing:
            raise ValueError(f"{path.name}: faltan columnas {missing}")
        df = raw[OHLC].copy()
        df.index = idx
        vol_col = next((c for c in ("tick_volume", "volume", "tickvol") if c in raw.columns), None)
        df["volume"] = raw[vol_col].to_numpy() if vol_col else 0.0
        if "spread_pips" in raw.columns:
            df["spread_pips"] = raw["spread_pips"].to_numpy()

    idx = pd.DatetimeIndex(df.index)
    idx = idx.tz_localize(tz) if idx.tz is None else idx
    df.index = idx.tz_convert("UTC")
    df.index.name = "time"
    df = df.astype(float)
    df = df[~df.index.duplicated(keep="last")].sort_index()
    return df


def load_sample_eurusd_h1() -> pd.DataFrame:
    """EURUSD H1 de ejemplo (abr-2017 a feb-2018) del paquete backtesting.py.

    Sirve para comprobar que el laboratorio corre. NO alcanza para validar una estrategia:
    son ~5.000 velas H1 y la Fase 1 pide 10+ años.
    """
    try:
        from backtesting.test import EURUSD  # type: ignore
    except ImportError as e:  # pragma: no cover
        raise ImportError("Instala los datos de muestra con: pip install -e '.[muestra]'") from e
    df = EURUSD.rename(columns=str.lower)[["open", "high", "low", "close", "volume"]].copy()
    df.index = pd.DatetimeIndex(df.index).tz_localize("UTC")
    df.index.name = "time"
    return df.astype(float)


@dataclass
class DataReport:
    rows: int
    start: pd.Timestamp | None
    end: pd.Timestamp | None
    problems: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems


def validate_ohlc(df: pd.DataFrame, max_gap: pd.Timedelta = pd.Timedelta(days=4)) -> DataReport:
    """Revisa que las velas sean coherentes. Los fines de semana (gap ≤ 4 días) son normales."""
    rep = DataReport(len(df), df.index.min() if len(df) else None, df.index.max() if len(df) else None)
    if df.empty:
        rep.problems.append("No hay datos")
        return rep
    if not df.index.is_monotonic_increasing:
        rep.problems.append("Fechas desordenadas")
    if df.index.has_duplicates:
        rep.problems.append("Fechas duplicadas")
    if df[OHLC].isna().any().any():
        rep.problems.append(f"{int(df[OHLC].isna().any(axis=1).sum())} velas con valores vacíos")
    bad_high = df["high"] < df[["open", "close"]].max(axis=1) - 1e-12
    bad_low = df["low"] > df[["open", "close"]].min(axis=1) + 1e-12
    if bad_high.any() or bad_low.any():
        rep.problems.append(f"{int((bad_high | bad_low).sum())} velas con high/low incoherente")
    if rep.start is not None and rep.start.year < 1990:
        rep.problems.append(f"Fechas desde {rep.start.year}: ¿la columna de tiempo está en otra unidad (ms/µs)?")
    if (df[OHLC] <= 0).any().any():
        rep.problems.append("Precios ≤ 0")
    gaps = df.index.to_series().diff()
    big = gaps[gaps > max_gap]
    if len(big):
        rep.problems.append(f"{len(big)} huecos de más de {max_gap.days} días (el mayor: {big.max()})")
    return rep


def daily_bars(df: pd.DataFrame) -> pd.DataFrame:
    """Velas diarias de forex con cierre a las 17:00 de Nueva York (el estándar del mercado).

    Un resample "D" en UTC crearía velas de domingo de 2 horas (el mercado abre el domingo
    ~22:00 UTC) que distorsionan el ADR y la volatilidad. Aquí lo del domingo se suma al lunes.
    La etiqueta de cada vela es la fecha de su día de operación, a las 00:00 UTC.
    """
    shifted = df.copy()
    shifted.index = df.index.tz_convert("America/New_York") + pd.Timedelta(hours=7)
    agg = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    if "spread_pips" in df:
        agg["spread_pips"] = "mean"
    out = shifted.groupby(shifted.index.date).agg(agg)
    out.index = pd.DatetimeIndex(pd.to_datetime(out.index)).tz_localize("UTC")
    out.index.name = "time"
    return out[out.index.dayofweek < 5]


def resample_ohlc(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    """Agrupa velas (p. ej. H1 → '4h', 'D'). Las velas sin datos (fines de semana) se descartan."""
    agg = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    if "spread_pips" in df:
        agg["spread_pips"] = "mean"
    out = df.resample(rule, label="left", closed="left").agg(agg)
    return out.dropna(subset=["open", "close"])
