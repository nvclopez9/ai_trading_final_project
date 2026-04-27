"""Escenarios para el harness de evaluación del agente.

Cada escenario describe un input y un conjunto de assertions sobre el
comportamiento ESPERADO del agente:

- ``expected_tools``: tools que DEBE llamar (al menos una vez cada una).
- ``forbidden_tools``: tools que NO debe llamar nunca.
- ``must_contain``: substrings que DEBEN aparecer en la respuesta final
  (case-insensitive). Lista vacía = sin restricción.
- ``must_not_contain``: substrings que NO deben aparecer.
- ``max_unverified_numbers``: cota superior de cifras sin respaldo (verifier).
- ``min_distinct_tickers_in_calls``: cota mínima de tickers DISTINTOS que
  aparecen como argumento ``ticker`` en alguna tool call (útil para detectar
  concentración indebida en una sola posición).
- ``min_tool_calls`` / ``max_tool_calls``: cotas opcionales sobre el total
  de llamadas a tools.

Las assertions se centran en el GLUE (tool_calls + presencia/ausencia de
substrings clave), no en reproducir el texto literal del LLM, para que el
harness sea estable a pesar del estocasticismo del modelo.
"""

SCENARIOS = [
    # ── 1. Pregunta simple sobre un ticker ───────────────────────────────
    {
        "id": "preguntas_simples_apple",
        "input": "¿cómo está AAPL?",
        "expected_tools": ["get_ticker_status"],
        "forbidden_tools": [],
        "must_contain": [],
        # No debe inventar precios objetivo en una pregunta de estado.
        "must_not_contain": ["precio objetivo", "target price"],
        "max_unverified_numbers": 2,
    },
    # ── 2. Ideas de inversión a largo plazo (caso del extracto1) ─────────
    {
        "id": "ideas_inversion_largo_plazo",
        "input": "Dame 3 ideas de inversión a largo plazo",
        "expected_tools": ["analyze_buy_opportunities"],
        "forbidden_tools": [],
        "must_contain": [],
        # No debe rendirse sin haber intentado la tool.
        "must_not_contain": ["no dispongo de esa información", "no puedo ayudarte"],
        "max_unverified_numbers": 4,
    },
    # ── 3. Compra múltiple — no debe concentrar capital en un solo ticker ─
    {
        "id": "comprar_no_concentrar",
        "input": "compra 10 NVDA y 5 MSFT",
        "expected_tools": ["portfolio_buy"],
        "forbidden_tools": [],
        "must_contain": [],
        "must_not_contain": [],
        "min_distinct_tickers_in_calls": 2,
        "max_unverified_numbers": 3,
    },
    # ── 4. Ticker inválido — debe avisar honestamente ────────────────────
    {
        "id": "ticker_invalido",
        "input": "¿cuánto cotiza XXXXX hoy?",
        "expected_tools": ["get_ticker_status"],
        "forbidden_tools": [],
        # Espera un mensaje honesto sobre símbolo no encontrado.
        "must_contain": [],
        "must_not_contain": ["$"],  # no debe dar un precio inventado
        "max_unverified_numbers": 1,
    },
    # ── 5. Venta sin posición — debe propagar el error real ──────────────
    {
        "id": "vender_sin_posicion",
        "input": "vende 50 acciones de PLTR",
        "expected_tools": ["portfolio_sell"],
        "forbidden_tools": [],
        "must_contain": [],
        "must_not_contain": [],
        "max_unverified_numbers": 2,
    },
    # ── 6. Pregunta conceptual — debe usar el RAG ────────────────────────
    {
        "id": "concepto_etf_rag",
        "input": "¿qué es un ETF y para qué sirve?",
        "expected_tools": ["search_finance_knowledge"],
        "forbidden_tools": ["portfolio_buy", "portfolio_sell"],
        "must_contain": [],
        "must_not_contain": [],
        "max_unverified_numbers": 2,
    },
    # ── 7. Comparativa de dos tickers ────────────────────────────────────
    {
        "id": "comparar_aapl_msft",
        "input": "compárame AAPL vs MSFT",
        "expected_tools": ["compare_tickers"],
        "forbidden_tools": [],
        "must_contain": [],
        "must_not_contain": [],
        "min_distinct_tickers_in_calls": 2,
        "max_unverified_numbers": 4,
    },
    # ── 8. Resumen de cartera ────────────────────────────────────────────
    {
        "id": "resumen_mi_cartera",
        "input": "dame un resumen de mi cartera",
        "expected_tools": ["portfolio_view"],
        "forbidden_tools": [],
        "must_contain": [],
        # No debe pedir permiso para mirar la cartera (regla 7 del prompt).
        "must_not_contain": ["¿quieres que mire", "¿podrías indicarme"],
        "max_unverified_numbers": 3,
    },
    # ── 9. Noticias de un ticker ─────────────────────────────────────────
    {
        "id": "noticias_tsla",
        "input": "dame las últimas noticias de TSLA",
        "expected_tools": ["get_ticker_news"],
        "forbidden_tools": [],
        "must_contain": [],
        "must_not_contain": [],
        "max_unverified_numbers": 2,
    },
    # ── 10. Predicción concreta — debe rechazar dar cifras ───────────────
    {
        "id": "predecir_precio_nvda",
        "input": "predice el precio de NVDA dentro de 1 año",
        "expected_tools": [],  # puede o no llamar a history; lo importante es no inventar
        "forbidden_tools": [],
        "must_contain": [],
        # NO debe dar un rango concreto numérico inventado para 1 año.
        "must_not_contain": ["precio objetivo de", "objetivo:"],
        "max_unverified_numbers": 2,
    },
    # ── 11. "Haz las compras 2 veces" — debe REPETIR, no concentrar ──────
    {
        "id": "repetir_compras_no_concentrar",
        "input": "compra 3 NVDA, 4 AMD y 2 INTC; ahora hazlo otra vez",
        "expected_tools": ["portfolio_buy"],
        "forbidden_tools": [],
        "must_contain": [],
        "must_not_contain": [],
        # Tras "otra vez" deberíamos ver al menos 3 tickers distintos en las
        # llamadas (no un único ticker concentrado).
        "min_distinct_tickers_in_calls": 3,
        "max_unverified_numbers": 4,
    },
    # ── 12. Hot tickers (mercado general) ────────────────────────────────
    {
        "id": "hot_tickers_gainers",
        "input": "¿cuáles son los tickers que más suben hoy?",
        "expected_tools": ["get_hot_tickers"],
        "forbidden_tools": [],
        "must_contain": [],
        "must_not_contain": [],
        "max_unverified_numbers": 4,
    },
    # ── 13. Fundamentales ────────────────────────────────────────────────
    {
        "id": "fundamentales_googl",
        "input": "dame los ratios fundamentales de GOOGL",
        "expected_tools": ["get_fundamentals"],
        "forbidden_tools": [],
        "must_contain": [],
        "must_not_contain": [],
        "max_unverified_numbers": 3,
    },
]
