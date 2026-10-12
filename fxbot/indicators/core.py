"""Indicadores técnicos como series (una fila por vela).

La mayoría son un port fiel de Caracas-Portafolio
(frontend/src/app/graficos/graficos.component.ts). Allá cada indicador devuelve solo el
último valor; aquí devuelven la serie completa, y el valor de la vela i usa SOLO datos
hasta la vela i (sin mirar al futuro). tests/test_paridad_caracas.py comprueba que
la última fila coincide con el código original.

Indicadores de volumen (obv, ad_line, chaikin, mfi, cvd, liquidity_z): en forex spot
solo hay "tick volume" (cuántas veces cambió el precio), no volumen negociado. Son
señales de BAJA CONFIANZA en forex; úsalos solo si el backtest demuestra que aportan.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view

# ── utilidades ──────────────────────────────────────────────────────────────


def _s(values: np.ndarray, like: pd.Series | pd.DataFrame, name: str) -> pd.Series:
    return pd.Series(values, index=like.index, name=name)


def _trailing(arr: np.ndarray, period: int, func, min_len: int) -> np.ndarray:
    """Aplica func a la ventana arr[max(0, i-period+1) : i+1] (crece hasta `period`)."""
    out = np.full(len(arr), np.nan)
    for i in range(len(arr)):
        w = arr[max(0, i - period + 1): i + 1]
        if len(w) >= min_len:
            out[i] = func(w)
    return out


# ── medias ──────────────────────────────────────────────────────────────────


def sma(x: pd.Series, period: int) -> pd.Series:
    return x.rolling(period).mean().rename(f"sma{period}")


def _ema_np(v: np.ndarray, period: int) -> np.ndarray:
    """EMA con semilla = SMA de los primeros `period` valores válidos (igual que Caracas-Portafolio)."""
    out = np.full(len(v), np.nan)
    valid = np.flatnonzero(~np.isnan(v))
    if len(valid) < period:
        return out
    start = valid[0]
    k = 2 / (period + 1)
    seed_end = start + period - 1
    e = float(np.mean(v[start: seed_end + 1]))
    out[seed_end] = e
    for i in range(seed_end + 1, len(v)):
        e = v[i] * k + e * (1 - k)
        out[i] = e
    return out


def ema(x: pd.Series, period: int) -> pd.Series:
    return _s(_ema_np(x.to_numpy(float), period), x, f"ema{period}")


# ── osciladores ─────────────────────────────────────────────────────────────


def _rsi_np(v: np.ndarray, p: int) -> np.ndarray:
    out = np.full(len(v), np.nan)
    if len(v) <= p:
        return out
    d = np.diff(v)
    ag = np.clip(d[:p], 0, None).sum() / p
    al = np.clip(-d[:p], 0, None).sum() / p

    def val(g, l):
        return (50.0 if g == 0 else 100.0) if l == 0 else 100 - 100 / (1 + g / l)

    out[p] = val(ag, al)
    for i in range(p + 1, len(v)):
        di = d[i - 1]
        ag = (ag * (p - 1) + max(di, 0)) / p
        al = (al * (p - 1) + max(-di, 0)) / p
        out[i] = val(ag, al)
    return out


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """RSI de Wilder. Precio plano = 50."""
    return _s(_rsi_np(close.to_numpy(float), period), close, f"rsi{period}")


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    line = ema(close, fast) - ema(close, slow)
    sig = ema(line, signal)
    return pd.DataFrame({"macd": line, "signal": sig, "hist": line - sig})


def stoch_k(df: pd.DataFrame, period: int = 14) -> pd.Series:
    hh = df["high"].rolling(period).max()
    ll = df["low"].rolling(period).min()
    rng = hh - ll
    k = np.where(rng == 0, 50.0, (df["close"] - ll) / rng.replace(0, np.nan) * 100)
    k = pd.Series(k, index=df.index, name="stoch_k")
    return k.where(hh.notna())


def stoch_d(df: pd.DataFrame, period: int = 14, smooth: int = 3) -> pd.Series:
    return stoch_k(df, period).rolling(smooth).mean().rename("stoch_d")


def dyn_rsi(close: pd.Series, base_period: int = 14) -> pd.Series:
    """El "DMI" del panel Analytics de Caracas-Portafolio.

    OJO: no es el DMI de Welles Wilder (eso es plus_di/minus_di en adx()). Es un RSI cuyo
    período se adapta a la volatilidad de las últimas 5 velas: más volátil → período más corto.
    """
    v = close.to_numpy(float)
    rsis = {p: _rsi_np(v, p) for p in range(5, 31)}
    out = np.full(len(v), 50.0)
    for i in range(len(v)):
        if i + 1 < base_period + 5:
            continue
        recent = v[i - 4: i + 1]
        mean = recent.mean()
        vol_pct = recent.std() / mean * 100 if mean > 0 else 1.0
        p = max(5, min(30, int(np.floor(base_period / max(vol_pct, 0.5) + 0.5))))
        if i + 1 >= p + 1 and not np.isnan(rsis[p][i]):
            out[i] = rsis[p][i]
    return _s(out, close, "dyn_rsi")


# ── tendencia ───────────────────────────────────────────────────────────────


def true_range(df: pd.DataFrame) -> pd.Series:
    prev = df["close"].shift(1)
    tr = pd.concat([df["high"] - df["low"], (df["high"] - prev).abs(), (df["low"] - prev).abs()], axis=1).max(axis=1)
    tr.iloc[0] = np.nan  # la primera vela no tiene cierre previo (igual que el original)
    return tr.rename("tr")


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """ATR de Wilder (en precio). Es el que se usa para colocar stops."""
    tr = true_range(df).to_numpy()
    out = np.full(len(tr), np.nan)
    if len(tr) > period:
        a = np.mean(tr[1: period + 1])
        out[period] = a
        for i in range(period + 1, len(tr)):
            a = (a * (period - 1) + tr[i]) / period
            out[i] = a
    return _s(out, df, f"atr{period}")


def atr_pct(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """"ATR %" de Caracas-Portafolio: media SIMPLE de los últimos `period` TR / cierre × 100."""
    return (true_range(df).rolling(period).mean() / df["close"] * 100).rename("atr_pct")


def _wilder_sum_smooth(arr: np.ndarray, p: int) -> np.ndarray:
    """smooth() de Caracas-Portafolio: semilla = suma de p valores; luego suma - suma/p + x."""
    out = np.full(len(arr), np.nan)
    if len(arr) < p:
        return out
    s = arr[:p].sum()
    out[p - 1] = s / p
    for i in range(p, len(arr)):
        s = s - s / p + arr[i]
        out[i] = s / p
    return out


def adx(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """ADX con +DI y −DI (el DMI de Wilder). ADX > 25 suele indicar tendencia."""
    h, l, c = (df[k].to_numpy(float) for k in ("high", "low", "close"))
    n = len(df)
    res = pd.DataFrame(np.nan, index=df.index, columns=["plus_di", "minus_di", "adx"])
    if n < period + 1:
        return res
    tr = np.maximum.reduce([h[1:] - l[1:], np.abs(h[1:] - c[:-1]), np.abs(l[1:] - c[:-1])])
    up, down = h[1:] - h[:-1], l[:-1] - l[1:]
    pdm = np.where((up > down) & (up > 0), up, 0.0)
    mdm = np.where((down > up) & (down > 0), down, 0.0)
    trs, ps, ms = (_wilder_sum_smooth(a, period) for a in (tr, pdm, mdm))
    with np.errstate(invalid="ignore", divide="ignore"):
        pdi = np.where(trs > 0, ps / trs * 100, 0.0)
        mdi = np.where(trs > 0, ms / trs * 100, 0.0)
        tot = pdi + mdi
        dx = np.where(tot > 0, np.abs(pdi - mdi) / tot * 100, 0.0)
    valid = ~np.isnan(trs)
    pdi[~valid] = np.nan
    mdi[~valid] = np.nan
    dx_valid = dx[valid]
    adx_part = _wilder_sum_smooth(dx_valid, period)
    adx_full = np.full(n - 1, np.nan)
    adx_full[np.flatnonzero(valid)] = adx_part
    res["plus_di"] = np.r_[np.nan, pdi]
    res["minus_di"] = np.r_[np.nan, mdi]
    res["adx"] = np.r_[np.nan, adx_full]
    return res


def aroon(df: pd.DataFrame, period: int = 25) -> pd.DataFrame:
    """Aroon sobre period+1 velas; 100 = el máximo (o mínimo) es la vela actual."""
    res = pd.DataFrame(np.nan, index=df.index, columns=["aroon_up", "aroon_down"])
    if len(df) <= period:
        return res
    hw = sliding_window_view(df["high"].to_numpy(float), period + 1)
    lw = sliding_window_view(df["low"].to_numpy(float), period + 1)
    # lastIndexOf: la ÚLTIMA aparición del extremo dentro de la ventana
    idx_h = period - np.argmax(hw[:, ::-1], axis=1)
    idx_l = period - np.argmin(lw[:, ::-1], axis=1)
    res.iloc[period:, 0] = idx_h / period * 100
    res.iloc[period:, 1] = idx_l / period * 100
    return res


def momentum(close: pd.Series, period: int = 20) -> pd.Series:
    """% de distancia del cierre a la SMA de las `period` velas ANTERIORES."""
    prev_sma = close.shift(1).rolling(period).mean()
    return ((close - prev_sma) / prev_sma * 100).rename("momentum")


def autocorr(close: pd.Series, period: int = 30) -> pd.Series:
    """Autocorrelación lag-1 de los retornos de las últimas `period` velas.
    > 0: los movimientos tienden a continuar; < 0: tienden a revertir; ≈ 0: ruido."""
    v = close.to_numpy(float)

    def f(w):
        r = np.diff(w) / np.where(w[:-1] == 0, 1, w[:-1])
        if len(r) < 4:
            return 0.0
        x, y = r[:-1], r[1:]
        dx, dy = x - x.mean(), y - y.mean()
        den = np.sqrt((dx ** 2).sum()) * np.sqrt((dy ** 2).sum())
        return float((dx * dy).sum() / den) if den > 0 else 0.0

    return _s(_trailing(v, period + 1, f, 10), close, "autocorr")


# ── volatilidad y rango ─────────────────────────────────────────────────────


def bollinger(close: pd.Series, period: int = 20, mult: float = 2.0) -> pd.DataFrame:
    mid = close.rolling(period).mean()
    sd = close.rolling(period).std(ddof=0)
    return pd.DataFrame({"bb_upper": mid + mult * sd, "bb_mid": mid, "bb_lower": mid - mult * sd})


def bbw(close: pd.Series, period: int = 20, mult: float = 2.0) -> pd.Series:
    """Ancho de Bollinger en % del precio medio. Contracción = posible expansión próxima."""
    mid = close.rolling(period).mean()
    sd = close.rolling(period).std(ddof=0)
    return (mult * 2 * sd / mid * 100).rename("bbw")


def adr_pct(daily: pd.DataFrame, period: int = 20) -> pd.DataFrame:
    """ADR % (rango diario promedio) y cuánto del rango normal ya consumió la vela actual.

    Se calcula sobre velas DIARIAS. En forex es muy útil: si el par ya recorrió ~100 % de su
    ADR, perseguir el movimiento suele salir caro.
    """
    rng = (daily["high"] - daily["low"]) / daily["low"].where(daily["low"] > 0) * 100
    rng = rng.fillna(0.0)
    adr = rng.rolling(period, min_periods=2).mean()
    used = (rng / adr.replace(0, np.nan) * 100).clip(upper=200).fillna(0.0)
    return pd.DataFrame({"adr_pct": adr, "adr_used_pct": used})


# ── posición estadística del precio ─────────────────────────────────────────


def price_percentile(close: pd.Series, period: int = 252) -> pd.Series:
    """Percentil del cierre actual frente a los últimos `period` cierres (incluido él)."""
    v = close.to_numpy(float)
    return _s(_trailing(v, period, lambda w: float(np.floor((w <= w[-1]).sum() / len(w) * 100 + 0.5)), 5),
              close, "pct252")


def value_zone_z(close: pd.Series, period: int = 252) -> pd.Series:
    """Z-score del cierre frente a su media de `period` velas. < −1 "barata", > 1 "cara"."""
    v = close.to_numpy(float)

    def f(w):
        sd = w.std()
        return float((w[-1] - w.mean()) / sd) if sd > 0 else 0.0

    return _s(_trailing(v, period, f, 20), close, "value_z")


def value_zone_label(z: float) -> str:
    if np.isnan(z):
        return "Sin datos"
    if z > 2:
        return "BURBUJA"
    if z > 1:
        return "CARA"
    if z > -1:
        return "NEUTRAL"
    if z > -2:
        return "BARATA"
    return "HIST. MÍN."


def kelly_half_returns(close: pd.Series, period: int = 60) -> pd.Series:
    """Half-Kelly calculado sobre los retornos de las velas (como en Caracas-Portafolio).

    Para el bot NO se usa esto para dimensionar: el Kelly correcto se calcula con los
    resultados de las OPERACIONES de la estrategia (ver fxbot.risk.sizing.kelly_from_trades).
    """
    v = close.to_numpy(float)

    def f(w):
        r = np.diff(w) / np.where(w[:-1] == 0, 1, w[:-1])
        wins, losses = r[r > 0], r[r < 0]
        if not len(wins) or not len(losses):
            return 0.0
        p = len(wins) / len(r)
        b = wins.mean() / abs(losses.mean())
        return float(max(0.0, min(1.0, (p * b - (1 - p)) / b / 2)))

    return _s(_trailing(v, period, f, 10), close, "kelly_half")


# ── volumen (baja confianza en forex) ───────────────────────────────────────


def obv(df: pd.DataFrame) -> pd.Series:
    sign = np.sign(df["close"].diff().fillna(0.0))
    return (sign * df["volume"]).cumsum().rename("obv")


def ad_line(df: pd.DataFrame) -> pd.Series:
    rng = df["high"] - df["low"]
    mfm = ((df["close"] - df["low"]) - (df["high"] - df["close"])) / rng.replace(0, np.nan)
    return (mfm.fillna(0.0) * df["volume"]).cumsum().rename("ad_line")


def chaikin(df: pd.DataFrame) -> pd.Series:
    adl = ad_line(df)
    return (ema(adl, 3) - ema(adl, 10)).rename("chaikin")


def mfi(df: pd.DataFrame, period: int = 14) -> pd.Series:
    tp = (df["high"] + df["low"] + df["close"]) / 3
    flow = tp * df["volume"]
    d = tp.diff()
    pos = flow.where(d > 0, 0.0).rolling(period).sum()
    neg = flow.where(d < 0, 0.0).rolling(period).sum()
    out = 100 - 100 / (1 + pos / neg.replace(0, np.nan))
    out = out.where(neg != 0, np.where(pos > 0, 100.0, 50.0))
    # el original exige period+1 velas (cada flujo se compara con la vela anterior)
    enough = pd.Series(np.arange(len(df)) >= period, index=df.index)
    return out.where(enough).rename("mfi")


def cvd(df: pd.DataFrame) -> pd.DataFrame:
    """Delta de volumen estimado con OHLC (estimador de Williams) y su acumulado."""
    rng = df["high"] - df["low"]
    buy = np.where(rng > 0, df["volume"] * (df["close"] - df["low"]) / rng.replace(0, np.nan), df["volume"] * 0.5)
    delta = pd.Series(buy * 2 - df["volume"].to_numpy(), index=df.index)
    return pd.DataFrame({"cvd_delta": delta, "cvd": delta.cumsum()})


def liquidity_z(df: pd.DataFrame, period: int = 20) -> pd.Series:
    """Z-score del volumen de la vela frente a las `period` anteriores."""
    prev = df["volume"].shift(1)
    mean = prev.rolling(period).mean()
    sd = prev.rolling(period).std(ddof=0)
    return ((df["volume"] - mean) / sd.replace(0, np.nan)).fillna(0.0).where(mean.notna()).rename("liquidity_z")


def volume_profile(df: pd.DataFrame, bins: int = 40) -> dict:
    """POC (precio con más volumen) y LVN (vacío de volumen) sobre las velas dadas."""
    if len(df) < 5:
        return {"poc": 0.0, "lvn": 0.0, "levels": []}
    lo, hi = float(df["low"].min()), float(df["high"].max())
    if hi - lo < 1e-10:
        return {"poc": 0.0, "lvn": 0.0, "levels": []}
    size = (hi - lo) / bins
    vols = np.zeros(bins)
    for h, l, c, v in df[["high", "low", "close", "volume"]].itertuples(index=False):
        for b in range(bins):
            b_lo = lo + b * size
            b_hi = b_lo + size
            if h - l > 0:
                ov = min(h, b_hi) - max(l, b_lo)
                if ov > 0:
                    vols[b] += v * ov / (h - l)
            elif b_lo <= c < b_hi:
                vols[b] += v
    if vols.max() == 0:
        return {"poc": 0.0, "lvn": 0.0, "levels": []}
    poc_i = int(np.argmax(vols))
    s, e = int(np.floor(bins * 0.1)), int(np.ceil(bins * 0.9))
    lvn_i = s + int(np.argmin(vols[s:e]))
    mid = lambda i: lo + i * size + size / 2  # noqa: E731
    return {"poc": mid(poc_i), "lvn": mid(lvn_i),
            "levels": [{"price": mid(i), "volume": float(vols[i])} for i in range(bins)]}


def all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Tabla con todos los indicadores del panel Analytics, vela por vela."""
    out = pd.concat([
        ema(df["close"], 20), ema(df["close"], 50), ema(df["close"], 200),
        rsi(df["close"]), macd(df["close"]), adx(df), aroon(df), atr(df), atr_pct(df),
        bbw(df["close"]), stoch_k(df), dyn_rsi(df["close"]), momentum(df["close"]),
        autocorr(df["close"]), price_percentile(df["close"]), value_zone_z(df["close"]),
        kelly_half_returns(df["close"]), obv(df), ad_line(df), chaikin(df), mfi(df), cvd(df),
        liquidity_z(df),
    ], axis=1)
    return out
