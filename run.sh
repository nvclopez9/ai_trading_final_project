#!/usr/bin/env bash
# Arranca el Bot de Inversiones en local: FastAPI backend + React frontend.
#
# Uso:
#   ./run.sh              -> backend en :8000, frontend en :5173
#   API_PORT=8600 ./run.sh -> backend en puerto custom
#
# Compatible con Git Bash, WSL, Linux y macOS.
# En CMD/PowerShell nativo de Windows usa `bash run.sh`.

set -euo pipefail

# Muestra el error y pausa antes de cerrar (útil en terminales que se cierran solas)
trap 'echo; echo "[run.sh] ❌ Error en línea $LINENO — revisa arriba."; read -r -p "Presiona Enter para cerrar..." _' ERR

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ── Localiza Python del venv (Windows y Unix) ────────────────────────────────
if [[ -x ".venv/Scripts/python.exe" ]]; then
  PY=".venv/Scripts/python.exe"
elif [[ -x ".venv/bin/python" ]]; then
  PY=".venv/bin/python"
else
  # Fallback al Python del sistema (útil si las deps están instaladas globalmente)
  PY="python"
  echo "[run.sh] ⚠️  No se encontró .venv/. Usando Python del sistema." >&2
fi

# ── Verifica e instala dependencias Python si faltan ─────────────────────────
if ! "$PY" -c "import fastapi, uvicorn" 2>/dev/null; then
  echo "[run.sh] Instalando dependencias Python (requirements.txt)..."
  "$PY" -m pip install -r requirements.txt --quiet
fi

# ── FastAPI + React ───────────────────────────────────────────────────────────
API_PORT="${API_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"

# Comprueba que Node esté disponible
if ! command -v npm >/dev/null 2>&1; then
  echo "[run.sh] ❌ npm no encontrado. Instala Node.js >= 18 para el frontend React." >&2
  exit 1
fi

# Instala deps del frontend si no existen
if [[ ! -d "frontend/node_modules" ]]; then
  echo "[run.sh] Instalando dependencias del frontend..."
  (cd frontend && npm install --silent)
fi

echo "[run.sh] ╔══════════════════════════════════════════╗"
echo "[run.sh] ║  Bot de Inversiones — Stack completo     ║"
echo "[run.sh] ║  API:      http://localhost:$API_PORT          ║"
echo "[run.sh] ║  Frontend: http://localhost:$FRONTEND_PORT      ║"
echo "[run.sh] ╚══════════════════════════════════════════╝"

# Mata procesos previos (por puerto + por nombre en Windows)
_kill_port() {
  local port="$1"
  if command -v lsof >/dev/null 2>&1; then
    local pids
    pids=$(lsof -ti tcp:"$port" 2>/dev/null || true)
    [[ -n "$pids" ]] && kill -9 $pids 2>/dev/null || true
  elif command -v netstat >/dev/null 2>&1; then
    local pids
    pids=$(netstat -ano 2>/dev/null | awk -v p="$port" '
      $4=="LISTENING" { n=split($2,a,":"); if(a[n]==p) print $5 }
    ' | sort -u || true)
    for pid in $pids; do
      [[ -n "$pid" && "$pid" != "0" ]] && taskkill //F //PID "$pid" >/dev/null 2>&1 || true
    done
  fi
}
# Kill by port
for PORT in $API_PORT $FRONTEND_PORT $((FRONTEND_PORT+1)) $((FRONTEND_PORT+2)); do
  _kill_port "$PORT"
done
# Windows: kill lingering uvicorn (python) and vite/node processes by process name
if command -v powershell.exe >/dev/null 2>&1; then
  powershell.exe -NoProfile -NonInteractive -Command "
    Get-WmiObject Win32_Process | Where-Object {
      (\$_.Name -eq 'python.exe' -and \$_.CommandLine -match 'uvicorn') -or
      (\$_.Name -eq 'node.exe' -and \$_.CommandLine -match 'vite')
    } | ForEach-Object { Stop-Process -Id \$_.ProcessId -Force -ErrorAction SilentlyContinue }
  " 2>/dev/null || true
elif command -v pkill >/dev/null 2>&1; then
  pkill -f "uvicorn backend.main" 2>/dev/null || true
  pkill -f "vite" 2>/dev/null || true
fi
sleep 2

# Lee LOG_LEVEL del .env para pasárselo a uvicorn
_UVICORN_LOG_LEVEL="warning"
if [[ -f ".env" ]]; then
  _v=$(grep -E '^LOG_LEVEL=' ".env" 2>/dev/null | cut -d'=' -f2- | tr -d '[:space:]"'"'" | head -1)
  [[ -n "$_v" ]] && _UVICORN_LOG_LEVEL=$(echo "$_v" | tr '[:upper:]' '[:lower:]')
fi

# Inicia FastAPI en background
echo "[run.sh] → Arrancando FastAPI en :$API_PORT (log-level: $_UVICORN_LOG_LEVEL)..."
"$PY" -m uvicorn backend.main:app \
  --host 0.0.0.0 \
  --port "$API_PORT" \
  --reload \
  --reload-dir backend \
  --log-level "$_UVICORN_LOG_LEVEL" &
API_PID=$!

# Inicia el dev server de Vite en background
echo "[run.sh] → Arrancando Vite dev server en :$FRONTEND_PORT ..."
(cd frontend && npm run dev -- --port "$FRONTEND_PORT") &
FRONTEND_PID=$!

# Espera a que ambos arranquen
sleep 3

# Abre el navegador (best-effort)
URL="http://localhost:$FRONTEND_PORT"
if command -v xdg-open >/dev/null 2>&1; then
  xdg-open "$URL" &>/dev/null &
elif command -v open >/dev/null 2>&1; then
  open "$URL" &>/dev/null &
elif command -v start >/dev/null 2>&1; then
  start "$URL" &>/dev/null || true
fi

echo "[run.sh] ✓ Todo arrancado. Ctrl+C para detener."

# Espera a que cualquiera de los dos procesos muera
wait $API_PID $FRONTEND_PID
