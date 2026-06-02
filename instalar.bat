@echo off
REM ===============================================
REM JARVIS 2.0 - Instalador Windows
REM ===============================================

echo.
echo ╔════════════════════════════════════════════╗
echo ║  JARVIS 2.0 - Instalador de Dependencias  ║
echo ╚════════════════════════════════════════════╝
echo.

REM Verificar si Python está instalado
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ ERROR: Python no está instalado o no está en PATH
    echo.
    echo Descarga Python desde: https://www.python.org/downloads/
    echo Asegúrate de marcar "Add Python to PATH" durante la instalación
    pause
    exit /b 1
)

echo ✅ Python encontrado
python --version
echo.

REM Crear entorno virtual
echo 📦 Creando entorno virtual...
python -m venv venv
call venv\Scripts\activate.bat

echo ✅ Entorno virtual activado
echo.

REM Instalar dependencias
echo 📥 Instalando dependencias Python...
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt

if errorlevel 1 (
    echo ❌ Error instalando dependencias
    pause
    exit /b 1
)

echo.
echo ✅ Dependencias Python instaladas correctamente
echo.

REM Configurar variables de entorno
if not exist .env (
    echo 🔧 Creando archivo .env...
    copy .env.example .env
    echo ⚠️  IMPORTANTE: Edita el archivo .env con tus claves API
    echo   - CLAUDE_API_KEY
    echo   - OPENAI_API_KEY
)

echo.
echo ════════════════════════════════════════════
echo ✅ INSTALACIÓN COMPLETADA
echo ════════════════════════════════════════════
echo.
echo PRÓXIMOS PASOS:
echo.
echo 1. Edita el archivo .env con tus claves API:
echo    - Copia tu CLAUDE_API_KEY desde: https://console.anthropic.com
echo    - Copia tu OPENAI_API_KEY desde: https://platform.openai.com
echo.
echo 2. Abre una terminal y ejecuta:
echo    call venv\Scripts\activate.bat
echo    python siri_2.0_backend.py
echo.
echo 3. En otra terminal, ejecuta el frontend:
echo    npm install
echo    npm start
echo.
pause
