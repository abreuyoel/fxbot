# Indicadores: de Caracas-Portafolio al bot

Los indicadores del bot son un port a Python del código de
[Caracas-Portafolio](https://github.com/abreuyoel/Caracas-Portafolio). El panel "Analytics" de
`/graficos` vive en `frontend/src/app/graficos/graficos.component.ts` y el VIX proxy en
`backend/app/api/stocks.py` (`realized_vol_stats`).

**Paridad comprobada:** `tools/paridad/generar_referencia.py` toma esos métodos tal cual, los
ejecuta con Node sobre velas de prueba y guarda los resultados. `tests/test_paridad_caracas.py`
verifica que el bot da los mismos números, más el régimen vela por vela en los 4 estados.
Si cambias un indicador en la web, vuelve a correr:

```bash
python tools/paridad/generar_referencia.py /ruta/a/caracas-portafolio
pytest tests/test_paridad_caracas.py
```

## Tabla de equivalencias

| Panel Analytics | Función en el bot | ¿Sirve en forex? |
|---|---|---|
| OBV | `obv` | Baja confianza: solo hay tick volume |
| A/D Line | `ad_line` | Baja confianza |
| CVD acumulado / delta | `cvd` | Baja confianza: es una estimación OHLC, no order flow real |
| Chaikin Oscillator | `chaikin` | Baja confianza |
| MFI | `mfi` | Baja confianza |
| ADX | `adx()["adx"]` | Sí |
| DMI (+DI / −DI) | `adx()[["plus_di", "minus_di"]]` | Sí (DMI de Wilder) |
| Aroon Up/Down | `aroon` | Sí |
| Momentum (20D) | `momentum` | Sí |
| Autocorr (30D) | `autocorr` | Sí, útil para elegir tendencia vs. reversión |
| ATR % | `atr_pct` | Sí |
| BBW | `bbw` | Sí |
| ADR % (20D) | `adr_pct` (sobre velas diarias) | Sí, muy útil en forex |
| Stoch %K | `stoch_k` | Sí |
| HVN / POC, LVN | `volume_profile` | Baja confianza |
| Percentil 252D | `price_percentile` | Sí |
| Value Zone (Z-score) | `value_zone_z` + `value_zone_label` | Sí, como contexto |
| Kelly ½ (1 año, USD) | `kelly_half` | Como referencia; el bot usa `kelly_from_trades` |
| Z-Liquidez (20D) | `liquidity_z` | Baja confianza |
| Régimen multi-TF | `regime.market_regime` | Sí, con calibración `fx` |
| Régimen de volatilidad (HMM) | — (en el backend de la web: `/stocks/regime-hmm`) | Candidato a portar al bot si el laboratorio muestra que ayuda |
| VIX proxy (IBC) | `regime.vol_proxy` | Sí, con bandas por percentil |

## Hallazgos al revisar tu código

Estado:
- **Corrección de nombres:** fusionada en [Caracas-Portafolio#17](https://github.com/abreuyoel/Caracas-Portafolio/pull/17).
- **Mejoras de fondo:** en [Caracas-Portafolio#18](https://github.com/abreuyoel/Caracas-Portafolio/pull/18).
  - **Régimen:** HMM gaussiano de 3 estados entrenado sobre retornos en USD, con probabilidades filtradas.
  - **DMI:** la tarjeta muestra el DMI de Wilder (+DI/−DI); se quita el de Chande.
  - **Kelly:** ½ Kelly continuo con 252 sesiones, en USD.

La prueba de paridad del bot ya sigue esas fórmulas nuevas.

1. **El "HMM" no es un HMM.** `calcMarketRegime` dice "Gaussian HMM (4 states)", pero es una
   regla ponderada: la tendencia de 5, 20 y 60 velas con pesos 0,25/0,50/0,25, más un filtro de
   volatilidad. Funciona como heurística. Un HMM entrenado de verdad (`hmmlearn`) se puede probar
   en el laboratorio contra esta versión. Si gana fuera de muestra, se cambia.
2. **El "DMI" es el DMI de Chande, no el de Wilder (corregido en la web).** `dmi()` es el
   *Dynamic Momentum Index* de Tushar Chande: un RSI cuyo período se acorta cuando sube la
   volatilidad. Es un indicador real, pero junto al ADX casi todo el mundo lee "DMI" como el
   direccional de Wilder (+DI/−DI). Por eso un 75,1 al lado de un ADX de 24,5 confundía. En el
   bot se llama `dyn_rsi` y el +DI/−DI está en `adx()`. Además, el panel de IA lo calculaba con
   la semilla vieja y daba 99 con precios planos, así que la IA veía otro número que el usuario.
3. **El Kelly se calcula sobre los retornos diarios de la acción, no sobre operaciones.** Para un
   bot, el Kelly correcto sale de los resultados de la estrategia en múltiplos de R
   (`risk.sizing.kelly_from_trades`). El de la web es una medida de "sesgo alcista" de la acción,
   no un tamaño de posición.
4. **Las bandas del VIX proxy son absolutas** (<18 %, 18–30, 30–50, >50). Están bien para la
   BVC, pero EURUSD se mueve entre 5 % y 10 % anual: siempre caería en "letargo". En el bot las
   bandas son por percentil, que es lo mismo que tu tarjeta ya muestra como "Percentil 71":
   <20 letargo, 20–70 óptimo, 70–90 tensión, >90 pánico.
5. **Los umbrales del régimen están calibrados para la BVC** (vol5 > 60 %, tendencia ±1,5/2,5 %).
   La calibración `fx` mantiene la lógica, pero mide la tendencia en desviaciones típicas del
   propio par. `calibration="bvc"` reproduce la web exacta y es la que usa la prueba de paridad.
6. **"ATR %" usa media simple del True Range**, no la de Wilder. Para colocar stops el bot usa
   `atr()` (Wilder, la estándar). El `atr_pct` de la web se conserva para el panel.
7. **"HVN" y "POC" son el mismo número** en `calcVolumeProfile`. No es un error de cálculo, pero
   la tarjeta "HVN / POC" muestra un solo valor.

## Volumen en forex

El forex spot no tiene una bolsa central, así que nadie publica el volumen negociado. MetaTrader
da el *tick volume*: cuántas veces cambió el precio en la vela. Está correlacionado con la
actividad, pero OBV, CVD, MFI y el perfil de volumen calculados con él son aproximaciones
gruesas. Regla del bot: un indicador de volumen solo entra a una estrategia si el walk-forward
demuestra que mejora el resultado fuera de muestra.

Para tener volumen real del euro se puede usar el futuro 6E del CME como referencia.
