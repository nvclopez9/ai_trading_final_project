"""Configuración global de pytest para los tests del proyecto.

Objetivo único: asegurar que los tests puedan importar ``src.*`` (por
ejemplo ``from src.services import portfolio``) aunque se lancen con
``pytest tests/`` desde la raíz del repo sin instalar el paquete. Para ello
añadimos la raíz del proyecto al ``sys.path`` antes de que pytest
descubra y cargue los módulos de test.
"""
# sys y pathlib: manipulación del path de import y resolución de rutas.
import sys
from pathlib import Path

# Calculamos la raíz del repo: este fichero vive en tests/, así que el padre
# del padre es la carpeta del proyecto. ``resolve()`` convierte a ruta
# absoluta para evitar sorpresas cuando pytest se lanza desde otra cwd.
ROOT = Path(__file__).resolve().parents[1]
# Insertamos la raíz en la posición 0 de sys.path para que tenga prioridad
# sobre cualquier paquete instalado con el mismo nombre. El check de
# pertenencia evita duplicados si conftest se recarga.
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
