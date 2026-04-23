# Documentos RAG

Esta carpeta contiene el corpus de educación financiera que el agente usa para responder a preguntas conceptuales (qué es un PER, cómo funciona el DCA, qué significa drawdown, fiscalidad básica en España, etc.).

## Qué hay

**PDFs oficiales publicados en abierto por entidades reguladoras/supervisoras.** Nada de blogs, cursos privados ni contenido de pago. Cada documento se ha descargado directamente del portal de la entidad emisora.

| Archivo | Entidad | Descripción | URL oficial |
|---|---|---|---|
| `cnmv_50_preguntas_inversion.pdf` | CNMV | 50 preguntas y respuestas básicas sobre inversión (glosario y conceptos clave). | <https://www.cnmv.es/DocPortal/Publicaciones/Guias/Guia_50_preguntas.pdf> |
| `cnmv_guia_accionista.pdf` | CNMV | Los derechos de los accionistas: qué implica ser accionista, derechos económicos y políticos. | <https://www.cnmv.es/DocPortal/Publicaciones/Guias/guia_accionistacc.pdf> |
| `cnmv_guia_productos_renta_fija.pdf` | CNMV | "Qué debe saber de... los productos de renta fija" (bonos, letras, obligaciones). | <https://www.cnmv.es/DocPortal/Publicaciones/Guias/guia_rentafija.pdf> |
| `cnmv_guia_fondos_inversion.pdf` | CNMV | Los fondos de inversión y la inversión colectiva. | <https://www.cnmv.es/DocPortal/Publicaciones/Guias/Los_fondos_de_inversion.pdf> |
| `cnmv_manual_universitarios_mercado_valores.pdf` | CNMV | Manual para universitarios: el mercado de valores y los productos de inversión. | <http://www.cnmv.es/DocPortal/Publicaciones/Guias/ManualUniversitarios.pdf> |
| `cnmv_psicologia_economica_inversores.pdf` | CNMV | Psicología económica para inversores (sesgos, heurísticos, errores típicos). | <https://www.cnmv.es/DocPortal/Publicaciones/Guias/Psicologia_economica_para_inversores.pdf> |
| `cnmv_fiscalidad_acciones_irpf.pdf` | CNMV | Fiscalidad de las acciones cotizadas en el IRPF (España). | <https://www.cnmv.es/DocPortal/Publicaciones/Guias/GuiaFiscalidadAcciones2026.pdf> |
| `cnmv_fiscalidad_fondos_irpf.pdf` | CNMV | Fiscalidad de los fondos de inversión en el IRPF (España). | <https://www.cnmv.es/docportal/publicaciones/guias/guia_fiscalidad_fondos_de_inversion.pdf> |
| `sec_saving_and_investing_roadmap.pdf` | SEC / Investor.gov | "Saving and Investing — A Roadmap to Your Financial Security" (conceptos básicos, planificación). | <https://www.investor.gov/sites/investorgov/files/2019-02/Saving-and-Investing.pdf> |
| `sec_mutual_funds_and_etfs.pdf` | SEC / Investor.gov | "Mutual Funds and ETFs — A Guide for Investors" (fondos, ETFs, comisiones, clases). | <https://www.investor.gov/sites/investorgov/files/2019-02/mutual-funds-ETFs.pdf> |

Los PDFs de la CNMV están en **español**; los de la SEC en **inglés**. El RAG mezcla ambos idiomas sin problema porque el embedding `nomic-embed-text` es multilingüe.

## Cobertura temática

- **Conceptos básicos**: acciones, bonos, ETFs, fondos (CNMV 50 preguntas, Manual universitarios, SEC Saving and Investing).
- **Métricas fundamentales y análisis**: Manual universitarios CNMV.
- **Renta fija**: CNMV Productos de renta fija.
- **Fondos y ETFs**: CNMV Fondos de inversión + SEC Mutual Funds and ETFs.
- **Derechos del accionista**: CNMV Guía del accionista.
- **Psicología del inversor / sesgos**: CNMV Psicología económica para inversores.
- **Fiscalidad España**: CNMV Fiscalidad acciones + Fiscalidad fondos.
- **Planificación y estrategia**: SEC Saving and Investing Roadmap.

## Añadir más documentos (opcional)

Puedes añadir material adicional en esta carpeta:

- **PDFs** de otras fuentes libres: Banco de España / finanzasparatodos.es, ESMA, BCE, FINRA, OCDE, material de universidades con licencia abierta, libros en dominio público.
- **Ficheros `.md`** con tus propias notas o contenido que quieras añadir al RAG.
- **Ficheros `.txt`** con apuntes o volcados de texto plano.

Respeta copyright: no incluyas PDFs comerciales sin licencia de redistribución. Ver `LICENCIA.md`.

## Reindexar

Tras añadir o modificar documentos, ejecuta desde la raíz del repo:

```
python -m src.rag.ingest
```

El script descubre automáticamente `.pdf`, `.md` y `.txt`, los trocea (chunk 800, overlap 120), genera embeddings con `nomic-embed-text` vía Ollama y los persiste en ChromaDB (`./chroma/`).

> **Nota**: la ingesta **no es idempotente**. Para reindexar desde cero, borra la carpeta `chroma/` antes de volver a ejecutar el comando.
