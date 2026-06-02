# 🔵 JARVIS 2.0 - Asistente IA tipo Iron Man

Sistema profesional de asistente de voz inteligente con interfaz holográfica futurista. Funciona en PC (backend) + Móvil (frontend).

```
┌─────────────────────────────────────────┐
│  ⬤ J.A.R.V.I.S v2.0                   │
│                                         │
│  🎤 Habla al móvil                    │
│  ⚡ Procesa en el PC                    │
│  🔊 Responde con voz                   │
│                                         │
│  Claude 3.5 + GPT-4 + TTS              │
└─────────────────────────────────────────┘
```

---

## 🚀 Instalación Rápida (Windows)

### Requisitos previos:
- ✅ Windows 10/11
- ✅ Python 3.9+ ([Descargar](https://www.python.org/downloads/))
- ✅ Node.js 16+ ([Descargar](https://nodejs.org/))
- ✅ API Keys: Claude + OpenAI

---

## 📋 Paso 1: Descargar el proyecto

```bash
# Clonar o descargar archivos
# Crear carpeta JARVIS_2.0 y descargar todos los archivos allí
```

---

## 🔑 Paso 2: Obtener las claves API

### Claude (Anthropic):
1. Ir a: https://console.anthropic.com
2. Click en "API Keys"
3. Click en "Create new secret key"
4. Copiar la clave (empieza con `sk-ant-`)

### OpenAI (GPT-4):
1. Ir a: https://platform.openai.com/account/api-keys
2. Click en "Create new secret key"
3. Copiar la clave (empieza con `sk-`)

---

## ⚙️ Paso 3: Configurar las claves

1. **Abre el archivo `.env.example`** (está en la carpeta del proyecto)

2. **Reemplaza las claves:**
   ```env
   CLAUDE_API_KEY=sk-ant-tu-clave-aqui
   OPENAI_API_KEY=sk-tu-clave-aqui
   ```

3. **Guarda el archivo** (Ctrl+S)

4. **Renombra a `.env`** (sin la extensión `.example`)

---

## 📦 Paso 4: Instalar dependencias

**Haz doble click en `instalar.bat`**

Este script:
- ✅ Verifica Python
- ✅ Crea entorno virtual
- ✅ Instala dependencias Python (FastAPI, WebSocket, etc.)
- ✅ Prepara todo para ejecutar

**Espera a que termine (2-3 minutos aprox)**

---

## 🚀 Paso 5: Ejecutar el sistema

### Terminal 1 - Backend:
```bash
Haz doble click en: iniciar_backend.bat
```

Deberías ver:
```
╔════════════════════════════════════════════╗
║    🔵 JARVIS 2.0 - Backend Iniciado 🔵    ║
║  WebSocket: ws://localhost:8000/ws        ║
║  API REST:  http://localhost:8000/api/..  ║
╚════════════════════════════════════════════╝
```

### Terminal 2 - Frontend:
```bash
Haz doble click en: iniciar_frontend.bat
```

Debería abrir automáticamente en: `http://localhost:3000`

---

## 🎮 Usar JARVIS

### En la interfaz:

1. **Botón grande azul 🎤**: Presiona para hablar
2. **Clic en CLAUDE/GPT-4**: Elige qué IA usar
3. **Habla natural**: "¿Cuál es la capital de Francia?"
4. **Escucha la respuesta**: JARVIS responde en audio

### Funciones:
- ✅ Reconocimiento de voz (Web Speech API)
- ✅ Procesamiento con Claude o GPT-4
- ✅ Síntesis de voz (respuesta hablada)
- ✅ Historial de conversaciones
- ✅ Interfaz futurista tipo Iron Man

---

## 🔧 Solucionar problemas

### Error: "Python no está instalado"
```
→ Instala desde: https://www.python.org/downloads/
→ IMPORTANTE: Marca "Add Python to PATH"
```

### Error: "node: command not found"
```
→ Instala Node.js desde: https://nodejs.org/
→ Reinicia Windows después de instalar
```

### Error: "WebSocket connection failed"
```
→ Asegúrate de que iniciar_backend.bat está corriendo
→ Verifica que el puerto 8000 no esté en uso
→ Abre una terminal CMD y ejecuta: netstat -ano | findstr :8000
```

### Error: "API Key inválida"
```
→ Verifica que las claves en .env sean correctas
→ Verifica que no haya espacios extras
→ Prueba generar claves nuevas
```

### El audio no funciona
```
→ Verifica los permisos de micrófono del navegador
→ Click en el icono de candado (izquierda de la URL)
→ Permite acceso al micrófono
```

### React no compila
```
→ Abre cmd en la carpeta del proyecto
→ Ejecuta: npm cache clean --force
→ Ejecuta: npm install
→ Ejecuta: npm start
```

---

## 📱 Usar desde otro dispositivo (móvil/tablet)

### En la misma red WiFi:

1. **En la terminal del frontend**, busca la IP:
   ```
   En lugar de localhost:3000 verás algo como:
   http://192.168.X.X:3000
   ```

2. **En el móvil**, abre un navegador y ve a esa URL

3. **En el backend**, cambia `localhost` por tu IP:
   ```python
   # Cambia esto en siri_2.0_backend.py
   ws://localhost:8000  →  ws://192.168.X.X:8000
   ```

---

## 🌐 Estructura del proyecto

```
JARVIS_2.0/
├── siri_2.0_backend.py          ← Backend FastAPI
├── package.json                 ← Dependencias React
├── requirements.txt             ← Dependencias Python
├── .env                        ← Claves API (crea este)
├── .env.example                ← Template (referencia)
├── instalar.bat                ← Script instalación
├── iniciar_backend.bat         ← Ejecuta servidor
├── iniciar_frontend.bat        ← Ejecuta React
├── JARVIS_Frontend.jsx         ← Componente React
├── src/
│   ├── index.js
│   └── JARVIS_Frontend.jsx
├── public/
│   └── index.html
└── venv/                       ← Entorno virtual (auto)
```

---

## 🔐 Seguridad

- ✅ Las claves API están en `.env` (no en código)
- ✅ WebSocket con validación
- ✅ CORS configurado
- ✅ Historial local (opcional enviarlo a BD)

---

## 🎯 Características

- 🎤 Reconocimiento de voz (Chrome, Edge, Safari)
- 🧠 IA dual: Claude 3.5 Sonnet + GPT-4
- 🔊 Síntesis de voz natural (español)
- 🌐 WebSocket en tiempo real
- 📊 Historial de conversaciones
- 🎨 Interfaz holográfica futurista
- 📱 Responsive (móvil, tablet, PC)
- ⚡ Latencia baja (ms)

---

## 💡 Próximas mejoras

```
[ ] Comando por voz para controlar PC
[ ] Integración con Spotify/YouTube
[ ] Recordatorio de notas
[ ] Control de luces smart
[ ] Predicción de palabras
[ ] Guardado en base de datos
[ ] App nativa Android/iOS
```

---

## 🆘 Soporte

Si algo no funciona:

1. **Lee la sección "Solucionar problemas"** arriba
2. **Verifica los logs** en la terminal
3. **Revisa que las claves API sean válidas**
4. **Intenta cerrar y abrir todo de nuevo**

---

## 📝 Licencia

Libre para uso personal y educativo.

---

## 🚀 ¡Disfruta tu JARVIS!

```
⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜
⬜🔵🔵🔵🔵🔵🔵🔵🔵⬜
⬜🔵⬛⬛⬛⬛⬛⬛🔵⬜
⬜🔵⬛ JARVIS ⬛🔵⬜
⬜🔵⬛⬛⬛⬛⬛⬛🔵⬜
⬜🔵🔵🔵🔵🔵🔵🔵🔵⬜
⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜
```

**Creado con ❤️ para Iron Man fans**
