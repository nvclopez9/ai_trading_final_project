# Bug Report — Bot de Inversiones
Fecha: 2026-04-22

## Resumen ejecutivo

- **0 bugs críticos en el código del proyecto.**
- **1 bug crítico de ENTORNO**: el sistema del usuario tiene **Python 3.14.2**, que es incompatible con las dependencias actuales (pydantic V1 usado por chromadb/langchain-community aún no soporta 3.14).
- **4/4 tests pytest pasan**.
- **Todos los `.py` compilan** con `py_compile`.
- **Encoding UTF-8 correcto** en todos los ficheros clave.
- **Requirements.txt parseable** y con versiones pineadas.
- Veredicto: el código está listo. Bloqueante para arrancar: la versión de Python del entorno.

---

## Bugs críticos (impiden arrancar)

### BUG-001 (entorno, NO código) — Python 3.14 incompatible
- **Síntoma al importar chromadb**:
  ```
  pydantic.v1.errors.ConfigError: unable to infer type for attribute "chroma_server_nofile"
  UserWarning: Core Pydantic V1 functionality isn't compatible with Python 3.14 or greater.
  ```
- **Síntoma al importar agent_builder (vía langchain pydantic V1)**:
  ```
  TypeError: 'function' object is not subscriptable
  Unable to evaluate type annotation 'Optional[dict[str, Any]]'.
  ```
- **Causa**: Python 3.14 eliminó la evaluación de forward refs usada por `pydantic.v1`. LangChain y Chroma todavía dependen internamente de `pydantic.v1`.
- **Fix (elegir uno)**:
  1. Instalar **Python 3.12** (recomendado, es la versión LTS más estable del ecosistema ML/LangChain hoy).
  2. O Python 3.11 o 3.10.
  3. NO bajar de 3.10 (usamos anotaciones PEP 604 `X | None`).
- **Pasos en Windows**:
  1. Descargar instalador de https://www.python.org/downloads/release/python-3128/ (o la 3.12 más reciente).
  2. Instalar marcando "Add python.exe to PATH".
  3. Crear venv nuevo desde 3.12:
     ```powershell
     py -3.12 -m venv .venv
     .venv\Scripts\activate
     pip install -r requirements.txt
     ```

---

## Bugs no-críticos

Ninguno encontrado en análisis estático.

---

## Warnings / code smells

- **warning (informativo)** — pydantic V1 deprecation warning presente con Python 3.14. Desaparecerá automáticamente al cambiar a Python 3.12.
- **warning (bajo)** — `src/tools/rag_tool.py` accede a `_vectorstore._collection.count()` (API privada). Ya está envuelto en try/except. Sin impacto funcional, podría romper en upgrade mayor de `langchain-chroma`.
- **info** — El agente se construye dentro de `@st.cache_resource`, lo que significa que si cambias el `.env` durante una sesión Streamlit tienes que reiniciar el proceso para que se recargue.

---

## Informativos (no bugs)

- **README.md** en UTF-8 (364 líneas de ancho en algunas secciones, aceptable — el commenter agent lo reescribió limpio).
- **Contenido RAG poblado**: 12 documentos markdown + LICENCIA.md en `data/rag_docs/` con temario financiero completo, listos para ingesta.
- **`src/rag/ingest.py` soporta `.pdf`, `.md` y `.txt`** con fallback si `UnstructuredMarkdownLoader` no está instalado.
- El agente usa `create_tool_calling_agent` (no ReAct) — decisión justificada en qa_log.md.
- Memoria de chat aislada por `session_id` vía `RunnableWithMessageHistory` (Fase 4 completada).

---

## Verificaciones realizadas

| Verificación | Resultado |
|---|---|
| `py_compile` sobre los 19 ficheros .py | **OK (19/19)** |
| `file README.md requirements.txt app.py ...` | Todos UTF-8 |
| `requirements.txt` parseable con `packaging.Requirement` | **OK** |
| `python -m pytest tests/` | **4/4 passed** |
| Imports módulos puros (db, portfolio, market_tools, prompts, charts, portfolio_view) | OK |
| Imports módulos con chromadb/langchain | **FAIL por Python 3.14** (no nuestro bug) |

---

## Pasos recomendados ANTES de la demo

1. **Cambiar a Python 3.12** (ver BUG-001). Crear venv nuevo, reinstalar requirements.
2. **Tener Ollama corriendo** y haber hecho `ollama pull gemma3:4b && ollama pull nomic-embed-text`.
3. **Ingestar el RAG**:
   ```
   python -m src.rag.ingest
   ```
   El contenido `data/rag_docs/*.md` se procesará automáticamente.
4. **Arrancar la app**:
   ```
   streamlit run app.py
   ```
5. Probar en el chat: "¿Cómo está AAPL?", "¿Qué es el P/E?", "Compra 10 MSFT", "Muéstrame mi cartera".
6. Abrir pestañas `📊 Cartera` y `📈 Gráficos` para verificar visualización.
