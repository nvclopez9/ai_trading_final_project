#!/usr/bin/env bash
# Relanza el Bot de Inversiones en local (mata cualquier instancia previa).
#
# Uso:
#   ./run.sh          -> arranca/relanza Streamlit en http://localhost:8501
#   PORT=8600 ./run.sh -> usa otro puerto
#
# Compatible con Git Bash, WSL, Linux y macOS. Si estás en CMD/PowerShell
# nativo de Windows usa run.bat o ejecuta este script con `bash run.sh`.

set -euo pipefail

# Directorio del propio script (resolvemos symlinks). Permite invocarlo desde
# cualquier CWD sin que falle el venv ni la búsqueda de app.py.
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PORT="${PORT:-8501}"

# Localiza el python del venv. Aceptamos tanto el layout Windows (.venv/Scripts/)
# como el Unix (.venv/bin/) para que el mismo .sh funcione en ambos.
if [[ -x ".venv/Scripts/python.exe" ]]; then
  PY=".venv/Scripts/python.exe"
elif [[ -x ".venv/bin/python" ]]; then
  PY=".venv/bin/python"
else
  echo "[run.sh] ❌ No encuentro .venv/. Crea el entorno con:" >&2
  echo "         python -m venv .venv && .venv/Scripts/pip install -r requirements.txt" >&2
  exit 1
fi

# 1) Mata cualquier Streamlit que ya esté en el puerto.
echo "[run.sh] Liberando puerto $PORT..."
if command -v lsof >/dev/null 2>&1; then
  # macOS / Linux
  PIDS=$(lsof -ti tcp:"$PORT" || true)
  [[ -n "$PIDS" ]] && kill -9 $PIDS 2>/dev/null || true
elif command -v netstat >/dev/null 2>&1; then
  # Windows (Git Bash): netstat -ano + taskkill por PID.
  # $2 es "0.0.0.0:8501" o "[::]:8501"; comparamos el último ":XXX" con el puerto
  # y filtramos solo conexiones en LISTENING para no matar conexiones cliente.
  PIDS=$(netstat -ano 2>/dev/null | awk -v port="$PORT" '
    $4 == "LISTENING" {
      n = split($2, parts, ":")
      if (parts[n] == port) print $5
    }' | sort -u || true)
  for pid in $PIDS; do
    [[ -n "$pid" && "$pid" != "0" ]] && taskkill //F //PID "$pid" >/dev/null 2>&1 || true
  done
fi
sleep 1

# 2) Lanza Streamlit.
echo "[run.sh] Arrancando Streamlit en http://localhost:$PORT ..."
exec "$PY" -m streamlit run app.py \
  --server.port="$PORT" \
  --server.headless=true \
  --browser.gatherUsageStats=false
