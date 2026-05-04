@echo off
title Bot de Inversiones — Launcher
cd /d "%~dp0"

echo =============================================
echo   Bot de Inversiones — Arrancando stack...
echo =============================================
echo.

echo [1/4] Matando procesos previos...
powershell -NoProfile -NonInteractive -Command ^
  "$ports = @(8000,5173,5174); " ^
  "foreach ($p in $ports) { " ^
  "  $pids = (Get-NetTCPConnection -LocalPort $p -ErrorAction SilentlyContinue).OwningProcess | Select-Object -Unique; " ^
  "  foreach ($id in $pids) { if ($id -gt 0) { Stop-Process -Id $id -Force -ErrorAction SilentlyContinue } } " ^
  "} " ^
  "Get-WmiObject Win32_Process | Where-Object { ($_.Name -eq 'python.exe' -and $_.CommandLine -match 'uvicorn') -or ($_.Name -eq 'node.exe' -and $_.CommandLine -match 'vite') } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
timeout /t 3 /nobreak > nul

echo [2/4] Arrancando Backend en :8000 ...
start "Backend :8000" cmd /k ".venv\Scripts\python.exe -m uvicorn backend.main:app --host 0.0.0.0 --port 8000"

timeout /t 4 /nobreak > nul

echo [3/4] Arrancando Frontend en :5173 ...
start "Frontend :5173" cmd /k "cd /d "%~dp0frontend" && npm run dev -- --port 5173"

timeout /t 5 /nobreak > nul

echo [4/4] Abriendo navegador...
start http://localhost:5173

echo.
echo  Backend  ^>  http://localhost:8000
echo  Frontend ^>  http://localhost:5173
echo.
echo IMPORTANTE: Para aplicar cambios cierra las ventanas y vuelve a abrir start.bat
echo Presiona cualquier tecla para cerrar este launcher
pause > nul
