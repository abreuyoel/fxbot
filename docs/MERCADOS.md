# ¿Forex, futuros, acciones o ETF? Dónde poner cada dólar

**Resumen:** con $500–1000, la combinación que más sentido tiene es:

- **Un núcleo pasivo en un ETF del S&P 500**, en Binance. El bot no lo opera.
- **Un satélite activo en forex** con el bot, en FP Markets. Solo con dinero real después de aprobar la demo.

Los futuros quedan fuera por ahora. Quantfury sobra como tercera plataforma.

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

## Binance: Stocks vs. bStocks

Binance tiene dos productos distintos:

1. **"Stocks" (desde junio de 2026):** más de 7000 acciones y ETF de EE. UU., como SPY o VOO.
2. **bStocks:** tokens respaldados 1:1, por ejemplo **SPYB**, que sigue al SPY. Se emiten bajo un
   prospecto aprobado en Abu Dhabi (ADGM) y solo están disponibles en jurisdicciones permitidas.
   Hay otras versiones tokenizadas, como SPYX de xStocks.

Me dices que en tu app aparecen, así que están disponibles para tu cuenta. Antes de comprar,
revisa estos 5 puntos en la propia app:

- Qué compras exactamente: ¿la acción real a tu nombre (vía un broker asociado) o un token? Con
  un token, tu derecho es contra el emisor y el custodio, no contra la bolsa.
- La comisión por compra y venta, y el spread fuera del horario de la bolsa (bStocks se negocia
  24/7, pero fuera de horario el precio puede alejarse del real).
- Si hay comisión anual de custodia, más el gasto del propio ETF (SPY 0,09 %, VOO 0,03 %).
- Si los dividendos se pagan o se reinvierten.
- Cómo se vende y se retira a USDT.

**Cómo comprar:** una compra mensual fija (DCA), por ejemplo $50 al mes, sin intentar adivinar
el momento. Si en algún momento el bot opera esto, sería solo para rebalancear, no para
especular.

## Quantfury

Es solo una app móvil, sin API para bots, así que no sirve para automatizar. Para un ETF pasivo
no aporta nada que Binance no tenga, y una tercera plataforma es una cuenta más que vigilar, con
su propio riesgo de custodia. Si en el futuro manejas más de ~$5000, repartir la custodia entre
plataformas sí tiene sentido.

## Plan por etapas

| Etapa | Duración | ETF (Binance) | Bot forex (FP Markets) |
|---|---|---|---|
| Ahora: Fase 1–2 | 3–4 meses | Tus $500, con compras graduales | **Cuenta demo**, $0 reales |
| Fase 3 | 2 meses | Sigue igual + aportes mensuales | $500 **nuevos**, riesgo 0,5 % |
| Fase 4 | Indefinida | ~60–70 % del total | ~30–40 % del total, riesgo 1 % |

La regla de oro: el bot nunca recibe dinero del ETF para "recuperar" pérdidas.

## Fuentes

- [Binance Academy — qué son los bStocks](https://www.binance.com/en/academy/articles/what-are-bstocks-a-guide-to-tokenized-stocks-on-binance)
- [PR Newswire — lanzamiento de bStocks (respaldo 1:1, ADGM)](https://www.prnewswire.com/news-releases/binance-exchange-launches-bstocks-tokenized-securities-11-backing-and-247-trading-302798876.html)
- [Fortune — Binance agrega acciones de EE. UU.](https://fortune.com/2026/06/01/binance-adds-u-s-stocks-in-super-app-push-plans-to-launch-tokenized-shares/)
- [Binance en X — jurisdicciones restringidas del producto TradFi](https://x.com/binance/status/2079901513757987313)
- [BrokerChooser — comisiones de Quantfury](https://brokerchooser.com/broker-reviews/quantfury-review/quantfury-fees)
