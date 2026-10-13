# fxbot: bot de trading de forex (Fase 1: laboratorio)

Bot de forex en Python para operar desde Venezuela con $500–1000. Usa FP Markets como broker y
reutiliza los indicadores de [Caracas-Portafolio](https://github.com/abreuyoel/Caracas-Portafolio).

> **Aviso.** Esto no es asesoría financiera. El trading con apalancamiento puede hacerte perder
> todo el capital. El bot no opera con dinero real hasta que aprueba las fases 1 y 2.

## Qué hacer ahora: 3 tareas, en este orden

**Tarea 1. Validar el bot (tu PC, 10–15 minutos).**
Abre MetaTrader 5 en tu cuenta demo y haz doble clic en `scripts\validar_windows.bat`. Si ya
bajaste los datos antes, no los vuelve a descargar. Al terminar, manda
`resultados\resumen.json` y `resultados\reporte.txt`.

**Tarea 2. Primera compra de ETF (Binance, cuando la bolsa de EE. UU. esté abierta).**
Doble clic en `scripts\compra_mensual.bat` y responde las preguntas. Compra en Binance lo que te
diga. Si vas a meter $500 en 4 meses, el primer mes son $125: $87,50 de SPYB y $37,50 de SMHB.

**Tarea 3. Mensaje a FP Markets (5 minutos).**
Pega en su chat de soporte el mensaje de `docs/BROKERS_Y_DINERO.md` (sección 1) y guarda la
respuesta. No deposites nada en FP Markets todavía.

Todo lo demás (prompts, cTrader, VPS) es para más adelante y te aviso cuando toque.

## Qué hacer con cada documento

| Documento | Para qué es | Qué haces tú con él |
|---|---|---|
| [`docs/MERCADOS.md`](docs/MERCADOS.md) | ETF (SPY, VOO, VGT, SMH) vs. forex vs. futuros, qué es un bStock y el plan de dinero por etapas | Léelo cuando quieras entender el porqué del 70 % SPYB + 30 % SMHB |
| [`docs/BROKERS_Y_DINERO.md`](docs/BROKERS_Y_DINERO.md) | Broker, fondeo, cTrader, apalancamiento, VPS y costos | Pega en el chat de FP Markets el mensaje de la sección 1 y guarda las respuestas |
| [`docs/PROMPT_MAESTRO.md`](docs/PROMPT_MAESTRO.md) | El encargo completo del sistema: fases, reglas de riesgo y criterios para avanzar | Nada por ahora. Cuando quieras avanzar una fase, pégaselo a Claude Code junto con "haz la Fase 2" |
| [`docs/PROMPT_IA_TIEMPO_REAL.md`](docs/PROMPT_IA_TIEMPO_REAL.md) | Los prompts que usará la IA del bot: filtro de señales, resúmenes de Londres y NY, revisión semanal | Nada por ahora. Se programan en la Fase 2. Puedes leerlos para ajustar el tono o los horarios |
| [`docs/INDICADORES.md`](docs/INDICADORES.md) | Cómo cada indicador de tu web pasó al bot, y lo que encontré en tu código | Revisa y fusiona la rama `claude/kind-hawking-6l9i9m` de Caracas-Portafolio (correcciones de nombres) |

## Estado

| Fase | Qué es | Estado |
|---|---|---|
| **1. Laboratorio** | Datos, indicadores, backtest con costos reales, walk-forward, Monte Carlo, what-if | ✅ Construido. Falta correrlo con tus datos (paso a paso de arriba) |
| 2. Demo | Conector a la demo de FP Markets, Telegram con botón de aprobar, filtro de IA, diario | Pendiente: empieza si la Fase 1 encuentra una estrategia que apruebe |
| 3. Real micro | $500, 0,5 % por operación | Pendiente |
| 4. Real normal | $1000, 1 %, panel en caracasportafolio.com | Pendiente |

## Para desarrolladores

```bash
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -e ".[dev,muestra]"
pytest                                               # 82 pruebas
python -m fxbot.lab.run --muestra                    # prueba rápida con datos de ejemplo
```

Ejemplos de uso del laboratorio:

```bash
# un par
python -m fxbot.lab.run --csv datos/EURUSD_H1.csv --walkforward
# varios pares a la vez: las operaciones fuera de muestra se juntan para el veredicto
python -m fxbot.lab.run --csv datos/EURUSD_H1.csv datos/GBPUSD_H1.csv datos/USDJPY_H1.csv --walkforward
```

Opciones:
- `--tf 1h|4h|D`: temporalidad (por defecto `1h`).
- `--capital 500`: capital inicial.
- `--riesgo 1`: % de riesgo por operación.
- `--riesgo-tope 1.5`: % máximo aceptado cuando solo cabe el lote mínimo (`0` = descartar).
- `--dd-max 20`: caída que apaga el bot.
- `--apalancamiento 30`: apalancamiento de la cuenta; solo limita el margen (ver BROKERS_Y_DINERO.md).
- `--comision 7`: USD por lote, ida y vuelta.
- `--wf-entreno-meses 24 --wf-prueba-meses 6`: tamaño de las ventanas del walk-forward.

Descarga manual de datos (Windows, con MT5 abierto):

```bash
pip install -e ".[mt5]"
python scripts/descargar_datos_mt5.py --simbolos EURUSD GBPUSD USDJPY --desde 2012-01-01
```

El sufijo de los símbolos del broker (`EURUSD.r`, etc.) se detecta solo.

### Cómo leer el reporte

- **Backtest completo:** una sola historia, optimista porque los parámetros se eligieron mirando esos mismos datos.
- **Por banda del VIX proxy / régimen:** en qué condiciones gana o pierde la estrategia.
- **What-if:** qué pasa con spread doble, más deslizamiento, cuenta estándar, sin lote mínimo forzado, o con otro riesgo.
- **Walk-forward:** elige parámetros con 2 años y los prueba en los 6 meses siguientes, que nunca vio. **Solo esto cuenta.**
  - Los parámetros se eligen por "meseta": el combo **y sus vecinos** tienen que funcionar. Un pico aislado suele ser sobreajuste.
  - `train_score_pico` es el puntaje del combo solo; `train_score` es el de la meseta.
- **Monte Carlo:** 5000 versiones de la historia con las mismas operaciones, usando el riesgo efectivo promedio.
- **Veredicto:** pasa a demo solo con ≥ 300 operaciones fuera de muestra (sumando pares), profit factor > 1,3 y ruina < 5 %.

### Qué hay adentro

```
fxbot/
  instruments.py           pip, contrato, lotaje y valor del pip por par
  data/loaders.py          CSV de MT5, validación, velas H4 y diarias (cierre 17:00 NY)
  indicators/core.py       indicadores de Caracas-Portafolio como series, sin mirar al futuro
  regime/vol_proxy.py      VIX proxy: vol. realizada 30 velas + percentil + bandas para forex
  regime/market_regime.py  régimen multi-timeframe (bvc = idéntico a la web; fx = para forex)
  strategies/              línea base: cruce EMA + ADX, stops por ATR, filtro de VIX proxy
  risk/sizing.py           tamaño con costos, tope del lote mínimo, límites duros, Kelly desde operaciones
  lab/                     backtest, costos, métricas, Monte Carlo, walk-forward con meseta, CLI multi-par
scripts/descargar_datos_mt5.py   histórico desde MT5 (hora del servidor → UTC, sufijo automático)
scripts/validar_windows.bat      todo el flujo de la Fase 1 con doble clic
fxbot/portfolio/dca.py           calculadora de compra mensual de ETF hacia tus pesos objetivo
scripts/compra_mensual.bat       la calculadora con preguntas, con doble clic
tools/paridad/                   regenera la prueba de paridad con el código original de tu web
```

### Supuestos del backtest (conservadores a propósito)

- La señal se calcula al cierre de una vela y se entra a la apertura de la siguiente.
- Comprar paga el ask (bid + spread); cerrar una venta también.
- Si una vela toca el stop y el objetivo, cuenta como stop.
- Un gap más allá del stop sale a la apertura, que puede costar más de 1R.
- El swap se cobra a las 17:00 de NY y cuenta triple los miércoles.
- Con capital chico se usa el lote mínimo solo si arriesga ≤ `--riesgo-tope`; si no, la señal se descarta.
- Se respeta el margen: con apalancamiento bajo, la operación se achica o no entra.
