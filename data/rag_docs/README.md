# Documentos RAG

Esta carpeta contiene el corpus de educación financiera que el agente usa para responder a preguntas conceptuales (qué es un PER, cómo funciona el DCA, qué significa drawdown, fiscalidad básica en España, etc.).

## Qué hay ya

Se incluye contenido **original del proyecto** en formato Markdown, en español, bajo licencia CC0 (ver `LICENCIA.md`). Cada documento cubre un bloque temático:

- `01_conceptos_basicos.md` — Acciones, bonos, ETFs, fondos, dividendos, términos base.
- `02_metricas_fundamentales.md` — PER, EPS, ROE, ROA, P/B, market cap, beta, FCF, EV/EBITDA.
- `03_analisis_fundamental.md` — Estados financieros, valoración intrínseca, value vs growth.
- `04_analisis_tecnico.md` — Tendencia, soporte/resistencia, medias móviles, RSI, MACD.
- `05_estrategias_largo_plazo.md` — Buy & hold, value, growth, dividend, DCA, indexación.
- `06_diversificacion_asset_allocation.md` — Asignación por perfil, correlaciones, rebalanceo.
- `07_riesgo.md` — Tipos de riesgo, volatilidad, drawdown, ratio Sharpe, VaR.
- `08_indices_y_mercados.md` — S&P 500, Dow, Nasdaq, IBEX 35, Euro Stoxx 50, MSCI World.
- `09_psicologia_del_inversor.md` — Sesgos, errores típicos, importancia del plan.
- `10_fiscalidad_espana_basica.md` — Tramos del ahorro, retenciones, compensación de pérdidas, regla de los 2 meses.
- `11_glosario.md` — ~80 términos alfabéticos de consulta rápida.
- `12_etfs_y_fondos_indexados.md` — TER, acumulación vs distribución, UCITS, ejemplos (VWCE, IWDA, CSPX).

Todos los documentos terminan con un disclaimer recordando que es información general, no asesoramiento financiero.

## Añadir más documentos (opcional)

Puedes añadir material adicional en esta carpeta:

- **PDFs** de fuentes libres: guías de la CNMV, Banco de España, ESMA; informes del BCE; material de universidades con licencia abierta; libros en dominio público.
- **Ficheros `.md`** con tus propias notas o contenido que quieras añadir al RAG.
- **Ficheros `.txt`** con apuntes o volcados de texto plano.

Respeta copyright: no incluyas PDFs comerciales sin licencia de redistribución.

## Reindexar

Tras añadir o modificar documentos, ejecuta desde la raíz del repo:

```
python -m src.rag.ingest
```

El script descubre automáticamente `.pdf`, `.md` y `.txt`, los trocea (chunk 800, overlap 120), genera embeddings con `nomic-embed-text` vía Ollama y los persiste en ChromaDB (`./chroma/`).

> **Nota**: la ingesta **no es idempotente**. Para reindexar desde cero, borra la carpeta `chroma/` antes de volver a ejecutar el comando.
