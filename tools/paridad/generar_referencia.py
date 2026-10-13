"""Genera tests/fixtures/paridad_caracas.json ejecutando el código ORIGINAL de Caracas-Portafolio.

- Indicadores del panel Analytics: extrae los métodos de graficos.component.ts tal cual,
  los envuelve en una clase y los ejecuta con Node (--experimental-strip-types).
- VIX proxy: extrae realized_vol_stats() y sus ayudantes de backend/app/api/stocks.py con ast.

Uso:
    python tools/paridad/generar_referencia.py /ruta/a/caracas-portafolio

Hay que volver a correrlo si cambias un indicador en Caracas-Portafolio, para que el bot
siga calculando exactamente lo mismo que tu web.
"""
from __future__ import annotations

import ast
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
FIXTURE = HERE.parents[1] / "tests" / "fixtures" / "paridad_caracas.json"

TS_METHODS = [
    "obv", "accumulationDistribution", "adlSeriesArr", "aroon", "aroonAt", "adx", "directional", "chaikin", "emaOfArray",
    "atrPercentile", "calcAdr", "calcBbw", "dmi", "stochastic", "mfi", "calcMarketRegime", "_rollingStd",
    "calcCvd", "calcPricePercentile", "calcValueZone", "calcKelly", "calcAutoCorr", "calcLiquidityZ",
    "calcMomentum", "calcRsi", "ema", "calcVolumeProfile",
]
LENGTHS = [12, 20, 25, 30, 45, 60, 90, 130, 200, 260, 320]


def synthetic_candles(n: int = 320, seed: int = 7) -> list[dict]:
    rng = np.random.default_rng(seed)
    price, out = 1.10, []
    for i in range(n):
        if 150 <= i < 165:      # tramo plano: casos borde (rangos 0, divisiones por 0)
            o = h = l = c = price
        else:
            drift = 0.0015 if i < 100 else (-0.0012 if i < 220 else 0.0)
            sd = 0.045 if 230 <= i < 240 else 0.004   # ráfaga de volatilidad → régimen "volatil"
            o = price
            c = o * (1 + drift + rng.normal(0, sd))
            h = max(o, c) * (1 + abs(rng.normal(0, 0.002)))
            l = min(o, c) * (1 - abs(rng.normal(0, 0.002)))
            price = c
        out.append({"time": f"t{i:04d}", "open": o, "high": h, "low": l, "close": c,
                    "volume": float(rng.integers(500, 5000))})
    return out


def kelly_candles(n: int = 300, seed: int = 25) -> list[dict]:
    """Serie con deriva y volatilidad moderadas: el Kelly ½ cae entre 0 y 1 (no en los topes)."""
    rng = np.random.default_rng(seed)
    p, out = 100.0, []
    for i in range(n):
        p *= 1 + 0.0006 + rng.normal(0, 0.025)
        out.append({"time": f"k{i:04d}", "open": p, "high": p, "low": p, "close": p, "volume": 1.0})
    return out


def extract_method(src: str, name: str) -> str:
    """Devuelve el texto del método `private name(...) {...}` contando llaves."""
    marker = f"private {name}("
    start = src.find(marker)
    if start < 0:
        raise SystemExit(f"No encontré el método {name} en graficos.component.ts")
    # el cuerpo empieza en la primera '{' después del cierre de la firma
    depth_paren, i = 0, start + len(marker) - 1
    while True:
        ch = src[i]
        depth_paren += ch == "("
        depth_paren -= ch == ")"
        i += 1
        if depth_paren == 0:
            break
    # saltar el tipo de retorno (puede ser un literal "{ up: number; ... }" de varias líneas)
    depth, expect_type = 0, False
    while True:
        ch = src[i]
        if ch in ":|&" and depth == 0:
            expect_type = True
        elif ch == "{" and depth == 0 and not expect_type:
            body_start = i
            break
        elif ch in "{[(<":
            depth += 1
            expect_type = False
        elif ch in "}])>":
            depth -= 1
        elif not ch.isspace():
            expect_type = False
        i += 1
    depth, j = 0, body_start
    while True:
        depth += src[j] == "{"
        depth -= src[j] == "}"
        j += 1
        if depth == 0:
            return src[start:j]


def run_ts(caracas: Path, candles: list[dict]) -> dict:
    src = (caracas / "frontend/src/app/graficos/graficos.component.ts").read_text()
    methods = "\n\n".join("  " + extract_method(src, m) for m in TS_METHODS)
    rf = re.search(r"KELLY_RISK_FREE\s*=\s*([0-9.]+)", src)
    harness = f"""
const KELLY_RISK_FREE = {rf.group(1) if rf else "0.04"};
type Candle = {{ time: string; open: number; high: number; low: number; close: number; volume: number }};
class Ref {{
{methods}
}}
const candles: Candle[] = JSON.parse(process.argv[2]);
const lengths: number[] = JSON.parse(process.argv[3]);
const r = new Ref() as any;
const out: any = {{}};
for (const n of lengths) {{
  const d = candles.slice(0, n);
  const closes = d.map(c => c.close), times = d.map(c => c.time);
  const rsi = r.calcRsi(closes, times, 14);
  const ema20 = r.ema(closes, times, 20);
  out[n] = {{
    obv: r.obv(d), ad_line: r.accumulationDistribution(d), chaikin: r.chaikin(d),
    aroon: r.aroon(d), adx: r.adx(d), atr_pct: r.atrPercentile(d), adr: r.calcAdr(d), bbw: r.calcBbw(d),
    dmi: r.dmi(d), stoch: r.stochastic(d), mfi: r.mfi(d), regime: r.calcMarketRegime(d),
    cvd: r.calcCvd(d), pct252: r.calcPricePercentile(d), value_zone: r.calcValueZone(d),
    kelly: r.calcKelly(d), autocorr: r.calcAutoCorr(d, 30), liquidity_z: r.calcLiquidityZ(d),
    momentum: r.calcMomentum(d), rsi14: rsi.length ? rsi[rsi.length - 1].value : null,
    ema20: ema20.length ? ema20[ema20.length - 1].value : null,
    vp: (() => {{ const v = r.calcVolumeProfile(d); return {{ poc: v.poc, lvn: v.lvn }}; }})(),
  }};
}}
out.regimes = candles.map((_, i) => r.calcMarketRegime(candles.slice(0, i + 1)));
const mid: Candle[] = JSON.parse(process.argv[4]);
out.kelly_mid = [100, 200, 300].map(n => r.calcKelly(mid.slice(0, n)));
console.log(JSON.stringify(out));
"""
    with tempfile.TemporaryDirectory() as tmp:
        f = Path(tmp) / "ref.ts"
        f.write_text(harness)
        res = subprocess.run(["node", "--experimental-strip-types", "--no-warnings", str(f),
                              json.dumps(candles), json.dumps(LENGTHS), json.dumps(kelly_candles())],
                             capture_output=True, text=True)
    if res.returncode:
        raise SystemExit(res.stderr)
    return json.loads(res.stdout)


def run_vol_proxy(caracas: Path, closes: list[float]) -> list[dict]:
    src = (caracas / "backend/app/api/stocks.py").read_text()
    tree = ast.parse(src)
    keep = {"_index_log_returns", "_annualized_vol", "realized_vol_stats"}
    nodes = [n for n in tree.body
             if (isinstance(n, ast.FunctionDef) and n.name in keep)
             or (isinstance(n, ast.Assign) and any(getattr(t, "id", "").startswith("_VOL_") for t in n.targets))]
    ns: dict = {"Optional": object}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), "stocks_vol", "exec"), ns)
    return [ns["realized_vol_stats"](closes[:n]) for n in (40, 60, 120, 200, 320)]


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    caracas = Path(sys.argv[1])
    candles = synthetic_candles()
    long_closes = [c["close"] for c in synthetic_candles(320, seed=11)]
    data = {"candles": candles, "lengths": LENGTHS, "ts": run_ts(caracas, candles), "kelly_candles": kelly_candles(),
            "vol_closes": long_closes, "vol_proxy": run_vol_proxy(caracas, long_closes)}
    FIXTURE.parent.mkdir(parents=True, exist_ok=True)
    FIXTURE.write_text(json.dumps(data, indent=1))
    print(f"Fixture escrito en {FIXTURE}")


if __name__ == "__main__":
    main()
