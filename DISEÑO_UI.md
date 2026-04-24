# DISEÑO_UI — Bot de Inversiones con Agente de IA

> Propuesta de rediseño multi-pantalla sobre **Streamlit Multipage Apps**.
> Autor: agente de diseño de producto/UI.  Fecha: 2026-04-24.
>
> Este documento es el **contrato de diseño** que otro agente implementará.
> No contiene código productivo; sí firmas de componentes y wireframes.
>
> Asume que ya existen (en paralelo):
> - Pestaña/pantalla **❓ Ayuda** (`src/ui/help_view.py`).
> - **Chips de ejemplo** en el chat (prompts sugeridos cuando está vacío).
> - **Noticias** por ticker (`src/ui/news_view.py`).
> - Tools de mercado ampliadas (`src/tools/market_tools.py`).
> - Agente con prompts actualizados (`src/agent/prompts.py`).

---

## Índice

1. Análisis de referentes
2. Patrones ganadores (síntesis)
3. Arquitectura de pantallas propuesta
4. Convenciones de diseño (paleta, tipografía, iconografía)
5. Componentes reutilizables (firmas)
6. Wireframes ASCII por pantalla
7. Plan de migración (ficheros, singleton, navegación)
8. Orden de implementación y estimación (S/M/L)
9. Riesgos y mitigaciones
10. Checklist de accesibilidad y UX
11. Glosario y decisiones abiertas

---

## 1. Análisis de referentes

> Nota metodológica: la sesión no ha podido ejecutar `WebFetch` contra los
> sitios de los brokers (permiso denegado en este entorno). Los hallazgos
> siguientes se basan en conocimiento actualizado de dichas interfaces
> públicas. El implementer debería, si tiene dudas puntuales, abrir una
> captura de la pantalla concreta — pero a nivel de layout, el resumen
> siguiente es suficiente para decidir el diseño.

### 1.1 Robinhood (web/app)
- Navegación minimalista: top bar con buscador global central, izquierda logo, derecha cartera/cuenta.
- Home = dashboard personal: valor de cartera arriba grande, gráfico línea en verde/rojo según el día, debajo "Stocks" (posiciones) y "Lists" (watchlists).
- Ticker detail: precio gigante + delta día, chart protagonista con timeframes (1D/1W/1M/3M/1Y/5Y), debajo "Stats", "About", "News", "Analyst ratings", "Earnings", "Related lists".
- Densidad baja: pocas cifras por pantalla, mucho whitespace. Apuesta por "legible a 2 metros".
- Colores: verde `#00C805` subidas, rojo `#FF5000` bajadas, fondo negro puro en modo oscuro.

### 1.2 Trading212
- Tabs horizontales: Invest / CFD / Pies, y secciones: Discover, Portfolio, Orders, History.
- Home muestra "Top movers", "Most bought by community", "Events" (earnings próximos).
- Ticker detail con tabs: Overview / Chart / News / Financials / Ratios / Dividends / Analyst.
- Copia muy didáctica en tooltips (describe P/E ratio, etc.). Inspiración directa para nuestro perfil educativo.

### 1.3 eToro
- Social first: feed de operaciones de traders destacados arriba.
- Ticker page: Overview / Chart / Research / News / Feed.
- Colores verde/rojo + azul eléctrico como accent.
- "Stats" en grid 2×4 con tarjetas discretas (precio apertura, cierre anterior, day range, 52w range, vol., vol. medio, market cap, P/E).

### 1.4 Yahoo Finance (quote page)
- Navegación top: Markets / News / Research / Personal Finance / Screeners / Portfolios.
- Ticker detail = **la referencia canónica** del sector:
  - Header: símbolo, nombre, precio, delta abs y %, mercado cerrado/abierto.
  - Chart interactivo con periodos (1D, 5D, 1M, 6M, YTD, 1Y, 5Y, Max).
  - Grid "Summary": 16 celdas (Previous Close, Open, Bid, Ask, Day's Range, 52 Week Range, Volume, Avg Volume, Market Cap, Beta, PE Ratio, EPS, Earnings Date, Dividend, Ex-Dividend, 1y Target).
  - Tabs: Summary / Chart / Conversations / Statistics / Historical / Profile / Financials / Analysis / Options / Holders / Sustainability.
  - Sidebar derecha con "Related tickers" y news feed.
- Alta densidad pero jerarquizada por tamaño de fuente.

### 1.5 Google Finance
- Home: buscador grande + "You may be interested in" + "Market trends" (Indexes, Active, Gainers, Losers, Climate leaders, Crypto, Currencies).
- Ticker page limpísima: chart, "Compare to" (chips multi-ticker), "Previous close / Day range / Year range / Market cap / Avg Volume / P/E / Dividend yield / Primary exchange".
- Sidebar con "News" cronológico.
- Colores sobrios: verde `#137333`, rojo `#A50E0E`. Tipografía Roboto tabular.

### 1.6 TradingView (symbol page)
- Chart es el 70% del viewport; controles a izquierda (indicadores, dibujo) y derecha (watchlist + alertas + chat).
- Tabs inferiores: Overview / Ideas / News / Minds / Technicals / Forecast / Financials / Profile.
- "Key stats" en bandas horizontales compactas (4 filas × 4 columnas).
- Dark mode nativo, verde `#26A69A` / rojo `#EF5350` (convención de velas japonesas).

### 1.7 DeGiro
- Enfoque europeo, conservador. Top bar: Mercados / Favoritos / Cartera / Actividad.
- Ticker detail sobrio: precio, chart, "Información de la empresa", "Datos financieros", "Noticias".
- Watchlist/favoritos destacados.

### 1.8 Interactive Brokers (Client Portal)
- Densidad máxima, orientada a pro: múltiples paneles simultáneos, ventanas ancladas.
- No es nuestra referencia principal (demasiado denso para un producto educativo) pero tomamos prestado el patrón de **"Position card" con P&L absoluto y % simultáneo**.

### 1.9 Webull
- Extremadamente coloreado, con mucha info por cm². Tabs: Chart / Detail / Options / Analysis / News / Press / Financials / Profile.
- "Capital Flow" y "Level 2" son features pro que NO adoptamos.
- Inspiración útil: badges "Bullish/Bearish" en cabecera + barra de análisis técnico resumido (rating tipo speedometer de TradingView).

---

## 2. Patrones ganadores (15 bullets)

1. **El precio manda**: la cifra del precio actual siempre a 2-3× el tamaño del resto del texto.
2. **Delta dual**: mostrar siempre cambio absoluto y % juntos (ej. `+2,34 € (+1,25%)`).
3. **Verde/rojo semánticos**: coloreo consistente en TODA la app (precio, P&L, sparklines, badges).
4. **Chart como protagonista** en la pantalla de ticker (≥40% de la altura above-the-fold).
5. **Timeframes como chips**: `1D | 5D | 1M | 6M | YTD | 1Y | 5Y` en una fila horizontal.
6. **Stats grid 2×4 o 4×4**: métricas clave en tarjetas compactas (label gris arriba, valor negrita abajo).
7. **Tabs internas en ticker detail** (Resumen / Gráfico / Noticias / Explícame) en vez de scroll infinito.
8. **Buscador global omnipresente** (Ctrl+K estilo). En Streamlit lo emulamos con un `text_input` persistente en sidebar.
9. **Sparklines inline** en listados (posiciones, watchlist, hot tickers).
10. **Tipografía tabular para cifras**: monospace o tabular-nums para que los números alineen.
11. **Educación en tooltips**: todo acrónimo (P/E, EPS, Beta, Market Cap) tiene un "?" con explicación corta.
12. **Market status badge**: "Mercado abierto/cerrado" + hora del último precio.
13. **Top movers en home** como punto de entrada al flujo de descubrimiento.
14. **Navegación persistente**: el usuario siempre sabe dónde está (pill activa en la nav).
15. **Feedback inmediato**: spinner en cada call de red + toast/snackbar en éxito/error.

---

## 3. Arquitectura de pantallas propuesta

Adoptamos **Streamlit Multipage Apps** con carpeta `pages/`. El orden de las
páginas se controla con el prefijo numérico en el nombre del fichero.

```
proyecto IA/
├── app.py                      # 🏠 Home / Dashboard (página raíz)
├── pages/
│   ├── 1_💬_Chat.py
│   ├── 2_📈_Mercado.py
│   ├── 3_💼_Cartera.py
│   ├── 4_🔥_Hot.py
│   └── 5_❓_Ayuda.py
├── src/
│   └── ui/
│       ├── components/         # NUEVO — componentes reutilizables
│       │   ├── __init__.py
│       │   ├── ticker_card.py
│       │   ├── price_delta.py
│       │   ├── metric_grid.py
│       │   ├── sparkline.py
│       │   └── nav_hint.py
│       ├── charts.py           # ya existe
│       ├── portfolio_view.py   # ya existe
│       ├── help_view.py        # lo crea otro agente
│       └── news_view.py        # lo crea otro agente
└── .streamlit/
    └── config.toml             # tema dark + acentos
```

### Razonamiento de 6 pantallas

| # | Pantalla | Rol | Entra el usuario cuando… |
|---|----------|-----|--------------------------|
| 1 | 🏠 Home | Landing, overview personal | abre la app |
| 2 | 💬 Chat | Agente conversacional | quiere preguntar con lenguaje natural |
| 3 | 📈 Mercado | Detalle por ticker | quiere profundizar en un valor |
| 4 | 💼 Cartera | Gestión de posiciones | quiere registrar/ver su portfolio |
| 5 | 🔥 Hot | Descubrir movimientos | busca ideas / curiosidad |
| 6 | ❓ Ayuda | Onboarding + FAQ | es la primera vez / se atasca |

No incluimos "Screener" ni "Feed social" — quedan fuera del alcance MVP.

---

## 4. Convenciones de diseño

### 4.1 Paleta (`.streamlit/config.toml`)

```toml
[theme]
base = "dark"
primaryColor = "#2962FF"          # azul CTA
backgroundColor = "#0E1117"       # fondo general (default dark)
secondaryBackgroundColor = "#1A1F2B"  # chrome de tarjetas / sidebar
textColor = "#E6E9EF"
font = "sans serif"
```

Colores semánticos (se aplican vía inline style o markdown):

| Uso | Hex | Contexto |
|-----|-----|----------|
| Subida | `#00C851` | precio ↑, P&L+, delta positivo |
| Bajada | `#FF4444` | precio ↓, P&L−, delta negativo |
| Neutro | `#9AA0A6` | sin datos, variación ≈0 |
| Accent | `#2962FF` | botones primarios, links |
| Warning | `#FFB020` | banners educativos, "no es consejo financiero" |
| Info | `#4FC3F7` | tooltips, hints |

**Regla**: ningún verde/rojo distinto a los anteriores. Un solo valor por estado.

### 4.2 Tipografía

- Texto general: sans-serif por defecto de Streamlit.
- Cifras monetarias y %: `font-family: 'JetBrains Mono', 'Fira Code', monospace;`
  aplicado vía `st.markdown(..., unsafe_allow_html=True)` dentro del componente `price_delta`.
- Jerarquía:
  - Precio hero: `font-size: 2.5rem; font-weight: 700;`
  - Delta bajo precio: `font-size: 1.1rem;`
  - Stats label: `font-size: 0.85rem; color: #9AA0A6;`
  - Stats value: `font-size: 1.2rem; font-weight: 600;`

### 4.3 Formato numérico (locale `es_ES`)

- Miles con punto, decimales con coma: `12.450,30 €`.
- Porcentajes con signo explícito y 2 decimales: `+1,25%`, `-0,34%`.
- Shares/qty como entero si es entero, 4 decimales si fraccional.
- Market cap abreviado: `3,12 B$` / `845,2 M$`.

Helper sugerido: `fmt_money(x, currency="EUR")`, `fmt_pct(x)`, `fmt_qty(x)`
en `src/ui/components/__init__.py`.

### 4.4 Iconografía (emoji como prefijo de sección)

| Sección | Emoji |
|---------|-------|
| Home | 🏠 |
| Chat | 💬 |
| Mercado | 📈 |
| Cartera | 💼 |
| Hot | 🔥 |
| Ayuda | ❓ |
| Subida | 🟢 o ▲ |
| Bajada | 🔴 o ▼ |
| Noticias | 📰 |
| Estadísticas | 📊 |
| Sugerencia | 💡 |
| Aviso | ⚠️ |

Regla: emoji SIEMPRE al inicio del título, un espacio, luego el texto.

---

## 5. Componentes reutilizables (firmas)

Ubicación: `src/ui/components/*.py`. No se implementan aquí — se declaran
para que el implementer respete contrato.

### 5.1 `ticker_card(ticker: str, compact: bool = False) -> None`

Renderiza una tarjeta con símbolo, nombre corto, precio actual, delta %
y (si `compact=False`) una sparkline 30d.

- Llama a `market_tools` para obtener precio y serie.
- En `compact=True` se usa en listados (posiciones, hot tickers).
- En `compact=False` se usa como "ticker activo" en el sidebar del Chat.
- Clicable: incluye un `st.button` "Abrir en Mercado" que hace
  `st.switch_page("pages/2_📈_Mercado.py")` tras guardar el ticker
  en `st.session_state["active_ticker"]`.

### 5.2 `price_delta(current: float, previous: float, currency: str = "USD") -> None`

Renderiza precio + delta coloreado, formateado.

- Usa `st.metric(label=..., value=fmt_money(current), delta=fmt_pct(...))`
  cuando no se requiera estilo custom.
- Para el hero de Mercado, usa markdown con HTML inline y clases semánticas.

### 5.3 `metric_grid(metrics: dict[str, str | float], cols: int = 4) -> None`

Dibuja un grid de `cols` columnas con pares label/valor.

- Input: `{"Market Cap": "3,12 B$", "P/E": 29.4, "EPS": 6.12, ...}`.
- Usa `st.columns(cols)` y dentro `st.metric` (label arriba gris, valor abajo).
- Los valores `None` o `"—"` se renderizan con guion largo.

### 5.4 `sparkline(series: list[float], up_color: str = "#00C851", down_color: str = "#FF4444") -> plotly.Figure`

Mini-gráfico sin ejes, sin grid, sin hover. Devuelve una figura Plotly.

- Altura fija: 40 px.
- El color se decide por `series[-1] >= series[0]`.
- Se embebe con `st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})`.

### 5.5 `nav_hint(text: str, target_page: str, ticker: str | None = None) -> None`

Renderiza un botón "→ Ir a X" con efecto de navegación programática.

- Guarda en `st.session_state` las claves necesarias antes de `st.switch_page`.

### 5.6 Helpers de formato

```python
fmt_money(x: float, currency: str = "EUR") -> str
fmt_pct(x: float, with_sign: bool = True) -> str
fmt_qty(x: float) -> str
fmt_market_cap(x: float) -> str   # "3,12 B$", "845,2 M$"
color_for_delta(x: float) -> str  # "#00C851" | "#FF4444" | "#9AA0A6"
```

---

## 6. Wireframes ASCII por pantalla

### 6.1 🏠 Home / Dashboard (`app.py`)

```
┌──────────────────────────────────────────────────────────────────────┐
│ [sidebar Streamlit]                                                  │
│  🏠 Home                                                             │
│  💬 Chat                                                             │
│  📈 Mercado                                                          │
│  💼 Cartera                                                          │
│  🔥 Hot                                                              │
│  ❓ Ayuda                                                            │
│  ────────────                                                        │
│  🔎 [buscador global]                                                │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  👋 Hola, Iván                                     Mercado abierto ● │
│                                                                      │
│  ┌─────────────────────────────┐   ┌─────────────────────────────┐  │
│  │ Valor cartera               │   │ Sparkline 30d               │  │
│  │  12.450,30 €                │   │  ▁▂▂▃▅▆▇▆▅▆▇█▇▆▅▆▇█▇█      │  │
│  │  +155,20 €  (+1,25%) hoy    │   │                             │  │
│  └─────────────────────────────┘   └─────────────────────────────┘  │
│                                                                      │
│  💼 Mis posiciones (top 5)                          Ver todas →      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ AAPL   10 uds   1.875,40 €   ▲ +1,24%   ▁▂▃▄▅▆▅▇            │   │
│  │ MSFT    4 uds   1.640,20 €   ▼ -0,42%   ▇▆▅▄▃▂▃▂            │   │
│  │ TSLA    6 uds   1.024,80 €   ▲ +3,10%   ▁▁▂▃▅▆▇█            │   │
│  │ VWCE   20 uds   2.210,00 €   ▲ +0,18%   ▄▅▄▅▅▆▆▇            │   │
│  │ NVDA    2 uds     820,50 €   ▲ +2,05%   ▂▃▄▅▆▇▆▇            │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  🔥 Mercado hoy                                                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                  │
│  │ Top gainers │  │ Top losers  │  │ Most active │                  │
│  │ NVDA +7.2%  │  │ META -4.1%  │  │ TSLA 45M    │                  │
│  │ AMD  +5.4%  │  │ NFLX -2.8%  │  │ AAPL 38M    │                  │
│  │ TSLA +3.1%  │  │ KO   -1.9%  │  │ SPY  28M    │                  │
│  └─────────────┘  └─────────────┘  └─────────────┘                  │
│                                                                      │
│  💡 Sugerencias del bot                                              │
│  [ ¿Qué tal va AAPL hoy? ]   [ Resumen de mi cartera ]              │
│  [ Noticias sobre NVDA ]     [ Explícame qué es P/E ]                │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

### 6.2 💬 Chat (`pages/1_💬_Chat.py`)

```
┌──────────────────────────────────────────────────────────────────────┐
│ [sidebar con nav]                                                    │
├──────────────────────────────────────────────────────────────────────┤
│  💬 Chat con el agente                                               │
│  ┌───────────────────────────────────────┬────────────────────────┐ │
│  │                                       │  📌 Ticker activo      │ │
│  │  🧑 ¿Cómo va AAPL?                     │  ┌──────────────────┐  │ │
│  │                                       │  │ AAPL             │  │ │
│  │  🤖 AAPL cotiza a 187,54 $ (+1,24%).   │  │ Apple Inc.      │  │ │
│  │      Volumen sobre la media. Hay       │  │ 187,54 $         │  │ │
│  │      noticias sobre el iPhone 17...    │  │ ▲ +1,24%         │  │ │
│  │                                       │  │ ▁▂▃▅▆▇▆▇         │  │ │
│  │  🧑 Compárame con MSFT                  │  │                  │  │ │
│  │                                       │  │ [Abrir en 📈]    │  │ │
│  │  🤖 [tabla comparativa]                 │  └──────────────────┘  │ │
│  │                                       │                        │ │
│  │                                       │  Historial sesión:     │ │
│  │                                       │  • AAPL                │ │
│  │                                       │  • MSFT                │ │
│  │                                       │                        │ │
│  ├───────────────────────────────────────┤  [ 🗑 Limpiar chat ]   │ │
│  │  Chips (si chat vacío):               │                        │ │
│  │  [¿Qué tal AAPL?] [Resumen cartera]   │                        │ │
│  │  [Noticias NVDA]  [Explica P/E]       │                        │ │
│  ├───────────────────────────────────────┤                        │ │
│  │  [ Pregunta al agente...          ⏎ ] │                        │ │
│  └───────────────────────────────────────┴────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────┘
```

Nota: el panel derecho usa `st.columns([3,1])`. En móvil se colapsa
debajo del chat (Streamlit responsive).

### 6.3 📈 Mercado / Detalle de ticker (`pages/2_📈_Mercado.py`)

```
┌──────────────────────────────────────────────────────────────────────┐
│  📈 Mercado                                                          │
│                                                                      │
│  🔎 Ticker: [ AAPL ▾ ]   [ Buscar ]           Mercado abierto ●     │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ AAPL · Apple Inc. · NASDAQ                                   │   │
│  │                                                              │   │
│  │   187,54 $                                                   │   │
│  │   ▲ +2,30 $   (+1,24%) hoy                                   │   │
│  │                                                              │   │
│  │ Rango 52s: 142,10 – 198,23   │   P/E: 29,4   │ Mkt Cap: 3,1T │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  [ 1D ] [ 5D ] [ 1M ] [ 6M ] [ YTD ] [ 1A ] [ 5A ]                  │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                                                              │   │
│  │                    📉 Gráfico Plotly                         │   │
│  │                                                              │   │
│  │                                                              │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  [ 📊 Estadísticas ] [ 📰 Noticias ] [ 💡 Explícame esta empresa ]  │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ Estadísticas (4×4 grid)                                      │   │
│  │                                                              │   │
│  │  Apertura      Cierre ant.    Rango día     Volumen          │   │
│  │  185,20        185,24         184,80-188   52,3M             │   │
│  │                                                              │   │
│  │  Rango 52s     Vol. medio     P/E           EPS              │   │
│  │  142–198       58M            29,4          6,12             │   │
│  │                                                              │   │
│  │  Market Cap    Beta           Dividendo    Próx. earnings    │   │
│  │  3,12 T$       1,28           0,96 $       2026-05-02        │   │
│  │                                                              │   │
│  │  Sector        Industria      País          Web              │   │
│  │  Tech          Consumer Elec  US            apple.com        │   │
│  └──────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────┘
```

Las tres tabs internas (`st.tabs`) reemplazan al scroll largo:
- **📊 Estadísticas**: grid 4×4 con `metric_grid`.
- **📰 Noticias**: delega en `src/ui/news_view.py` (del otro agente).
- **💡 Explícame esta empresa**: botón grande que dispara el agente con un
  prompt estructurado del tipo:
  `"Explícame brevemente qué hace {ticker}, su modelo de negocio y riesgos principales, en 5 bullets."`
  y renderiza la respuesta en un `st.info` expandible; además, ofrece
  `"Ir al chat con esta pregunta →"` que navega a Chat con el prompt pre-cargado.

### 6.4 💼 Mi Cartera (`pages/3_💼_Cartera.py`)

```
┌──────────────────────────────────────────────────────────────────────┐
│  💼 Mi Cartera                                                       │
│                                                                      │
│  ┌────────────────┐ ┌────────────────┐ ┌────────────────┐           │
│  │ Valor total    │ │ Cost basis     │ │ P&L total      │           │
│  │ 12.450,30 €    │ │ 11.120,00 €    │ │ +1.330,30 €    │           │
│  │                │ │                │ │ +11,96%        │           │
│  └────────────────┘ └────────────────┘ └────────────────┘           │
│                                                                      │
│  Posiciones                                                          │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ Ticker │ Qty │ Avg  │ Actual │ Valor   │ P&L    │ P&L %     │   │
│  │ AAPL   │ 10  │ 165  │ 187,54 │ 1.875,4 │ +225,4 │ +13,6% 🟢  │   │
│  │ MSFT   │  4  │ 420  │ 410,05 │ 1.640,2 │ −39,8  │ −2,4%  🔴  │   │
│  │ TSLA   │  6  │ 150  │ 170,80 │ 1.024,8 │ +124,8 │ +13,9% 🟢  │   │
│  │ ...                                                            │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ┌─────────────────────────┐  ┌─────────────────────────┐           │
│  │ Allocation (pie)        │  │ P&L por posición (bar)  │           │
│  │   🥧                    │  │   ▁▂▃▅▆▇                │           │
│  └─────────────────────────┘  └─────────────────────────┘           │
│                                                                      │
│  ▸ Transacciones (expander)                                          │
│                                                                      │
│  [ ➕ Añadir posición ]  [ ⬇ Exportar CSV ]  [ 🗑 Limpiar cartera ] │
└──────────────────────────────────────────────────────────────────────┘
```

Reutiliza `src/ui/portfolio_view.py` existente; se refactoriza la función
`render_portfolio_tab()` para que acepte un parámetro opcional
`as_page: bool = False` que ajuste el título superior (H1 vs H2).

"Limpiar cartera" abre un `st.dialog` (Streamlit ≥1.31) o un expander con
doble confirmación ("Escribe BORRAR para confirmar").

### 6.5 🔥 Hot (`pages/4_🔥_Hot.py`)

```
┌──────────────────────────────────────────────────────────────────────┐
│  🔥 Tickers Hot                                                      │
│                                                                      │
│  [ 🟢 Gainers ] [ 🔴 Losers ] [ 🔵 Most Active ]                     │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ # │ Ticker │ Nombre        │ Precio  │ Var%    │ Spark 5d   │   │
│  │ 1 │ NVDA   │ Nvidia        │ 892,40  │ +7,24%  │ ▁▂▃▅▆▇█   │   │
│  │ 2 │ AMD    │ AMD           │ 168,30  │ +5,44%  │ ▁▂▃▄▅▆▇   │   │
│  │ 3 │ TSLA   │ Tesla         │ 170,80  │ +3,10%  │ ▁▁▂▃▅▆▇   │   │
│  │ 4 │ META   │ Meta          │ 512,10  │ +2,80%  │ ▂▃▄▅▆▇    │   │
│  │ 5 │ NFLX   │ Netflix       │ 620,40  │ +2,45%  │ ▂▃▄▅▆▇    │   │
│  │ ...                                                           │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  (Click sobre fila → abre Mercado con ticker pre-cargado)            │
└──────────────────────────────────────────────────────────────────────┘
```

En la tabla, cada fila tiene un botón "Abrir →" a la derecha que hace
`st.session_state["active_ticker"] = ticker; st.switch_page("pages/2_📈_Mercado.py")`.

### 6.6 ❓ Ayuda (`pages/5_❓_Ayuda.py`)

```
┌──────────────────────────────────────────────────────────────────────┐
│  ❓ Ayuda                                                            │
│                                                                      │
│  ▸ ¿Qué puede hacer este bot?                                        │
│  ▸ ¿Qué preguntas puedo hacer al chat?                               │
│  ▸ ¿Cómo gestiono mi cartera?                                        │
│  ▸ ¿Qué significan P/E, EPS, Market Cap?                             │
│  ▸ Limitaciones y disclaimer                                         │
│  ▸ Atajos y navegación                                               │
│                                                                      │
│  ⚠️  Este bot es educativo. No constituye asesoramiento financiero. │
└──────────────────────────────────────────────────────────────────────┘
```

Delegada a `src/ui/help_view.py`. Esta página solo llama a
`render_help()` y añade al final el disclaimer legal.

---

## 7. Plan de migración

### 7.1 Ficheros a crear/mover

**Nuevos ficheros:**
- `pages/1_💬_Chat.py`
- `pages/2_📈_Mercado.py`
- `pages/3_💼_Cartera.py`
- `pages/4_🔥_Hot.py`
- `pages/5_❓_Ayuda.py`
- `src/ui/components/__init__.py` (con helpers `fmt_*`)
- `src/ui/components/ticker_card.py`
- `src/ui/components/price_delta.py`
- `src/ui/components/metric_grid.py`
- `src/ui/components/sparkline.py`
- `src/ui/components/nav_hint.py`
- `src/ui/home_view.py` (contenido del nuevo home)
- `src/ui/hot_view.py` (tabla gainers/losers/active)
- `src/ui/market_view.py` (detalle de ticker)
- `src/agent/singleton.py` (ver 7.2)
- `.streamlit/config.toml` (tema)

**Ficheros modificados:**
- `app.py`: se vacía casi por completo y pasa a ser el Home. Ya **no**
  contiene `st.tabs`. La inicialización del agente se centraliza.
- `src/ui/portfolio_view.py`: se extrae `render_portfolio_tab` a
  `render_portfolio(as_page: bool = False)`.
- `src/ui/charts.py`: se añade parámetro `height` opcional para que la
  sparkline pueda reutilizar la lógica.

**Ficheros eliminados/obsoletos:** ninguno — se mantiene compatibilidad.

### 7.2 Singleton del agente (`src/agent/singleton.py`)

Multipage comparte `st.cache_resource` a nivel de proceso, pero el patrón
correcto es **centralizar** la función cacheada en un módulo y llamarla
desde cada página:

```python
# src/agent/singleton.py (firma, NO implementar aquí)
@st.cache_resource(show_spinner="Inicializando agente...")
def get_agent():
    init_db()
    return build_agent()

def ensure_session_id() -> str:
    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())
    return st.session_state.session_id
```

Cada página hace al principio:

```python
from src.agent.singleton import get_agent, ensure_session_id
agent = get_agent()
session_id = ensure_session_id()
```

### 7.3 Navegación programática

- **Entre páginas**: `st.switch_page("pages/2_📈_Mercado.py")`.
- **Pasar parámetros**: se usa `st.session_state` como bus.
  - `st.session_state["active_ticker"]` — el ticker "actual".
  - `st.session_state["prefill_prompt"]` — prompt para inyectar en Chat.
  - `st.session_state["messages"]` — historial visual (como hoy).
- **Sidebar**: Streamlit muestra la nav automáticamente. Añadimos al
  sidebar un buscador global + disclaimer al pie.

### 7.4 Session state compartido — contrato

| Clave | Tipo | Escribe | Lee |
|-------|------|---------|-----|
| `session_id` | str | Home al arrancar | Chat (al invocar agente) |
| `messages` | list[dict] | Chat | Chat |
| `active_ticker` | str | Home, Hot, Mercado, Chat | Mercado, Chat (sidebar) |
| `prefill_prompt` | str \| None | Mercado ("Explícame…"), Home (chips) | Chat |
| `chart_period` | str | Mercado | Mercado |
| `nav_target` | str \| None | cualquiera | router post-switch |

---

## 8. Orden de implementación y estimación

Recomendación (respetando el orden solicitado con ajustes mínimos):

| Orden | Pantalla | Esfuerzo | Justificación |
|-------|----------|----------|---------------|
| 1 | 💼 Cartera | **S** | Ya existe `portfolio_view.py`; solo envolver en página. |
| 2 | 📈 Mercado | **L** | Es la pantalla más densa: hero + chart + tabs + stats + noticias + "Explícame". |
| 3 | 💬 Chat | **M** | Extraer de `app.py` + añadir sidebar con ticker activo. |
| 4 | 🏠 Home | **M** | Requiere nuevos widgets (sparkline, top movers) pero reutiliza componentes. |
| 5 | 🔥 Hot | **S** | Solo listas + navegación. Depende de `market_tools.get_hot_tickers()`. |
| 6 | ❓ Ayuda | **S** | Ya la hace otro agente; solo envolver. |

**Total**: ~2× L-equivalentes, ~3× M, ~3× S. Viable en 1 sprint corto (3-5 días de trabajo concentrado).

**Criterios de "hecho" por pantalla:**
- Renderiza sin errores con agente caído (fallback amable).
- Cifras con formato `es_ES`.
- Responsive hasta 360 px de ancho sin overflow.
- Todos los estados: vacío, cargando, error, OK.

---

## 9. Riesgos y mitigaciones

| Riesgo | Impacto | Mitigación |
|--------|---------|------------|
| Re-render cross-page del agente | Latencia al cambiar de página | Singleton en `src/agent/singleton.py` + `@st.cache_resource` (comparte proceso). Test: cambiar páginas 10× no debe reinicializar Ollama. |
| Pérdida de `session_state` | Chat "olvida" el contexto visual al navegar | **No ocurre**: `session_state` es compartido entre páginas del mismo browser tab. Sí documentarlo en Ayuda. |
| Llamadas a yfinance redundantes | Lentitud en Home (5 sparklines + 3 top movers) | Cachear con `@st.cache_data(ttl=300)` las funciones de `market_tools` que devuelvan series. |
| `st.switch_page` requiere ≥1.30 | Entorno antiguo rompe | Pin `streamlit>=1.32` en `requirements.txt` al implementar. |
| Emojis en nombre de fichero | Windows/git a veces problemáticos | Si da error, renombrar a `1_Chat.py` sin emoji; el emoji va en `st.set_page_config(page_icon=...)`. |
| Tema dark forzado | Usuarios que prefieran light | Aceptable para MVP; documentar en Ayuda cómo cambiarlo en `config.toml`. |
| Colisión con otro agente (help, news, chips) | Merge conflict en `app.py` | Este diseño **vacía** `app.py` y crea nuevas páginas — los cambios del otro agente en `help_view.py`/`news_view.py` se reutilizan sin conflicto. Verificar antes de mergear. |
| Agente fallando en "Explícame" | Pantalla Mercado se bloquea | Try/except + mensaje amable (patrón ya existente en Chat). |

---

## 10. Checklist de accesibilidad y UX

- [ ] Contraste AA en todos los textos sobre `#0E1117` (verificar con
      Lighthouse). Los colores propuestos cumplen ≥ 4.5:1.
- [ ] Labels explícitos en todos los `st.text_input`, `st.selectbox`,
      `st.number_input`. No usar `label_visibility="collapsed"` salvo
      que haya un título adjacente que sustituya.
- [ ] Spinner en cada operación de red (`st.spinner("Cargando {ticker}...")`).
- [ ] `st.toast` en éxito (ej. "Posición añadida ✅") y `st.error` en fallo
      con mensaje humano (sin stacktrace).
- [ ] Fallback amable si yfinance falla: "No pudimos obtener datos de {ticker}.
      Comprueba el símbolo o inténtalo más tarde."
- [ ] Responsive: nunca más de 4 columnas en un `st.columns` a menos que
      el contenido sea trivial (iconos). En cartera la tabla usa
      `st.dataframe` que es responsive por defecto.
- [ ] Keyboard: el chat input se envía con Enter (default Streamlit).
      El buscador de Mercado también. No requerimos shortcuts adicionales.
- [ ] Orden de lectura lógico de arriba a abajo en todas las pantallas.
- [ ] Todos los porcentajes incluyen el símbolo `%` explícito y signo.
- [ ] Disclaimer "No es asesoramiento financiero" en Home (footer) y Ayuda.
- [ ] Tooltips con `help="..."` en acrónimos (P/E, EPS, Market Cap, Beta).

---

## 11. Glosario y decisiones abiertas

### Glosario

- **Sparkline**: mini-gráfico de línea sin ejes, ~40 px alto.
- **Delta**: diferencia entre precio actual y precio de referencia (cierre anterior).
- **P&L**: Profit and Loss (beneficio/pérdida).
- **Hot ticker**: ticker en gainers/losers/most active del día.
- **Ticker activo**: último ticker mencionado en el chat o seleccionado en Mercado.

### Decisiones tomadas (no alternativas)

1. **6 páginas** y no 4 ni 8. Separamos Home de Chat para dar respiro al
   onboarding; separamos Hot de Home porque "descubrir" es otro modo mental.
2. **Dark theme por defecto**. Los brokers serios (TradingView, Webull)
   lo usan; reduce fatiga visual en sesiones largas.
3. **`st.switch_page` + `session_state` como bus**. No usamos querystring
   (`st.query_params`) porque añade fricción y se pierde al refrescar.
4. **Reutilizar `news_view.py` y `help_view.py` del otro agente tal cual**.
   No duplicamos esfuerzo.
5. **Prefijos numéricos + emoji en `pages/`**. Es la forma canónica de
   ordenar la nav de Streamlit; el emoji se muestra en el sidebar.
6. **Cachear `market_tools` con `ttl=300`**. Balance entre frescura (5 min)
   y latencia en Home.
7. **No implementar screener ni feed social**. Fuera de alcance MVP.

### Decisiones abiertas (que el implementer puede ajustar)

- Formato exacto de números si el negocio prefiere `1,234.56` (anglosajón)
  en vez de `1.234,56` (es_ES). Propuesta: `es_ES`.
- Si la `sparkline` se calcula con series 30d o 5d en las distintas
  pantallas (Home: 30d; Hot: 5d). No bloqueante.
- Si `active_ticker` debería persistir entre sesiones (SQLite) o solo en
  memoria. Propuesta: solo memoria.

---

## Anexo A — Ejemplo de esqueleto mental de `pages/2_📈_Mercado.py`

> Pseudocódigo para orientar al implementer, NO es el código final.

```
setup página (title, icon)
agent = get_agent()
session_id = ensure_session_id()

ticker = st.session_state.get("active_ticker", "AAPL")
ticker = st.text_input("Ticker", value=ticker).upper().strip()
st.session_state["active_ticker"] = ticker

info = market_tools.get_quote(ticker)  # cacheado
render hero con price_delta(info.price, info.prev_close)
render stats rápidas (rango 52s, P/E, mkt cap) en una fila

period = chips [1D, 5D, 1M, 6M, YTD, 1Y, 5Y]
fig = price_history_chart(ticker, period)
st.plotly_chart(fig, use_container_width=True)

tab_stats, tab_news, tab_explain = st.tabs([...])
with tab_stats: metric_grid(info.all_stats, cols=4)
with tab_news: render_news(ticker)   # del otro agente
with tab_explain:
    if st.button("💡 Explícame esta empresa"):
        prompt = f"Explícame brevemente qué hace {ticker}..."
        with st.spinner("El agente está pensando..."):
            resp = agent.invoke({"input": prompt}, config=...)
        st.info(resp["output"])
        if st.button("Ir al chat →"):
            st.session_state["prefill_prompt"] = prompt
            st.switch_page("pages/1_💬_Chat.py")
```

---

**FIN DEL DOCUMENTO DE DISEÑO**
