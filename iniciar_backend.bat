@echo off
REM ===============================================
REM JARVIS 2.0 - Backend Server
REM ===============================================

echo.
echo ╔════════════════════════════════════════════╗
echo ║       🔵 JARVIS 2.0 - Backend Server     ║
echo ╚════════════════════════════════════════════╝
echo.

REM Verificar si .env existe
if not exist .env (
    echo ❌ ERROR: Archivo .env no encontrado
    echo.
    echo Por favor:
    echo 1. Copia .env.example a .env
    echo 2. Edita .env con tus claves API
    echo.
    pause
    exit /b 1
)

REM Activar entorno virtual
if not exist venv (
    echo ❌ ERROR: Entorno virtual no encontrado
    echo Por favor ejecuta primero: instalar.bat
    pause
    exit /b 1
)

call venv\Scripts\activate.bat

echo ✅ Entorno virtual activado
echo.

REM Ejecutar servidor
echo 🚀 Iniciando servidor FastAPI...
echo.
echo ╔════════════════════════════════════════════╗
echo ║   Backend escuchando en:                  ║
echo ║   http://localhost:8000                   ║
echo ║   ws://localhost:8000/ws                  ║
echo ╚════════════════════════════════════════════╝
echo.
echo 📱 Frontend debería estar en:
echo    http://localhost:3000
echo.

python siri_2.0_backend.py

if errorlevel 1 (
    echo.
    echo ❌ Error ejecutando el servidor
    echo.
    echo Soluciones comunes:
    echo - Verifica que las dependencias estén instaladas (pip install -r requirements.txt)
    echo - Verifica que .env tenga las claves API correctas
    echo - Verifica que el puerto 8000 no esté en uso
    echo.
    pause
)
