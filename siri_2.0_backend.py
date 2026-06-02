"""
JARVIS 2.0 - Backend FastAPI
Sistema de asistente IA inteligente con voz en tiempo real
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import asyncio
import json
import os
from dotenv import load_dotenv
import anthropic
import openai
from google.cloud import texttospeech
import speech_recognition as sr
import base64
from typing import Optional
import logging

# Configuración
load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# APIs
CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
# Debe ser la RUTA al archivo .json de credenciales, no el contenido
GOOGLE_CLOUD_CREDENTIALS_PATH = os.getenv("GOOGLE_CLOUD_CREDENTIALS_PATH")

# Inicializar clientes
client_anthropic = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
client_openai = openai.OpenAI(api_key=OPENAI_API_KEY)

# Si tienes credenciales de Google Cloud
try:
    if GOOGLE_CLOUD_CREDENTIALS_PATH:
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = GOOGLE_CLOUD_CREDENTIALS_PATH
    tts_client = texttospeech.TextToSpeechClient()
except Exception:
    tts_client = None
    logger.warning("Google Cloud TTS no disponible, usaremos respaldo")

app = FastAPI(title="JARVIS 2.0")

# CORS para móvil y PC
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Variables globales
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
    
    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
    
    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Error broadcasting: {e}")

manager = ConnectionManager()

# Sistema de conversación
conversation_history = []
MAX_HISTORY = 20  # Mantener últimos 20 mensajes

def add_to_history(role: str, content: str):
    """Agregar mensaje al historial"""
    conversation_history.append({"role": role, "content": content})
    if len(conversation_history) > MAX_HISTORY:
        conversation_history.pop(0)

async def process_with_claude(user_input: str, use_gpt: bool = False) -> str:
    """
    Procesar entrada con Claude o GPT
    """
    try:
        if use_gpt:
            logger.info(f"Procesando con GPT: {user_input}")
            response = client_openai.chat.completions.create(
                model="gpt-4-turbo",
                messages=[
                    {"role": "system", "content": "Eres JARVIS, el asistente de IA de Iron Man. Responde de forma concisa, profesional y futurista. Máximo 2-3 oraciones."},
                    *conversation_history[-5:],
                    {"role": "user", "content": user_input}
                ],
                temperature=0.7,
                max_tokens=150
            )
            reply = response.choices[0].message.content
        else:
            logger.info(f"Procesando con Claude: {user_input}")
            response = client_anthropic.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=150,
                system="Eres JARVIS, el asistente de IA de Iron Man. Responde de forma concisa, profesional y futurista. Máximo 2-3 oraciones.",
                messages=[
                    *conversation_history[-5:],
                    {"role": "user", "content": user_input}
                ]
            )
            reply = response.content[0].text
        
        add_to_history("user", user_input)
        add_to_history("assistant", reply)
        return reply
        
    except Exception as e:
        logger.error(f"Error procesando con IA: {e}")
        return "Lo siento, hubo un error procesando tu solicitud."

async def text_to_speech(text: str) -> Optional[bytes]:
    """
    Convertir texto a audio usando Google Cloud TTS
    Si no está disponible, usar fallback simple
    """
    try:
        if tts_client:
            synthesis_input = texttospeech.SynthesisInput(text=text)
            voice = texttospeech.VoiceSelectionParams(
                language_code="es-ES",
                name="es-ES-Neural2-A",
                ssml_gender=texttospeech.SsmlVoiceGender.MALE
            )
            audio_config = texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.MP3
            )
            
            response = tts_client.synthesize_speech(
                input=synthesis_input,
                voice=voice,
                audio_config=audio_config
            )
            return response.audio_content
    except Exception as e:
        logger.error(f"Error en TTS: {e}")
    
    # Fallback: usar pyttsx3 (TTS local)
    try:
        import pyttsx3
        engine = pyttsx3.init()
        engine.setProperty('rate', 150)
        engine.setProperty('volume', 1.0)
        
        # Para español
        engine.setProperty('voice', 'spanish')
        
        # Guardar a archivo temporal
        engine.save_to_file(text, '/tmp/response.mp3')
        engine.runAndWait()
        
        with open('/tmp/response.mp3', 'rb') as f:
            return f.read()
    except Exception as e:
        logger.error(f"Error en TTS fallback: {e}")
        return None

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    Endpoint WebSocket principal
    Recibe audio, procesa con IA, devuelve audio
    """
    await manager.connect(websocket)
    logger.info("Cliente conectado")
    
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            msg_type = message.get("type")
            
            if msg_type == "audio":
                # Recibir audio en base64
                audio_data = message.get("audio")
                use_gpt = message.get("use_gpt", False)
                
                try:
                    # Enviar estado: procesando
                    await websocket.send_json({
                        "type": "status",
                        "status": "processing",
                        "message": "Escuchando..."
                    })
                    
                    # Aquí iría el reconocimiento de voz
                    # Por ahora, recibimos texto directamente del cliente
                    user_text = message.get("text", "")
                    
                    if user_text:
                        # Procesar con IA
                        ai_response = await process_with_claude(user_text, use_gpt=use_gpt)
                        
                        # Convertir a voz
                        audio_bytes = await text_to_speech(ai_response)
                        
                        if audio_bytes:
                            audio_b64 = base64.b64encode(audio_bytes).decode('utf-8')
                            await websocket.send_json({
                                "type": "response",
                                "text": ai_response,
                                "audio": audio_b64,
                                "audio_type": "audio/mp3"
                            })
                        else:
                            await websocket.send_json({
                                "type": "response",
                                "text": ai_response,
                                "audio": None
                            })
                        
                        # Estado: listo
                        await websocket.send_json({
                            "type": "status",
                            "status": "ready",
                            "message": "Listo para escuchar"
                        })
                
                except Exception as e:
                    logger.error(f"Error procesando audio: {e}")
                    await websocket.send_json({
                        "type": "error",
                        "message": str(e)
                    })
            
            elif msg_type == "ping":
                await websocket.send_json({"type": "pong"})
    
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info("Cliente desconectado")
    except Exception as e:
        logger.error(f"Error WebSocket: {e}")
        manager.disconnect(websocket)

@app.get("/health")
async def health():
    """Health check"""
    return {
        "status": "online",
        "service": "JARVIS 2.0",
        "version": "1.0.0"
    }

@app.post("/api/chat")
async def chat(data: dict):
    """
    Endpoint REST alternativo para chat
    """
    user_input = data.get("text", "")
    use_gpt = data.get("use_gpt", False)
    
    if not user_input:
        return {"error": "No text provided"}
    
    response_text = await process_with_claude(user_input, use_gpt=use_gpt)
    audio_bytes = await text_to_speech(response_text)
    
    if audio_bytes:
        audio_b64 = base64.b64encode(audio_bytes).decode('utf-8')
        return {
            "text": response_text,
            "audio": audio_b64,
            "audio_type": "audio/mp3"
        }
    
    return {"text": response_text}

@app.get("/api/history")
async def get_history():
    """Obtener historial de conversación"""
    return {"history": conversation_history}

@app.delete("/api/history")
async def clear_history():
    """Limpiar historial"""
    global conversation_history
    conversation_history = []
    return {"message": "Historial borrado"}

if __name__ == "__main__":
    import uvicorn
    print("""
    ╔════════════════════════════════════════════════════════════╗
    ║          🔵 JARVIS 2.0 - Backend Iniciado 🔵              ║
    ║                                                            ║
    ║  WebSocket: ws://localhost:8000/ws                        ║
    ║  API REST:  http://localhost:8000/api/chat                ║
    ║  Health:    http://localhost:8000/health                  ║
    ║                                                            ║
    ║  Abre el frontend en: http://localhost:3000               ║
    ╚════════════════════════════════════════════════════════════╝
    """)
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        reload=True
    )
