import os
import logging
import json
import re
import tempfile
import asyncio
from typing import Dict, List, Optional
import uuid

# --- FASTAPI & ASYNC ---
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel
import aiohttp
import edge_tts

# =============================================================================
# CONFIGURACIÓN
# =============================================================================

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Variables de Entorno
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY", "")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# 🚀 CAMBIO DE MODELO: Usamos Gemini Flash (Muy rápido y bueno razonando)
# Alternativa si falla: "meta-llama/llama-3-8b-instruct:free"
MODEL_NAME = "google/gemini-2.0-flash-001"

app = FastAPI()

# CORS (Crucial para que tu frontend de React se conecte)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =============================================================================
# 🧠 CEREBRO Y ESTADO (PEDAGOGÍA)
# =============================================================================

# Definición del Currículo
TOPIC_CURRICULUM = {
    "Pensamiento Matemático": [
        {"tema": "Introducción y Datos vs Opinión", "objetivo": "Que el usuario entienda que un dato es medible y una opinión es subjetiva."},
        {"tema": "Tipos de Gráficas", "objetivo": "Diferenciar cuándo usar gráfica de barras vs pastel."},
        {"tema": "Medidas de Tendencia Central", "objetivo": "Calcular la media en un ejemplo de la vida real."}
    ],
    "General": [
        {"tema": "Exploración", "objetivo": "Responder dudas generales del usuario."}
    ]
}

MENTORS_CONFIG = {
    "raava": {
        "name": "Raava",
        "voice": "es-MX-DaliaNeural",
        "style": "Eres Raava, una mentora IA paciente. Tu método es socrático: haces preguntas para que el alumno descubra la respuesta."
    },
    "newton": {
        "name": "Isaac Newton",
        "voice": "es-MX-JorgeNeural",
        "style": "Eres Isaac Newton. Exiges precisión. Si el alumno es vago, corrígelo. Usa analogías de física."
    },
    "einstein": {
        "name": "Albert Einstein",
        "voice": "es-ES-AlvaroNeural",
        "style": "Eres Einstein. Usa la imaginación. Explica cosas complejas con trenes, elevadores o luz."
    }
}

# 💾 MEMORIA RAM (Estado de la sesión)
# Guardamos: Historial de chat y Índice del Currículo actual
sessions: Dict[str, dict] = {}

# =============================================================================
# MODELOS DE DATOS (Pydantic para validación automática)
# =============================================================================
class InitSessionRequest(BaseModel):
    session_id: str
    mentor_id: str = "raava"
    user_data: dict = {}
    current_topic: str = "General"

class ChatRequest(BaseModel):
    session_id: str
    message: str
    mentor_id: str = "raava"
    user_context: Optional[dict] = {}
    current_topic: Optional[str] = "General"

class TalkRequest(BaseModel):
    text: str
    mentor_id: str = "raava"

# =============================================================================
# RUTAS
# =============================================================================

@app.get("/")
async def health_check():
    return {"status": "online", "engine": "FastAPI + Gemini Flash"}

# 1. INICIALIZAR SESIÓN
@app.post("/init_session")
async def init_session(req: InitSessionRequest):
    try:
        logging.info(f"🆕 Iniciando sesión {req.session_id}")
        
        # Determinar qué lista de temas usar
        topic_key = "General"
        for key in TOPIC_CURRICULUM:
            if key in req.current_topic:
                topic_key = key
                break
        
        # Inicializar estado
        sessions[req.session_id] = {
            "curriculum_key": topic_key,
            "step_index": 0, # Empezamos en el tema 0
            "history": [],
            "user_name": req.user_data.get("nombre", "Estudiante"),
            "user_passion": req.user_data.get("pasion", "aprender")
        }
        
        mentor = MENTORS_CONFIG.get(req.mentor_id, MENTORS_CONFIG["raava"])
        welcome_msg = f"Hola {sessions[req.session_id]['user_name']}. Soy {mentor['name']}. Vamos a aprender sobre {req.current_topic}. ¿Listo?"
        
        # Guardar bienvenida en historial para contexto
        sessions[req.session_id]["history"].append({"role": "assistant", "content": welcome_msg})
        
        return {"status": "success", "message": "Sesión lista"}

    except Exception as e:
        logging.error(f"Error init: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})

# 2. CHAT (CON LÓGICA DE ESTADO)
@app.post("/chat")
async def chat(req: ChatRequest):
    try:
        # Recuperar o crear sesión
        if req.session_id not in sessions:
            sessions[req.session_id] = {
                "curriculum_key": "General", 
                "step_index": 0, 
                "history": [], 
                "user_name": "Estudiante",
                "user_passion": "General"
            }
        
        session = sessions[req.session_id]
        
        # --- LÓGICA PEDAGÓGICA ---
        # 1. Obtener el objetivo actual
        curriculum = TOPIC_CURRICULUM.get(session["curriculum_key"], TOPIC_CURRICULUM["General"])
        current_step = curriculum[session["step_index"]] if session["step_index"] < len(curriculum) else curriculum[-1]
        
        # 2. Construir System Prompt Dinámico (Esto reduce la latencia y mejora la enseñanza)
        mentor_style = MENTORS_CONFIG.get(req.mentor_id, MENTORS_CONFIG["raava"])["style"]
        
        system_prompt = f"""
        {mentor_style}
        
        ESTADO ACTUAL DE LA CLASE:
        Alumno: {session['user_name']} (Le gusta: {session['user_passion']})
        Tema Actual: {current_step['tema']}
        Objetivo Docente: {current_step['objetivo']}
        
        REGLAS DE RESPUESTA:
        1. NO des explicaciones largas. Máximo 2 oraciones por turno.
        2. NO pases al siguiente tema todavía. Céntrate SOLO en el objetivo actual.
        3. Sé Socrático: Haz una pregunta al final para verificar que entendió.
        4. Si el alumno responde bien, felicítalo brevemente.
        """
        
        # 3. Preparar mensajes para la API
        messages_payload = [{"role": "system", "content": system_prompt}]
        # Añadir últimos 6 mensajes del historial (para no saturar contexto y ahorrar tokens)
        messages_payload.extend(session["history"][-6:])
        messages_payload.append({"role": "user", "content": req.message})

        # 4. Llamada ASÍNCRONA a OpenRouter (Clave para velocidad en FastAPI)
        async with aiohttp.ClientSession() as client:
            payload = {
                "model": MODEL_NAME,
                "messages": messages_payload,
                "temperature": 0.3, # Baja temperatura para que sea más rápido y preciso
                "max_tokens": 250   # Limitamos respuesta para forzar brevedad
            }
            headers = {
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://raava.edu",
            }
            
            async with client.post(OPENROUTER_URL, json=payload, headers=headers) as response:
                if response.status != 200:
                    err_text = await response.text()
                    logging.error(f"OpenRouter Error: {err_text}")
                    return {"reply": "Estoy pensando demasiado... pregúntame de nuevo."}
                
                result = await response.json()
                reply = result["choices"][0]["message"]["content"]

        # Actualizar historial
        session["history"].append({"role": "user", "content": req.message})
        session["history"].append({"role": "assistant", "content": reply})

        # --- LÓGICA DE AVANCE (Muy simple para Beta) ---
        # Si la respuesta del alumno fue muy positiva o la IA usó palabras de cierre,
        # podríamos incrementar el índice. Por ahora, lo dejamos manual o basado en longitud
        # para no complicar el código "beta".
        # Idea futura: Usar un "tool call" para que la IA decida cuándo avanzar.

        return {"reply": reply}

    except Exception as e:
        logging.error(f"Chat error: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})

# 3. LISTEN (Audio a Texto - Asíncrono)
@app.post("/listen")
async def listen(audio: UploadFile = File(...)):
    try:
        # Deepgram API directo
        url = "https://api.deepgram.com/v1/listen?model=nova-2&smart_format=true&language=es"
        headers = {
            "Authorization": f"Token {DEEPGRAM_API_KEY}",
            "Content-Type": audio.content_type or "audio/wav"
        }
        
        # Leer archivo en memoria
        content = await audio.read()
        
        async with aiohttp.ClientSession() as client:
            async with client.post(url, headers=headers, data=content) as response:
                if response.status != 200:
                    return {"text": ""}
                data = await response.json()
                transcript = data['results']['channels'][0]['alternatives'][0]['transcript']
                
        return {"text": transcript}

    except Exception as e:
        logging.error(f"Listen error: {e}")
        return {"text": ""}

# 4. TALK (Texto a Voz - Asíncrono)
@app.post("/talk")
async def talk(req: TalkRequest):
    try:
        # 1. Limpieza de texto (Crucial: los asteriscos del LLM causan el error 403)
        clean_text = re.sub(r'[*#`_~-]', '', req.text)
        
        # 2. Obtener la voz del mentor configurado
        mentor = MENTORS_CONFIG.get(req.mentor_id, MENTORS_CONFIG["raava"])
        voice = mentor["voice"]

        # 3. Ruta temporal segura (Usa /tmp para evitar errores de permisos)
        filename = f"voice_{uuid.uuid4().hex}.mp3"
        temp_path = os.path.join(tempfile.gettempdir(), filename)

        # 4. Lógica de generación (Igual a la de denuncia pero Async nativo)
        communicate = edge_tts.Communicate(clean_text, voice)
        await communicate.save(temp_path)

        # 5. Envío del archivo
        return FileResponse(
            temp_path, 
            media_type="audio/mpeg", 
            filename="mentor_voice.mp3"
        )

    except Exception as e:
        logging.error(f"Error en Talk: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})

# Para correr en local
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
