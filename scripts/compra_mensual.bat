@echo off
REM ================================================================
REM  Compra mensual de ETF (SPYB 70 % + SMHB 30 %) - doble clic
REM  Te pregunta cuanto vas a invertir, cuanto tienes y los precios,
REM  y te dice cuanto comprar de cada uno. NO compra nada por ti.
REM ================================================================
chcp 65001 >nul
set PYTHONUTF8=1
cd /d "%~dp0\.."

where python >nul 2>nul
if errorlevel 1 (
  echo No encuentro Python. Instala Python desde https://www.python.org/downloads/
  echo y marca la casilla "Add python.exe to PATH".
  pause
  exit /b 1
)
if not exist .venv (
  echo Preparando por primera vez...
  python -m venv .venv || goto :error
  call .venv\Scripts\activate.bat
  python -m pip install --quiet -e . || goto :error
) else (
  call .venv\Scripts\activate.bat
)

echo.
python -m fxbot.portfolio.dca || goto :error
echo.
pause
exit /b 0

:error
echo.
echo Algo fallo. Copia el mensaje de arriba y mandalo.
pause
exit /b 1
