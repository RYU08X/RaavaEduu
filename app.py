import os
import logging
import re
import tempfile
import uuid
import asyncio
from typing import Dict, List, Optional

# --- FASTAPI & ASYNC ---
from fastapi import FastAPI, UploadFile, File, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
import aiohttp
import edge_tts

# =============================================================================
# ⚙️ CONFIGURACIÓN
# =============================================================================

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# VARIABLES DE ENTORNO (Cámbialas por las tuyas o usa un archivo .env)
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY", "TU_CLAVE_DEEPGRAM")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "TU_CLAVE_OPENROUTER")

# MODELO: Usamos Gemini 2.0 Flash (Ideal para razonamiento rápido y barato)
MODEL_NAME = "google/gemini-2.0-flash-001"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

app = FastAPI()

# CORS: Permite que tu Frontend (React) se conecte sin errores
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =============================================================================
# 📚 PEDAGOGÍA: EL MAPA DE APRENDIZAJE
# =============================================================================

# Definimos los "Hitos" o pasos para el tema "Fundamentos Algebraicos"
ALGEBRA_CURRICULUM = [
    {
        "id": "reales",
        "tema": "Hito 1: Los Números Reales",
        "objetivo": "Entender que los números reales incluyen TODO (enteros, decimales, fracciones).",
        "meta_salida": "El usuario debe reconocer que tanto 5 como 3.14 son reales."
    },
    {
        "id": "variables",
        "tema": "Hito 2: Variables (Cajas Etiquetadas)",
        "objetivo": "Desmitificar la 'x'. Explicar que es solo un contenedor o espacio que cambia de valor.",
        "meta_salida": "Entender la analogía de contenedor/caja."
    },
    {
        "id": "lenguaje",
        "tema": "Hito 3: Traducción al Lenguaje Algebraico",
        "objetivo": "Traducir español a matemáticas (ej: 'El doble de un número' -> 2x).",
        "meta_salida": "Poder crear una expresión simple."
    },
    {
        "id": "cierre",
        "tema": "Cierre de Lección",
        "objetivo": "Felicitar al usuario, resumir lo aprendido y motivar.",
        "meta_salida": "Despedida."
    }
]

# Configuración de las personalidades de la IA
MENTORS_CONFIG = {
    "raava": {
        "name": "Raava",
        "voice": "es-MX-DaliaNeural",
        "base_prompt": "Eres Raava, una mentora IA empática, paciente y clara. Tu objetivo es guiar sin juzgar."
    },
    "newton": {
        "name": "Isaac Newton",
        "voice": "es-MX-JorgeNeural",
        "base_prompt": "Eres Sir Isaac Newton. Eres riguroso y te obsesiona la precisión. Usas analogías físicas."
    },
    "einstein": {
        "name": "Albert Einstein",
        "voice": "es-ES-AlvaroNeural",
        "base_prompt": "Eres Albert Einstein. Eres humilde, curioso y usas analogías visuales y experimentos mentales."
    }
}

# 🧠 MEMORIA VOLÁTIL (Se reinicia si apagas el servidor)
# Guarda el progreso del usuario: { session_id: { step_index, history, user_data... } }
sessions: Dict[str, dict] = {}

# =============================================================================
# 📝 MODELOS DE DATOS (PYDANTIC)
# =============================================================================

class InitSessionRequest(BaseModel):
    session_id: str
    mentor_id: str = "raava"
    user_data: dict  # Recibe {nombre, pasion, meta, aprendizaje}
    current_topic: str = "General"

class ChatRequest(BaseModel):
    session_id: str
    message: str
    mentor_id: str = "raava"
    user_context: Optional[dict] = {}

class TalkRequest(BaseModel):
    text: str
    mentor_id: str = "raava"

# =============================================================================
# 🛠️ FUNCIONES AUXILIARES
# =============================================================================

def get_system_prompt(session, mentor_config):
    """
    Construye el 'cerebro' de la IA para este turno específico,
    combinando el currículo con los datos personales del usuario.
    """
    
    # 1. Determinar el Hito actual
    step_idx = session["step_index"]
    if step_idx >= len(ALGEBRA_CURRICULUM):
        current_step = ALGEBRA_CURRICULUM[-1] # Se queda en el cierre si ya acabó
    else:
        current_step = ALGEBRA_CURRICULUM[step_idx]

    # 2. Extraer datos del usuario (Personalización)
    user_data = session.get("user_data", {})
    nombre = user_data.get("nombre", "Estudiante")
    pasion = user_data.get("pasion", "aprender")
    meta = user_data.get("meta", "entender el tema")
    estilo = user_data.get("aprendizaje", "visual")

    # 3. Construir el Prompt Maestro
    prompt = f"""
    {mentor_config['base_prompt']}
    
    --- CONTEXTO DEL ALUMNO ---
    Nombre: {nombre}
    Pasión/Interés: {pasion} (IMPORTANTE: Usa esto para tus analogías).
    Meta del Curso: "{meta}" (Si es un examen, sé preciso. Si es curiosidad, sé divertido).
    Estilo de Aprendizaje: {estilo}.

    --- ESTADO DE LA LECCIÓN ---
    Tema Actual: {current_step['tema']}
    Objetivo Docente: {current_step['objetivo']}
    Criterio de Éxito: {current_step['meta_salida']}

    --- TUS INSTRUCCIONES ---
    1. Explica el concepto brevemente (máx 3 oraciones).
    2. Usa una analogía relacionada con "{pasion}".
    3. Conversa, no des una cátedra. Haz una pregunta de comprobación al final.
    4. MOTOR DE AVANCE: Evalúa silenciosamente si el alumno entendió el concepto actual.
       - Si NO entendió: Explica de otra forma.
       - Si SÍ entendió (o dice "ok", "siguiente"): Termina tu respuesta escribiendo oculto: [[NEXT_TOPIC]]
    
    No digas [[NEXT_TOPIC]] en voz alta, es solo una señal para el sistema.
    """
    return prompt

def remove_temp_file(path: str):
    """Borra archivos de audio temporales para no llenar el disco."""
    try:
        os.remove(path)
    except Exception as e:
        logging.error(f"Error borrando archivo temporal {path}: {e}")

def clean_text_for_tts(text: str) -> str:
    """Limpia el texto para que la voz suene natural y fluida."""
    # Remover la etiqueta de control
    text = text.replace("[[NEXT_TOPIC]]", "")
    # Remover markdown (negritas, cursivas, bloques de código)
    text = re.sub(r'[*_`#]', '', text)
    # Remover espacios extra
    return text.strip()

# =============================================================================
# 🚀 ENDPOINTS (RUTAS)
# =============================================================================

@app.get("/")
async def health_check():
    return {"status": "online", "system": "Raava Edu Backend v2.0"}

# 1. INICIALIZAR SESIÓN
@app.post("/init_session")
async def init_session(req: InitSessionRequest):
    logging.info(f"🆕 Iniciando sesión para: {req.user_data.get('nombre')}")
    
    # Creamos el estado inicial en memoria
    sessions[req.session_id] = {
        "step_index": 0,       # Empezamos en el Hito 0
        "history": [],         # Historial vacío
        "user_data": req.user_data, # Guardamos nombre, pasion, meta, estilo
        "mentor_id": req.mentor_id
    }
    
    mentor = MENTORS_CONFIG.get(req.mentor_id, MENTORS_CONFIG["raava"])
    pasion = req.user_data.get("pasion", "cosas interesantes")
    
    # Mensaje de bienvenida inicial (No consume LLM para ser instantáneo)
    welcome_text = (
        f"Hola {req.user_data.get('nombre')}. Soy {mentor['name']}. "
        f"Me encanta que te guste {pasion}. Vamos a usar eso para entender los Fundamentos Algebraicos. "
        "Empecemos: ¿Sabes qué es un número real?"
    )
    
    # Guardamos este primer turno en el historial
    sessions[req.session_id]["history"].append({"role": "assistant", "content": welcome_text})
    
    return {"status": "success", "message": "Sesión creada"}

# 2. CHAT INTELIGENTE (TEXTO)
@app.post("/chat")
async def chat(req: ChatRequest):
    try:
        # Recuperación de errores: Si el ID no existe (reinicio del server), creamos uno básico
        if req.session_id not in sessions:
            sessions[req.session_id] = {
                "step_index": 0, 
                "history": [], 
                "user_data": req.user_context or {}, 
                "mentor_id": req.mentor_id
            }
        
        session = sessions[req.session_id]
        mentor_config = MENTORS_CONFIG.get(req.mentor_id, MENTORS_CONFIG["raava"])
        
        # 1. Construir el Prompt Dinámico
        system_prompt = get_system_prompt(session, mentor_config)
        
        # 2. Preparar historial para enviar a la API
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(session["history"][-6:]) # Solo últimos 6 mensajes (ahorro de tokens y velocidad)
        messages.append({"role": "user", "content": req.message})
        
        # 3. Llamada a OpenRouter (Gemini)
        async with aiohttp.ClientSession() as client:
            payload = {
                "model": MODEL_NAME,
                "messages": messages,
                "temperature": 0.3, # Creatividad baja para que sea preciso y rápido
                "max_tokens": 250
            }
            headers = {
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://raava.edu"
            }
            
            async with client.post(OPENROUTER_URL, json=payload, headers=headers) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    logging.error(f"Error OpenRouter: {error_text}")
                    return JSONResponse(status_code=500, content={"error": "La IA está pensando demasiado."})
                
                data = await resp.json()
                reply_full = data["choices"][0]["message"]["content"]

        # 4. LÓGICA DE AVANCE (La "Etiqueta Oculta")
        final_reply = reply_full
        
        if "[[NEXT_TOPIC]]" in reply_full:
            # ¡Eureka! El alumno entendió.
            logging.info(f"✅ AVANCE DETECTADO en sesión {req.session_id}")
            session["step_index"] += 1 # Pasamos al siguiente Hito
            final_reply = reply_full.replace("[[NEXT_TOPIC]]", "").strip() # Limpiamos la etiqueta
            
        # 5. Actualizar historial
        session["history"].append({"role": "user", "content": req.message})
        session["history"].append({"role": "assistant", "content": final_reply})

        return {"reply": final_reply}

    except Exception as e:
        logging.error(f"Chat error: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})

# 3. LISTEN (AUDIO -> TEXTO)
@app.post("/listen")
async def listen(audio: UploadFile = File(...)):
    try:
        # Deepgram API URL
        url = "https://api.deepgram.com/v1/listen?model=nova-2&smart_format=true&language=es"
        headers = {
            "Authorization": f"Token {DEEPGRAM_API_KEY}",
            "Content-Type": audio.content_type or "audio/wav"
        }
        
        # Leer el archivo recibido
        content = await audio.read()
        
        async with aiohttp.ClientSession() as client:
            async with client.post(url, headers=headers, data=content) as resp:
                if resp.status != 200:
                    logging.error("Error en Deepgram")
                    return {"text": ""}
                
                data = await resp.json()
                # Extraer la transcripción
                transcript = data.get('results', {}).get('channels', [{}])[0].get('alternatives', [{}])[0].get('transcript', "")
                logging.info(f"🎤 Escuchado: {transcript}")
                
        return {"text": transcript}

    except Exception as e:
        logging.error(f"Listen error: {e}")
        return {"text": ""}

# 4. TALK (TEXTO -> AUDIO)
@app.post("/talk")
async def talk(req: TalkRequest, background_tasks: BackgroundTasks):
    try:
        # Limpiar texto para que la voz no lea símbolos raros
        text_safe = clean_text_for_tts(req.text)
        
        if not text_safe:
            return JSONResponse(status_code=400, content={"error": "Texto vacío"})

        # Obtener voz del mentor
        mentor = MENTORS_CONFIG.get(req.mentor_id, MENTORS_CONFIG["raava"])
        voice = mentor["voice"]

        # Crear archivo temporal
        filename = f"tts_{uuid.uuid4().hex}.mp3"
        temp_path = os.path.join(tempfile.gettempdir(), filename)

        # Generar audio con Edge-TTS
        communicate = edge_tts.Communicate(text_safe, voice)
        await communicate.save(temp_path)

        # Programar borrado del archivo después de enviarlo (limpieza automática)
        background_tasks.add_task(remove_temp_file, temp_path)

        # Enviar archivo de audio
        return FileResponse(temp_path, media_type="audio/mpeg", filename="voice.mp3")

    except Exception as e:
        logging.error(f"Talk error: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})

# Para ejecutar en local:
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
