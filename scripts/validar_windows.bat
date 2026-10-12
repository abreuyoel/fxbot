@echo off
REM ================================================================
REM  fxbot - Fase 1 en Windows con doble clic
REM  1) Abre MetaTrader 5 e inicia sesion en tu cuenta DEMO de FP Markets
REM  2) Doble clic en este archivo
REM  3) Al terminar, manda el archivo resultados\resumen.json
REM  Este proceso solo LEE precios: no abre ninguna operacion.
REM ================================================================
chcp 65001 >nul
set PYTHONUTF8=1
cd /d "%~dp0\.."

where python >nul 2>nul
if errorlevel 1 (
  echo No encuentro Python. Instala Python 3.12 desde https://www.python.org/downloads/
  echo y marca la casilla "Add python.exe to PATH". Luego vuelve a abrir este archivo.
  pause
  exit /b 1
)

if not exist .venv (
  echo Creando entorno de Python...
  python -m venv .venv || goto :error
)
call .venv\Scripts\activate.bat

echo Instalando dependencias...
python -m pip install --quiet --upgrade pip
python -m pip install --quiet -e ".[mt5]" || goto :error

echo.
echo Descargando historico desde MetaTrader 5 (puede tardar unos minutos)...
python scripts\descargar_datos_mt5.py --simbolos EURUSD GBPUSD USDJPY --desde 2012-01-01 || goto :error

if not exist resultados mkdir resultados
echo.
echo Corriendo el laboratorio: backtest + walk-forward + Monte Carlo (5-10 minutos)...
python -m fxbot.lab.run --csv datos\EURUSD_H1.csv datos\GBPUSD_H1.csv datos\USDJPY_H1.csv --tf 1h --capital 500 --walkforward --salida resultados > resultados\reporte.txt 2>&1
if errorlevel 1 (
  type resultados\reporte.txt
  goto :error
)
type resultados\reporte.txt

echo.
echo ================================================================
echo  Listo. Manda estos dos archivos:
echo    resultados\resumen.json
echo    resultados\reporte.txt
echo ================================================================
pause
exit /b 0

:error
echo.
echo Algo fallo. Copia el mensaje de arriba y mandalo.
pause
exit /b 1
