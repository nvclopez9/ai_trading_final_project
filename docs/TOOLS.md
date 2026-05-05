# Herramientas del Agente de IA

El agente dispone de **19 herramientas** organizadas en 5 categorías. Cada herramienta es una función Python decorada con `@tool` de LangChain — el LLM lee su nombre y descripción para decidir cuándo invocarla, y LangChain ejecuta la función real y devuelve el resultado al LLM como observación.

Todas las herramientas devuelven `str` (no dict/JSON) para maximizar la fiabilidad del tool-calling con modelos de tamaño medio.

---

## Categoría 1 — Datos de Mercado

### `get_ticker_status`
**Cuándo la usa el agente:** cuando el usuario pregunta por el precio actual, el estado o la variación diaria de una acción concreta.

**Ejemplo de pregunta:** *"¿Cómo está Apple hoy?"*, *"¿Cuánto vale NVDA?"*

**Parámetros:**
| Parámetro | Tipo | Descripción |
|---|---|---|
| `ticker` | str | Símbolo bursátil (ej: `AAPL`, `MSFT`, `TSLA`) |

**Qué devuelve:** precio actual, variación diaria (%), P/E ratio, capitalización de mercado y nombre de la empresa.

**Fuente:** Yahoo Finance (yfinance)

---

### `get_ticker_history`
**Cuándo la usa el agente:** cuando el usuario pregunta por la evolución histórica de un ticker en un periodo concreto.

**Ejemplo de pregunta:** *"¿Cómo ha evolucionado Tesla en los últimos 3 meses?"*, *"Muéstrame el histórico de AAPL del último año"*

**Parámetros:**
| Parámetro | Tipo | Valor por defecto | Descripción |
|---|---|---|---|
| `ticker` | str | — | Símbolo bursátil |
| `period` | str | `1mo` | Periodo: `5d`, `1mo`, `3mo`, `6mo`, `1y`, `5y` |

**Qué devuelve:** precio máximo, mínimo, último cierre y variación total del periodo.

---

### `get_hot_tickers`
**Cuándo la usa el agente:** cuando el usuario pregunta por el estado general del mercado, las mayores subidas/bajadas del día, o los tickers más activos.

**Ejemplo de pregunta:** *"¿Qué tickers están subiendo más hoy?"*, *"Dame los 10 más activos del mercado"*

**Parámetros:**
| Parámetro | Tipo | Valor por defecto | Descripción |
|---|---|---|---|
| `category` | str | `gainers` | `gainers` (mayor subida %), `losers` (mayor bajada %), `actives` (mayor volumen) |

**Qué devuelve:** lista de los 10 tickers principales de la categoría con precio, variación y volumen.

---

### `get_ticker_news`
**Cuándo la usa el agente:** cuando el usuario pide noticias, titulares o novedades recientes de una empresa.

**Ejemplo de pregunta:** *"¿Qué noticias hay sobre Microsoft?"*, *"Titulares recientes de NVDA"*

**Parámetros:**
| Parámetro | Tipo | Valor por defecto | Descripción |
|---|---|---|---|
| `ticker` | str | — | Símbolo bursátil |
| `limit` | int | `5` | Número de noticias (1–10) |

**Qué devuelve:** lista de noticias con titular, fecha, fuente y enlace.

---

### `search_ticker`
**Cuándo la usa el agente:** cuando el usuario escribe el nombre de una empresa (no el símbolo) o un símbolo parcial/incorrecto.

**Ejemplo de pregunta:** *"¿Cuál es el ticker de Santander?"*, *"Busca el símbolo de LVMH"*, *"ticker de Adidas"*

**Parámetros:**
| Parámetro | Tipo | Descripción |
|---|---|---|
| `query` | str | Nombre de empresa o símbolo aproximado (ej: `"banco santander"`, `"Apple"`) |

**Qué devuelve:** lista de tickers coincidentes con nombre completo, símbolo y mercado.

---

### `analyze_news_article`
**Cuándo la usa el agente:** cuando el usuario pide analizar el impacto de una noticia específica sobre un ticker.

**Ejemplo de pregunta:** *"Analiza esta noticia sobre Tesla: [titular]"*, *"¿Qué implica para AAPL que [noticia]?"*

**Parámetros:**
| Parámetro | Tipo | Descripción |
|---|---|---|
| `ticker` | str | Símbolo relacionado con la noticia |
| `title` | str | Titular de la noticia |
| `source` | str | Fuente periodística (opcional) |
| `url` | str | Enlace a la noticia (opcional) |

**Qué devuelve:** contexto de mercado del ticker (precio, variación, tendencia 3M, market cap, P/E) para que el agente redacte el análisis de impacto.

---

## Categoría 2 — Análisis Fundamental

### `compare_tickers`
**Cuándo la usa el agente:** cuando el usuario quiere comparar dos o más acciones entre sí.

**Ejemplo de pregunta:** *"Compara AAPL vs MSFT vs GOOGL"*, *"¿Cuál es mejor, Amazon o Meta?"*

**Parámetros:**
| Parámetro | Tipo | Descripción |
|---|---|---|
| `tickers` | list[str] | Lista de 2 a 6 tickers (ej: `["AAPL", "MSFT", "NVDA"]`) |

**Qué devuelve:** tabla comparativa con precio actual, cambio diario, P/E, capitalización, dividendo, beta, 52-week high/low y retorno YTD.

---

### `get_fundamentals`
**Cuándo la usa el agente:** cuando el usuario pide ratios financieros detallados o quiere evaluar la salud financiera de una empresa.

**Ejemplo de pregunta:** *"Fundamentales de Tesla"*, *"¿Cómo está financieramente AAPL?"*, *"P/E y ROE de NVDA"*

**Parámetros:**
| Parámetro | Tipo | Descripción |
|---|---|---|
| `ticker` | str | Símbolo bursátil |

**Qué devuelve:** ratios agrupados en 4 bloques:
- **Valoración:** P/E, P/B, P/S, P/FCF
- **Rentabilidad:** ROE, ROA, margen bruto/operativo/neto, dividendo, payout ratio
- **Solidez:** Deuda/Equity, Current Ratio, Free Cash Flow
- **Mercado:** Market Cap, Beta, 52-week high/low, EPS

---

## Categoría 3 — Base de Conocimiento (RAG)

### `search_finance_knowledge`
**Cuándo la usa el agente:** cuando el usuario pregunta sobre conceptos financieros, glosario, estrategias de inversión, análisis técnico o educación bursátil. También cuando el agente quiere fundamentar una recomendación con doctrina establecida.

**Ejemplo de pregunta:** *"¿Qué es el P/E ratio?"*, *"Explícame la estrategia value investing"*, *"¿Qué es el análisis técnico?"*

**Parámetros:**
| Parámetro | Tipo | Descripción |
|---|---|---|
| `query` | str | Pregunta o concepto en lenguaje natural |

**Qué devuelve:** los 4 fragmentos más relevantes de los PDFs indexados, con el nombre del documento fuente. El agente cita la fuente en su respuesta.

**Cómo funciona internamente:**
1. Se genera el embedding del `query` con `mxbai-embed-large` (Ollama)
2. Se hace `similarity_search(k=4)` en ChromaDB
3. Se devuelven los fragmentos con metadata (nombre del PDF y página)

> Requiere haber ejecutado `python -m backend.rag.ingest` previamente con los PDFs en `data/rag_docs/`.

---

## Categoría 4 — Gestión de Cartera

Todas estas herramientas operan sobre la **cartera activa** del usuario (la seleccionada en la UI).

### `portfolio_view`
**Cuándo la usa el agente:** cuando el usuario pregunta por el estado de su cartera, sus posiciones, el efectivo disponible, el P&L o el patrimonio total. El agente también la usa automáticamente antes de hacer análisis.

**Ejemplo de pregunta:** *"¿Cómo está mi cartera?"*, *"¿Cuánto dinero tengo disponible?"*, *"¿Cuánto llevo ganado?"*

**Parámetros:** ninguno

**Qué devuelve:** efectivo disponible, lista de posiciones (ticker, cantidad, precio medio, precio actual, valor de mercado, P&L), valor total invertido y patrimonio total (cash + posiciones).

---

### `portfolio_buy`
**Cuándo la usa el agente:** cuando el usuario ordena comprar una cantidad concreta de acciones, o cuando ejecuta una propuesta de `analyze_buy_opportunities` aprobada.

**Ejemplo de pregunta:** *"Compra 10 acciones de AAPL"*, *"Adquiere 5 NVDA"*

**Parámetros:**
| Parámetro | Tipo | Descripción |
|---|---|---|
| `ticker` | str | Símbolo a comprar |
| `qty` | float | Cantidad de acciones |

**Comportamiento:** compra al precio actual de Yahoo Finance. Valida que haya suficiente cash. Detecta duplicados recientes (misma operación en <30s) y avisa antes de reintentar.

**Qué devuelve (formato estructurado):**
```
✅ Compra ejecutada (cartera #N · Nombre)
  Ticker:          NVDA (10 acciones)
  Precio mercado:  $198.48 / acción
  Total pagado:    $1,984.80
  Posición total:  10 acc. @ avg $198.48
  Efectivo rest.:  $109.51
```

---

### `portfolio_buy_all_cash`
**Cuándo la usa el agente:** cuando el usuario dice *"compra con todo el capital"*, *"invierte todo el efectivo en X"*, *"usa el resto del dinero"*. Evita el problema de tener que calcular la cantidad manualmente.

**Ejemplo de pregunta:** *"Compra NVDA con todo el capital disponible"*, *"Invierte todo en Apple"*

**Parámetros:**
| Parámetro | Tipo | Descripción |
|---|---|---|
| `ticker` | str | Símbolo a comprar |

**Comportamiento:** internamente obtiene el efectivo disponible, el precio actual de Yahoo Finance y calcula `qty = floor(cash / precio)`. Ejecuta la compra en un solo paso.

**Qué devuelve (formato estructurado):**
```
✅ Compra con todo el capital (cartera #N · Nombre)
  Ticker:          NVDA (10 acciones)
  Precio mercado:  $198.48 / acción
  Total invertido: $1,984.80
  Posición total:  10 acc. @ avg $198.48
  Efectivo rest.:  $109.51
```

---

### `portfolio_sell`
**Cuándo la usa el agente:** cuando el usuario ordena vender acciones, o cuando ejecuta una propuesta de `analyze_sell_candidates` aprobada.

**Ejemplo de pregunta:** *"Vende 5 AAPL"*, *"Liquida mi posición en Tesla"*

**Parámetros:**
| Parámetro | Tipo | Descripción |
|---|---|---|
| `ticker` | str | Símbolo a vender |
| `qty` | float | Cantidad de acciones |

**Comportamiento:** valida que exista la posición y que la cantidad sea suficiente. Si no hay posición, devuelve un mensaje útil. El agente lo invoca directamente sin consultar primero.

**Qué devuelve:** confirmación con precio de venta, ingreso recibido, P&L realizado de la operación.

---

### `portfolio_transactions`
**Cuándo la usa el agente:** cuando el usuario pide el historial de operaciones de su cartera.

**Ejemplo de pregunta:** *"¿Qué operaciones he hecho?"*, *"Muéstrame las últimas compras"*

**Parámetros:**
| Parámetro | Tipo | Valor por defecto | Descripción |
|---|---|---|---|
| `limit` | int | `10` | Número de transacciones a mostrar |

**Qué devuelve:** lista de transacciones (fecha, ticker, lado buy/sell, cantidad, precio, total).

---

### `portfolio_list`
**Cuándo la usa el agente:** cuando el usuario pide ver todas sus carteras o comparar entre ellas.

**Ejemplo de pregunta:** *"¿Cuántas carteras tengo?"*, *"Lista mis carteras"*

**Parámetros:** ninguno

**Qué devuelve:** lista de carteras con id, nombre, cash, nivel de riesgo, mercados y número de posiciones.

---

### `portfolio_set_risk`
**Cuándo la usa el agente:** cuando el usuario quiere cambiar el perfil de riesgo de su cartera activa.

**Ejemplo de pregunta:** *"Pon mi cartera en agresivo"*, *"Cambia el riesgo a conservador"*

**Parámetros:**
| Parámetro | Tipo | Descripción |
|---|---|---|
| `risk` | str | `conservador`, `moderado` o `agresivo` |

**Efecto:** el perfil de riesgo afecta a `analyze_buy_opportunities` (nº de picks, diversificación) y `analyze_sell_candidates` (criterio de selección).

---

### `portfolio_set_markets`
**Cuándo la usa el agente:** cuando el usuario quiere cambiar los mercados objetivo de su cartera.

**Ejemplo de pregunta:** *"Quiero invertir solo en USA"*, *"Cambia los mercados a USA y Europa"*

**Parámetros:**
| Parámetro | Tipo | Descripción |
|---|---|---|
| `markets` | str | CSV de mercados: `USA`, `EUROPA`, `ASIA`, `GLOBAL`, `ALL` |

---

## Categoría 5 — Análisis y Asesoría

### `analyze_buy_opportunities`
**Cuándo la usa el agente:** cuando el usuario pide ideas de inversión, quiere invertir una cantidad o pide al agente que decida qué comprar. Es la herramienta central del flujo *"Analizar → Proponer → Ejecutar"*.

**Ejemplo de pregunta:** *"Propón un plan de inversión para este mes"*, *"¿Qué compro con 2000$?"*, *"Invierte la mitad de mi patrimonio a corto plazo"*

**Parámetros:**
| Parámetro | Tipo | Descripción |
|---|---|---|
| `pct_of_patrimony` | float\|null | % del patrimonio total a invertir (0–100). Se ignora si se pasa `amount_usd`. |
| `amount_usd` | float\|null | Cantidad fija en USD. Tiene prioridad. |
| `horizon` | str | `short` (días/semanas), `medium` (meses), `long` (año+) |
| `num_picks` | int\|null | Nº de tickers. Si null, se decide según el riesgo de la cartera. |
| `market_cap_tier` | str | `small` (<$2B), `mid` ($2–10B), `large` (>$10B), `any` |
| `asset_class` | str | `stock`, `etf`, `commodity`, `crypto`, `leveraged`, `all` |

**Qué devuelve:** análisis textual con la lógica + bloque **PROPUESTA EJECUTABLE** con líneas tipo `COMPRAR 8 NVDA`. El agente presenta la propuesta al usuario y, si la aprueba, ejecuta `portfolio_buy` por cada línea.

**Universo de tickers disponible:**
- Large caps: AAPL, MSFT, NVDA, GOOGL, AMZN, META, TSLA, AVGO, AMD...
- Mid caps: ROKU, COIN, RBLX, U, SNAP, DKNG...
- Small caps: PLTR, RIOT, SOFI, MARA, CLSK...
- ETFs: SPY, QQQ, VOO, VTI, ARKK, XLK, XLF, SCHD...
- Commodities: GLD, SLV, USO, UNG, DBC...
- Crypto-ETPs: IBIT, FBTC, BITO, ETHA...
- Apalancados (×3): TQQQ, SOXL, UPRO, BITX...

---

### `analyze_sell_candidates`
**Cuándo la usa el agente:** cuando el usuario quiere saber qué vender, cortar pérdidas o tomar beneficios de sus posiciones actuales.

**Ejemplo de pregunta:** *"¿Qué debería vender?"*, *"Corta mis pérdidas"*, *"Toma beneficios de las ganadoras"*

**Parámetros:**
| Parámetro | Tipo | Descripción |
|---|---|---|
| `target` | str | `losers` (peor P&L%), `gainers` (mejor P&L%), `underperformers` (solo negativos), `reduce_exposure` (las más grandes), `auto` (decide según riesgo) |
| `pct_of_invested` | float\|null | % del valor invertido a liquidar |
| `num_picks` | int\|null | Nº de posiciones a sugerir vender |

**Qué devuelve:** análisis + bloque **PROPUESTA EJECUTABLE** con líneas tipo `VENDER 3 AAPL`. Misma mecánica que `analyze_buy_opportunities`.

---

## Flujo Analizar → Proponer → Ejecutar

```
Usuario: "Invierte 2000$ en large caps"
    │
    ▼
Agente invoca analyze_buy_opportunities(amount_usd=2000, market_cap_tier='large')
    │
    ▼
Tool devuelve análisis + PROPUESTA:
  COMPRAR 4 NVDA (~$436)
  COMPRAR 2 AAPL (~$380)
  COMPRAR 3 MSFT (~$480)
    │
    ▼
Agente resume la propuesta y pregunta al usuario
    │
    ▼
Usuario: "Sí, ejecuta"
    │
    ▼
Agente llama portfolio_buy(NVDA, 4)
Agente llama portfolio_buy(AAPL, 2)
Agente llama portfolio_buy(MSFT, 3)
    │
    ▼
Agente llama portfolio_view() para mostrar estado final
```

---

## Reglas importantes del agente

1. **No inventa datos** — cualquier precio, ratio o cifra financiera DEBE venir de una tool. Prohibido fabricar números.
2. **Tools de solo lectura** se invocan directamente sin pedir permiso.
3. **Tools que mutan estado** (buy, sell, set_risk, set_markets) avisan antes de ejecutar pero lo hacen en el mismo turno — no esperan a un turno posterior.
4. **Compra con todo el capital** → usa `portfolio_buy_all_cash(ticker)`, no `portfolio_buy`. Calcula qty automáticamente.
5. **Productos apalancados y cripto-ETPs** incluyen una advertencia de riesgo antes de la primera compra.
6. **RAG** se cita siempre con el nombre del PDF fuente.
7. **Sin confirmación doble** en el flujo Analizar→Ejecutar: una vez que el usuario dice "sí", el agente ejecuta sin volver a preguntar.
