# Dónde operar desde Venezuela, cómo meter el dinero y dónde correr el bot

Investigado el 12-oct-2026. Las condiciones para Venezuela cambian seguido y casi todas las
fuentes son sitios de comparación, no páginas oficiales de los brokers. **Antes de depositar,
confírmalo en el formulario de registro del broker** (el desplegable de países) o con su soporte.

## 1. Brokers de forex

| Broker | ¿Acepta Venezuela? | Plataformas útiles para el bot | Nota |
|---|---|---|---|
| **FP Markets** (ya tienes cuentas) | **Sí.** Tienes una cuenta real y una demo en el servidor `FPMarketsSC` (la entidad de Seychelles, la que atiende a Latinoamérica) | MT5 y **cTrader** | El elegido. Para el bot: cTrader Raw o MT5 |
| Exness | Probable, según sitios afiliados [3] | MT5 | Tiene cuenta **Standard Cent**: con $500 deja usar lotes muy chicos |
| XM, IC Markets, Tickmill, RoboForex | Aparecen como aceptados en comparadores [4][5] | MT5, algunos cTrader | Alternativas si FP Markets falla |
| Interactive Brokers | **No.** IBKR respondió en ene y feb de 2026 que no da servicio a residentes de Venezuela [6] | — | Descartado por ahora |
| Quantfury | Sí, pero es solo una app móvil y no encontré API pública | — | **No sirve para un bot** |
| Binance | Sí (lo usas para P2P) | No tiene forex | Sirve como **puente para fondear** con USDT y para el **ETF del S&P 500** (Stocks o bStocks como SPYB, que te aparecen disponibles). Ver [MERCADOS.md](MERCADOS.md) [7] |

**Recomendación:** FP Markets con una cuenta **cTrader Raw**. Hay dos razones:
- La [cTrader Open API](https://spotware.com/ctrader/dev-resources/open-api) es gratuita y
  funciona desde Python en Linux. MetaTrader 5 con Python exige Windows (VPS más caro).
- Ya tienes la cuenta abierta, así que solo te falta confirmar que esté verificada y que acepte
  depósitos desde Venezuela.

Mientras tanto, la **cuenta demo** de FP Markets sirve para la Fase 2 sin arriesgar nada. El
script `scripts/descargar_datos_mt5.py` usa la demo de MT5 para bajar el histórico.

Preguntas para el soporte de FP Markets antes de depositar:
1. ¿Puedo operar y **retirar** siendo residente en Venezuela, con pasaporte venezolano?
2. ¿Aceptan depósitos en USDT (red TRC20) y transferencias desde Towerbank (Panamá)? ¿Qué cuesta cada uno?
3. ¿El retiro sale por el mismo método? ¿Hay mínimo de retiro?
4. ¿Permiten trading automatizado vía cTrader Open API en la cuenta Raw?
5. ¿Ofrecen VPS gratis, y con qué saldo o volumen?

### Mensaje para el soporte de FP Markets (listo para pegar en su chat)

> Hola. Soy residente en Venezuela, con pasaporte venezolano, y tengo cuentas MT5 y cTrader con
> ustedes (entidad FP Markets SC). Antes de depositar quiero confirmar cinco cosas:
> 1. ¿Puedo operar y RETIRAR fondos sin restricciones siendo residente en Venezuela?
> 2. ¿Aceptan depósitos en USDT por la red TRC20 y transferencias desde Towerbank (Panamá)? ¿Qué comisión tiene cada uno?
> 3. ¿Los retiros salen por el mismo método del depósito? ¿Hay monto mínimo de retiro o comisión?
> 4. ¿Está permitido el trading automatizado mediante la cTrader Open API en una cuenta Raw?
> 5. ¿Ofrecen VPS gratuito? ¿Con qué saldo o volumen mensual?
> Gracias.

Guarda las respuestas (captura o correo). Si la 1 o la 4 es "no", avísame antes de depositar.

### ¿Tengo que abrir una cuenta cTrader?

**Ahora no.** Tu MT5 Raw (real) y tu MT5 demo bastan para la Fase 1 (descargar datos y
validar) y para la Fase 2 en demo, corriendo en tu PC.

cTrader importa recién para el dinero real, por el costo del servidor:

| | MT5 | cTrader |
|---|---|---|
| Conexión desde Python | Solo Windows | Cualquier sistema (Open API) |
| Servidor 24/5 | VPS Windows: ~$15–25/mes | VPS Linux: ~$5/mes |
| Con $500 al 2 % mensual ($10) | El VPS se come toda la ganancia | Queda margen |

**¿Hay que instalar el programa de cTrader?** No. El bot se conecta directo por la Open API, sin
el programa. Para mirar tu cuenta basta el **WebTrader** (en el navegador) o la app del celular.
Instala la versión de escritorio solo si te resulta más cómoda.

Para la Fase 2 hará falta un paso único: registrar una "aplicación" en el portal de la Open API
de cTrader (con tu cTrader ID) para obtener las credenciales del bot. Te guiaré cuando
lleguemos ahí. **Nunca compartas tu contraseña**: el bot usa un permiso (token) que puedes
revocar cuando quieras.

Abrir una **demo de cTrader** es gratis y no compromete nada. Si quieres adelantarte, en
*Add New Account* elige **Demo Account → cTrader → Account Type: Raw → USD → 1:30**. Así la
Fase 2 se puede programar directo contra cTrader. La cuenta cTrader real se abre recién en la
Fase 3.

### Apalancamiento: usa 1:30, no 1:5 ni 1:500

El apalancamiento **no** define cuánto arriesgas: eso lo fija el stop (1 % por operación).
Solo define cuánto margen retiene el broker. Con tu MT5 real en **1:5**:

- 0,01 lotes de EURUSD retienen ~$217 de margen.
- Con $500, como mucho cabe una posición de 0,02 lotes.
- Las señales con stop corto (que piden más lotes) se achican o no entran.

**1:30** (el máximo para minoristas en Europa en pares mayores) da margen de sobra para las
reglas del bot y sigue siendo prudente. 1:500 no le da nada al bot y facilita un error manual
grande. El laboratorio simula el margen (`--apalancamiento 30`) y el what-if muestra qué pasa
con 1:5.

Tu cuenta MT5 real tiene $50,10 y la de TradingView $1,50: déjalas quietas. El bot no usa ninguna
cuenta real hasta la Fase 3.

## 2. Prop firms (cuentas fondeadas)

FTMO, The5ers y FundedNext aparecen con **Venezuela restringida** en los listados que
consulté [8][9][10]. Esa vía está prácticamente cerrada ahora. Si en el futuro aparece una que
acepte Venezuela y permita bots, el mismo laboratorio sirve para simular sus reglas antes de pagar
el examen (por ejemplo, −5 % diario y −10 % total).

## 3. Cómo meter el dinero

| Vía | Costo aproximado | Comentario |
|---|---|---|
| USDT por Binance P2P → broker (red TRC20) | Comisión de red de ~$1 más el diferencial P2P | La más práctica para $500. Guarda los comprobantes |
| Transferencia desde Towerbank | Suele costar entre $20 y $50 por envío internacional (confírmalo con el banco) | Con $500, eso es el 4–10 % del capital solo en entrar |

El producto de inversión de Towerbank pide desde $10.000, así que no aplica por ahora.

## 4. ¿Forex, un ETF o acciones?

Son cosas distintas y se pueden combinar:

- **Un ETF del S&P 500 o del mundo** ha dado cerca de 10 % anual en el largo plazo, sin trabajo y
  sin bot. Pero hay años de −20 % o peor. La vía es Binance (Stocks o bStocks). Antes de comprar,
  revisa los 5 puntos de [MERCADOS.md](MERCADOS.md).
- **El bot de forex** busca 1–3 % al mes, con más riesgo y más trabajo. Hasta que pase la Fase 2
  (demo), no necesita dinero real.

Plan sugerido (detalle en [MERCADOS.md](MERCADOS.md)):
1. Mientras el bot está en Fase 1 y Fase 2 (3–4 meses, en demo), tus $500 van al ETF en Binance
   con compras graduales.
2. Si el bot aprueba la demo, fondeas FP Markets con $500 nuevos (no los del ETF).

### Ojo con el capital chico

Con $500 y 1 % de riesgo arriesgas $5 por operación. Con un lote mínimo de 0,01, un pip de
EURUSD vale $0,10. Un stop de 50 pips (lo normal en H4) cuesta $5 más comisión, o sea, ya pasas
el 1 %. En la primera prueba con datos de muestra, el bot **descartó 14 de 19 señales** por eso.

**Ya está resuelto en el bot:** si el lote mínimo arriesga como mucho 1,5 % (`--riesgo-tope`),
el bot lo usa y lo marca en el reporte; si arriesga más, descarta la señal. Además, la temporalidad
por defecto pasó a H1. Con los mismos datos, en H4 se descartan 3 señales (antes 14) y en H1
ninguna. El Monte Carlo usa el riesgo efectivo promedio, no el 1 % nominal.

Otras salidas, si hicieran falta:
- Empezar en real con $1000.
- Usar una cuenta cent (Exness Standard Cent u otra), que permite lotes más chicos.
- Arriesgar 2 %. **No recomendado.**

El laboratorio te muestra cuántas señales se pierden en cada caso.

## 5. Dónde correr el bot

En tu casa no, por los cortes de luz y de internet.

| Fase | Dónde | Costo |
|---|---|---|
| 1 – Backtest | Tu PC | $0 |
| 2 – Demo | Tu PC, o un VPS Linux básico (Hetzner, Contabo, DigitalOcean, Oracle Free Tier) | $0–6/mes |
| 3–4 – Real | VPS Linux con cTrader Open API | ~$5–6/mes |
| (si usas MT5) | VPS Windows (o el del broker si lo regala) | ~$15–25/mes |

**Regla de costos:** el VPS, la API de IA y los datos se descuentan de la ganancia en los
reportes. Con $500 al 2 % mensual ganas $10. Si la infraestructura cuesta $25, pierdes dinero.
Por eso el bot tiene un presupuesto (ver `PROMPT_MAESTRO.md`): la IA solo se llama cuando hay
una señal, más dos resúmenes al día, con un modelo barato. Si los costos superan el 30 % de la
ganancia promedio de los últimos 3 meses, se recortan solos.

## Fuentes

1. [comparebroker.io — FP Markets en Venezuela](https://comparebroker.io/brokers/is-fp-markets-legal-in-venezuela)
2. [Traders Union — países de FP Markets](https://tradersunion.com/brokers/forex/view/fp-markets/available-countries/) · [TradingBeasts](https://tradingbeasts.com/fp-markets-list-of-supported-banned-countries/)
3. [Finantres — Exness en Venezuela](https://finantres.com/exness-venezuela/?hub_page=9) · [Daytrading.com — Exness](https://www.daytrading.com/exness)
4. [FXLeaders — brokers en Venezuela](https://www.fxleaders.com/forex-brokers/forex-brokers-by-country/forex-brokers-venezuela/) (tabla de 2024)
5. [Traders Union — brokers en Venezuela](https://tradersunion.com/best-forex-brokers/in-venezuela/) · [ForexSuggest](https://forexsuggest.com/forex-brokers-venezuela/)
6. [IBKR Campus — respuestas sobre Venezuela](https://www.interactivebrokers.com/campus/trading-lessons/abrir-una-cuenta-depositar-y-retirar/)
7. [Fortune — Binance agrega acciones de EE. UU.](https://fortune.com/2026/06/01/binance-adds-u-s-stocks-in-super-app-push-plans-to-launch-tokenized-shares/) · [PR Newswire — bStocks](https://www.prnewswire.com/news-releases/binance-launches-us-stocks-trading-and-previews-bstocks-tokenized-securities-302787226.html)
8. [FundingTraders — países prohibidos por FTMO](https://fundingtraders.com/blog/ftmo-banned-countries-list/)
9. [PropFirmMatch — restricciones para Venezuela](https://propfirmmatch.com/prop-firm-lists/restricted-countries/venezuela)
10. [Chart Nomads — prop firms restringidas en Venezuela](https://chartnomads.com/prop-firm-lists/prop-firms-restricted-in-venezuela)
