# ¿Forex, futuros, acciones o ETF? Dónde poner cada dólar

**Resumen:** con $500–1000, la combinación que más sentido tiene es:

- **Un núcleo pasivo de ETF en Binance:** 70 % SPYB (S&P 500) y 30 % SMHB (semiconductores),
  con compra mensual fija. El bot no lo especula.
- **Un satélite activo en forex** con el bot, en FP Markets (cTrader). Solo con dinero real
  después de aprobar la demo.

Los futuros quedan fuera por ahora. Todo el ETF va en Binance (SPYB + SMHB); Quantfury no hace falta.

## Comparación

| | ETF S&P 500 (pasivo) | Forex con bot | Acciones sueltas | Futuros (micro) |
|---|---|---|---|---|
| Rendimiento esperado | ~8–10 % anual histórico, sin garantía | Meta 1–3 % mensual, **si** el bot tiene ventaja comprobada; si no, pierde por costos | Lo del mercado ± tu acierto | Igual que el subyacente, pero apalancado |
| Peor caída típica | −20 a −35 % (2020, 2022); −55 % en 2008 | Limitada por el bot a −20 % (se apaga) | Puede ser −50 % o más en una acción | Puede borrar $500 en un día |
| Trabajo | Casi ninguno | Alto al inicio; luego vigilar | Medio | Alto |
| ¿Sirve para el bot? | No hace falta bot: comprar y mantener le gana a casi todo | Sí, es para lo que está hecho | Más adelante, con velas diarias | No con este capital |
| Plataforma | Binance (Stocks o bStocks) | FP Markets (cTrader/MT5) | Binance | Ninguna confirmada para Venezuela |

### ¿Por qué no futuros?

Un contrato micro del S&P 500 (MES) mueve $5 por punto. El índice se mueve 50–100 puntos en un
día normal, o sea $250–500 por contrato en un día. Con $500 eso es apalancarse a todo o nada. El
mínimo razonable ronda los $5000. Además, no encontré un broker de futuros confirmado para
residentes de Venezuela. **No dan "mejor rendimiento": dan el mismo con más riesgo.**

### ¿Por qué el ETF sí?

El rendimiento de largo plazo de la bolsa es la ventaja más confiable que tiene un inversor
pequeño, y no requiere adivinar nada. El bot de forex todavía tiene que demostrar que tiene
ventaja. El ETF ya lo demostró durante 100 años, aunque con años muy malos. Como referencia, el
10 % anual de $500 son $50 al año, no $200 al mes.

## Qué ETF comprar: S&P 500 + una porción de tecnología

Me pediste incluir VOO, VGT y SMH además del S&P 500. Así queda:

| ETF | Qué es | Comentario |
|---|---|---|
| **SPY** (en Binance: **SPYB**) | S&P 500: las 500 empresas más grandes de EE. UU. | **El núcleo.** Ya lo encontraste en Binance |
| **VOO** | **El mismo S&P 500** que SPY, de otra gestora (Vanguard, gasto 0,03 % vs 0,09 %) | No hace falta tener los dos: es duplicar lo mismo. Compra el que esté disponible; en Binance ese es SPYB |
| **VGT** | Tecnología de EE. UU. (~300 empresas: Apple, Microsoft, NVIDIA…) | Más crecimiento, más caídas (−30 % en 2022) |
| **SMH** | Solo semiconductores (~25 empresas: NVIDIA, TSMC, Broadcom…) | El más volátil de los cuatro; puede caer −40 % en un mal año |

VGT y SMH comparten muchas de sus mayores posiciones (NVIDIA, Broadcom). Además, el S&P 500 ya
tiene ~30 % en tecnología. Tener los tres es apostar triple a lo mismo.

**Reparto sugerido para empezar:**

| Opción | SPYB (S&P 500) | Tecnología | Para quién |
|---|---|---|---|
| Prudente | 80 % | 20 % VGT | Si una caída de −25 % te haría vender |
| **Equilibrada (recomendada)** | **70 %** | **30 % (VGT o SMH, uno solo)** | Aguantas caídas fuertes sin tocar nada |
| Agresiva | 60 % | 20 % VGT + 20 % SMH | Solo si entiendes que en 2022 esto cayó −35 % o más |

### Calculadora de compra mensual

En Windows: **doble clic en `scripts\compra_mensual.bat`**. Te pregunta:
- cuánto vas a invertir;
- cuántas unidades tienes de SPYB y SMHB (las ves en Binance → Activos);
- los precios actuales.

Te responde cuánto comprar de cada uno, en USDT, para mantener el 70/30 **sin vender nada**. No
se conecta a tu cuenta ni compra por ti.

## Lo que averigüé de los bStocks de Binance

Tus capturas muestran **SPYB/USDT** en *TradFi → Spot → bStocks*. Esto es lo que encontré
sobre los 5 puntos que te pedí revisar:

| Punto | Respuesta |
|---|---|
| ¿Qué compras? | Un **token** respaldado 1:1 por la acción real, en custodia de un tercero. Tienes la exposición al precio y los dividendos, no la acción a tu nombre [1][2] |
| Comisión | No encontré la de SPYB. Revísala en la pantalla de compra (en spot de Binance suele ser ~0,1 %). Convertir acciones a bStocks y al revés no tiene comisión [3] |
| Spread fuera de horario | Se negocia 24/7. **Compra en horario de la bolsa de EE. UU.** (9:30–16:00 de Nueva York, que es 9:30–16:00 en Venezuela mientras EE. UU. tiene horario de verano) |
| Dividendos | Se **reinvierten** como más tokens en tu billetera spot. SPYB pagó $1,88 por acción en la última distribución [4]. Se descuenta la retención de EE. UU. para no residentes (en general 30 %) |
| Venta y retiro | Vendes SPYB por USDT en el mismo mercado spot. Retirar el token a otra billetera cobra comisión de red |

**Lo que NO debes tocar en esa pantalla:**
- **El botón "5x"**: es margen (comprar con dinero prestado). Para un ETF de largo plazo, nunca.
- **SOXLB y KORUB**: son ETF **apalancados 3x**. Pierden valor con el tiempo cuando el mercado se mueve de lado. Sirven para especular días, no para tener años.
- **SPYUSDT "Perp"** (en Futuros): es un contrato perpetuo con apalancamiento y comisión de financiamiento. No es comprar el ETF.

### Qué hay en Binance (confirmado por ti)

- **SPYB** (S&P 500) y **SMHB** (semiconductores): **sí están**, en *TradFi → Spot → bStocks*.
- **VGT y VOO: no están.** VOO da igual porque es lo mismo que SPYB. VGT se reemplaza por SMHB.

**Decisión: todo en Binance, 70 % SPYB + 30 % SMHB.** Una sola plataforma, sin Quantfury.

## Plan por etapas

| Etapa | Duración | ETF (Binance) | Bot forex (FP Markets) |
|---|---|---|---|
| Ahora: Fase 1–2 | 3–4 meses | Tus $500 con DCA (p. ej. $125 al mes por 4 meses), 70/30 | **Cuenta demo**, $0 reales |
| Fase 3 | 2 meses | Sigue igual + aportes mensuales | $500 **nuevos**, riesgo 0,5 % |
| Fase 4 | Indefinida | ~60–70 % del total | ~30–40 % del total, riesgo 1 % |

La regla de oro: el bot nunca recibe dinero del ETF para "recuperar" pérdidas.

## Fuentes

1. [Binance Academy — qué son los bStocks](https://www.binance.com/en/academy/articles/what-are-bstocks-a-guide-to-tokenized-stocks-on-binance)
2. [Morningstar / PR Newswire — lanzamiento de bStocks (respaldo 1:1, ADGM)](https://www.morningstar.com/news/pr-newswire/20260612cn82369/binance-exchange-launches-bstocks-tokenized-securities-11-backing-and-247-trading)
3. [crypto.news — conversión de acciones a bStocks sin comisión](https://crypto.news/binance-now-lets-users-turn-stocks-into-on-chain-tokens/)
4. [Crypto Briefing — dividendo de SPYB a billeteras spot](https://cryptobriefing.com/binance-spyb-dividend-distribution/)
5. [Yahoo Finance — Binance agrega 10 bStocks más](https://finance.yahoo.com/markets/crypto/articles/binance-adds-10-more-tokenized-072709446.html)
6. [BrokerChooser — comisiones de Quantfury](https://brokerchooser.com/broker-reviews/quantfury-review/quantfury-fees) · [InvestingBrokers — Quantfury](https://investingbrokers.com/quantfury-review/)
7. [Fortune — Binance agrega acciones de EE. UU.](https://fortune.com/2026/06/01/binance-adds-u-s-stocks-in-super-app-push-plans-to-launch-tokenized-shares/)
