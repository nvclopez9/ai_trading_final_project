# Riesgo en la inversión

En finanzas, **riesgo** no es exactamente lo que la intuición sugiere. No es "la probabilidad de que pase algo malo", sino la **variabilidad** de los resultados posibles. Un activo cuyo precio se mueve mucho es más arriesgado que otro que apenas fluctúa, aunque ambos acaben teniendo la misma rentabilidad media.

## Tipos de riesgo

### Riesgo sistemático (o de mercado)

Afecta a todos los activos de una clase, y no se puede eliminar diversificando dentro de ella. Incluye:

- Riesgo macroeconómico (recesiones, inflación, tipos de interés).
- Riesgo geopolítico (guerras, sanciones).
- Riesgo regulatorio general.

### Riesgo específico (o idiosincrático)

Afecta a una empresa, sector o país concreto. Diversificando se reduce mucho: un fraude en una empresa afecta poco a una cartera con cientos de valores.

### Riesgo de liquidez

Imposibilidad de vender un activo rápidamente sin incurrir en una fuerte pérdida de precio. Afecta especialmente a:

- Valores poco negociados.
- Algunos bonos corporativos.
- Activos alternativos (arte, vivienda, private equity).

### Riesgo de crédito

Probabilidad de que el emisor de un bono no pague. Se mide con ratings (AAA, AA, BBB, BB...); por debajo de BBB- se considera **high yield** o bono "basura".

### Riesgo de divisa

Si inviertes en activos denominados en otra moneda (dólares, yenes), los movimientos del tipo de cambio afectan tu rentabilidad en euros, positiva o negativamente.

### Riesgo de inflación

El valor real del dinero baja con el tiempo si la rentabilidad no supera la inflación. Un depósito al 1 % con inflación al 4 % es, en términos reales, un activo que pierde poder adquisitivo.

## Volatilidad

La **volatilidad** es la medida estadística más usada para cuantificar el riesgo. Se calcula como la desviación típica de los retornos del activo, normalmente anualizada.

Referencias orientativas:

- Letras del tesoro: ~0-2 %.
- Bonos gobierno largo plazo: ~5-8 %.
- Acciones desarrollados (S&P 500, MSCI World): ~15-20 %.
- Acciones emergentes: ~20-25 %.
- Criptoactivos: ~60-90 %+.

Una volatilidad del 20 % significa, muy aproximadamente, que dos tercios de los años la rentabilidad cae en el rango [media − 20 %, media + 20 %] (suponiendo distribución normal, que no es exactamente el caso en finanzas).

## Drawdown

El **drawdown** es la caída desde un máximo previo hasta un mínimo posterior, expresada en porcentaje. El **máximo drawdown** es la mayor caída histórica sufrida.

**Ejemplo**: si un índice sube hasta 100, cae a 60, y luego vuelve a 80, el drawdown en el punto bajo fue del 40 %.

Referencias históricas (máximos drawdowns aproximados):

- S&P 500 en la Gran Depresión (1929-1932): ~-85 %.
- S&P 500 en la crisis financiera 2008-2009: ~-55 %.
- MSCI World en el COVID (marzo 2020): ~-35 %.

Cualquier inversor debe preguntarse: ¿aguantaría psicológicamente una caída así? Si la respuesta es "no", el peso en renta variable probablemente es demasiado alto.

## Ratio de Sharpe

El **ratio de Sharpe** mide la rentabilidad adicional que obtiene un activo sobre el activo libre de riesgo, por cada unidad de riesgo (volatilidad) asumido.

Fórmula:

```
Sharpe = (Rentabilidad cartera - Rentabilidad libre de riesgo) / Volatilidad cartera
```

**Ejemplo**: cartera con rentabilidad del 10 %, activo libre de riesgo al 3 %, volatilidad del 14 %. Sharpe = (10 − 3) / 14 ≈ 0,5.

Interpretación intuitiva:

- Sharpe < 0,5: poca eficiencia en relación al riesgo.
- 0,5-1: razonable.
- > 1: buena rentabilidad ajustada al riesgo (poco sostenible a largo plazo para la mayoría).
- Valores muy altos (>2 sostenidos) son raros o sospechosos.

## VaR (Value at Risk) — noción básica

El **VaR** estima la pérdida máxima esperada en un horizonte y con una probabilidad dada.

**Ejemplo**: VaR del 95 % a 1 día = -3 % significa que, con un 95 % de confianza, en un día cualquiera la cartera no perderá más del 3 %. Implícitamente, existe un 5 % de probabilidad de superar esa pérdida.

Es útil para tener una referencia cuantitativa de riesgo, pero tiene limitaciones: asume distribuciones estadísticas que no reflejan bien los eventos extremos ("cisnes negros"). En crisis reales las pérdidas superan el VaR con más frecuencia de la que el modelo predice.

## Horizonte temporal y riesgo

Un punto clave: el **riesgo cambia con el horizonte**. Las acciones son volátiles año a año, pero en periodos de 20-30 años su rango de rentabilidades se estrecha mucho y su rentabilidad media real (ajustada a inflación) ha sido históricamente del orden del 5-7 %.

Para horizontes muy cortos (menos de 3 años), la renta variable es demasiado arriesgada para dinero que se va a necesitar; la liquidez y la renta fija corta son más adecuadas.

## Gestión práctica del riesgo

Algunas ideas concretas:

- **Fondo de emergencia** en efectivo (3-6 meses de gastos) antes de invertir.
- **Diversificar** entre clases de activos y geografías.
- **Asignación acorde al horizonte y a la tolerancia** real a pérdidas, no a la declarada.
- **No apalancarse** (invertir con dinero prestado) si no se entiende profundamente el riesgo.
- **Revisar la cartera** periódicamente, pero no cada día.

El mayor riesgo para el inversor medio no suele ser el mercado: es su propio comportamiento ante el mercado.

---

*Este contenido es informativo y educativo, no constituye asesoramiento financiero.*
