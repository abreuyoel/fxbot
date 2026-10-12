# fxbot: bot de trading de forex (Fase 1: laboratorio)

Bot de forex en Python, pensado para operar desde Venezuela con $500–1000, y que reutiliza los
indicadores de [Caracas-Portafolio](https://github.com/abreuyoel/Caracas-Portafolio).

> **Aviso.** Esto no es asesoría financiera. El trading con apalancamiento puede hacerte perder
> todo el capital. El bot no opera con dinero real hasta que aprueba las fases 1 y 2.

## Estado

| Fase | Qué es | Estado |
|---|---|---|
| **1. Laboratorio** | Datos, indicadores, backtest con costos reales, walk-forward, Monte Carlo, what-if | ✅ Construido. Falta correrlo con 10+ años de tus datos |
| 2. Demo | Conector cTrader/MT5 en cuenta demo, Telegram, filtro de IA, diario | Pendiente |
| 3. Real micro | $500, 0,5 % por operación | Pendiente |
| 4. Real normal | $1000, 1 % por operación, panel en caracasportafolio.com | Pendiente |

Documentos:
- [`docs/PROMPT_MAESTRO.md`](docs/PROMPT_MAESTRO.md): el encargo completo del sistema, ajustado a tus respuestas.
- [`docs/PROMPT_IA_TIEMPO_REAL.md`](docs/PROMPT_IA_TIEMPO_REAL.md): los prompts de la IA (filtro de señales, resúmenes de Londres y NY, revisión semanal).
- [`docs/BROKERS_Y_DINERO.md`](docs/BROKERS_Y_DINERO.md): broker, cómo fondear desde Venezuela, dónde correr el bot y cuánto cuesta.
- [`docs/INDICADORES.md`](docs/INDICADORES.md): equivalencia con tu web y lo que encontré revisando tu código.

## Instalar

```bash
cd trading-bot
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -e ".[dev,muestra]"
pytest                                               # 70 pruebas
```

## Usar el laboratorio

**1. Probar que todo corre** (datos de muestra: EURUSD H1, abr-2017 a feb-2018):

```bash
python -m fxbot.lab.run --muestra
```

**2. Bajar tus datos reales.** En Windows, con MetaTrader 5 abierto en la demo de FP Markets:

```bash
pip install MetaTrader5
python scripts/descargar_datos_mt5.py --simbolos EURUSD GBPUSD USDJPY --desde 2012-01-01
```

**3. Correr la validación de verdad:**

```bash
python -m fxbot.lab.run --csv datos/EURUSD_H1.csv --tf 4h --capital 500 --walkforward
python -m fxbot.lab.run --csv datos/EURUSD_H1.csv --tf 1h --capital 500 --walkforward
```

Opciones útiles:
- `--riesgo 0.5`: % de riesgo por operación.
- `--dd-max 20`: caída que apaga el bot.
- `--comision 7`: USD por lote, ida y vuelta.
- `--wf-entreno-meses 24 --wf-prueba-meses 6`: tamaño de las ventanas del walk-forward.

Los resultados quedan en `resultados/`: `operaciones.csv`, `equity.csv`, `resumen.json` y las
ventanas del walk-forward.

### Cómo leer el reporte

- **Backtest completo:** una sola historia, optimista porque los parámetros se eligieron mirando esos mismos datos.
- **Por banda del VIX proxy / régimen:** en qué condiciones gana o pierde la estrategia.
- **What-if:** qué pasa si el spread se duplica, si hay más deslizamiento, si usas una cuenta estándar o si cambias el riesgo.
- **Walk-forward:** elige parámetros con 2 años de datos y los prueba en los 6 meses siguientes, que nunca vio. **Solo esto cuenta.**
- **Monte Carlo:** 5000 versiones de la historia con las mismas operaciones. Da la caída esperada y la probabilidad de llegar al −20 %.
- **Veredicto:** pasa a demo solo con ≥ 300 operaciones fuera de muestra, profit factor > 1,3 y ruina < 5 %.

## Qué hay adentro

```
fxbot/
  instruments.py        pip, contrato, lotaje y valor del pip por par
  data/loaders.py       CSV de MT5 (script o exportación manual), validación, velas H4 y diarias (cierre 17:00 NY)
  indicators/core.py    indicadores de Caracas-Portafolio como series, sin mirar al futuro
  regime/vol_proxy.py   VIX proxy: vol. realizada 30 velas + percentil + bandas para forex
  regime/market_regime.py  régimen multi-timeframe (calibración bvc = idéntica a la web; fx = para forex)
  strategies/           línea base: cruce EMA + ADX, stops por ATR, filtro de VIX proxy
  risk/sizing.py        tamaño de posición con costos, límites duros, Kelly desde operaciones
  lab/                  backtest, costos (spread, comisión, swap, deslizamiento), métricas, Monte Carlo, walk-forward, CLI
scripts/descargar_datos_mt5.py   histórico desde MetaTrader 5 (convierte la hora del servidor a UTC)
tools/paridad/                   regenera la prueba de paridad ejecutando el código original de tu web
```

### Supuestos del backtest (conservadores a propósito)

- La señal se calcula al cierre de una vela y se entra a la apertura de la siguiente.
- Comprar paga el ask (bid + spread). Las salidas de una venta también pagan el spread.
- Si una vela toca el stop y el objetivo, cuenta como stop.
- Un gap más allá del stop sale a la apertura, que puede costar más de 1R. Los gaps de fin de semana existen.
- El swap se cobra a las 17:00 de NY y cuenta triple los miércoles.
- Si con el capital disponible ni 0,01 lotes cabe en el riesgo, la señal se descarta en vez de arriesgar de más.

## Primer hallazgo con los datos de muestra

Con $500 y 1 % de riesgo, en H4 el bot **descartó 14 de 19 señales**. Un stop normal de H4
(50+ pips) con el lote mínimo ya cuesta más de $5. Las alternativas (H1, $1000 o una cuenta
cent) están explicadas en [`docs/BROKERS_Y_DINERO.md`](docs/BROKERS_Y_DINERO.md#ojo-con-el-capital-chico).
