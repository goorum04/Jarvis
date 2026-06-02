@echo off
REM ===============================================
REM JARVIS 2.0 - Frontend React
REM ===============================================

echo.
echo ╔════════════════════════════════════════════╗
echo ║    🎨 JARVIS 2.0 - Frontend (React)      ║
echo ╚════════════════════════════════════════════╝
echo.

REM Verificar si Node.js está instalado
node --version >nul 2>&1
if errorlevel 1 (
    echo ❌ ERROR: Node.js no está instalado
    echo.
    echo Descarga Node.js desde: https://nodejs.org/
    echo Recomienda: Versión LTS (Long Term Support)
    echo.
    pause
    exit /b 1
)

echo ✅ Node.js encontrado
node --version
npm --version
echo.

REM Instalar dependencias npm si no existen
if not exist node_modules (
    echo 📥 Instalando dependencias de npm...
    echo    (esto puede tomar 2-3 minutos la primera vez)
    echo.
    call npm install
    
    if errorlevel 1 (
        echo ❌ Error instalando dependencias npm
        pause
        exit /b 1
    )
    echo ✅ Dependencias npm instaladas
    echo.
)

echo 🚀 Iniciando servidor React...
echo.
echo ╔════════════════════════════════════════════╗
echo ║   Frontend escuchando en:                 ║
echo ║   http://localhost:3000                   ║
echo ║                                           ║
echo ║   ⚠️  IMPORTANTE:                          ║
echo ║   Backend debe estar corriendo en otra    ║
echo ║   terminal en: http://localhost:8000      ║
echo ╚════════════════════════════════════════════╝
echo.
echo Presiona CTRL+C para detener el servidor
echo.

call npm start

if errorlevel 1 (
    echo.
    echo ❌ Error ejecutando React
    echo.
    echo Soluciones:
    echo - Verifica que tengas Node.js v14+ instalado
    echo - Intenta: npm install (de nuevo)
    echo - Intenta: npm cache clean --force
    echo.
    pause
)
