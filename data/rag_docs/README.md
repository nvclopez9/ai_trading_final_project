# Documentos RAG

Coloca aqui los PDFs de educacion financiera que quieras indexar en la base de conocimiento del agente.

Sugerencias (descarga tu mismo desde fuentes libres, el repo NO incluye PDFs por copyright):

- Glosario de terminos financieros de la CNMV.
- Guia del inversor principiante (CNMV / Bolsas y Mercados).
- Analisis tecnico basico (manuales abiertos).
- Estrategias de inversion value / growth / dividendos.
- Fundamentos de valoracion (P/E, EV/EBITDA, DCF, etc.).

Despues de dejar los PDFs en esta carpeta, ejecuta:

```
python -m src.rag.ingest
```

El script chunkea, genera embeddings con `nomic-embed-text` (Ollama) y persiste en `./chroma/`.
