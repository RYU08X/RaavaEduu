import os
import io
import logging
import re
import json
import asyncio
from quart import Quart, request, jsonify, send_file, Response
from quart_cors import cors
import edge_tts
from openai import AsyncOpenAI # Cliente compatible con OpenRouter

# Configuración de Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- CONFIGURACIÓN DE APP & API KEYS ---
app = Quart(__name__)
app = cors(app, allow_origin="*")

# Configuración de OpenRouter
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
YOUR_SITE_URL = os.getenv("SITE_URL", "https://tua-app-en-render.onrender.com")
YOUR_APP_NAME = "AI Mentor App"

# Cliente Asíncrono apuntando a OpenRouter
client = AsyncOpenAI(
    api_key=OPENROUTER_API_KEY,
    base_url="https://openrouter.ai/api/v1",
)

# --- MODELO SELECCIONADO ---
# Versión GRATUITA de Llama 3.3 70B Instruct
MODEL_NAME = "meta-llama/llama-3.3-70b-instruct:free"

# --- ALMACENAMIENTO VOLÁTIL (RAM) ---
sessions = {}

# --- CONFIGURACIÓN DE MENTORES ---
MENTORS_CONFIG = {
    "newton": {
        "name": "Isaac Newton",
        "voice": "es-MX-JorgeNeural",
        "temperature": 0.3, 
        "system_instruction": """
        Eres Sir Isaac Newton (1643-1727).
        PERSONALIDAD: Arrogante pero brillante, formal, usas lenguaje ligeramente arcaico y académico. Te obsesiona la física, las matemáticas y la alquimia.
        ESTILO: Respuestas directas, lógicas. No toleras la ignorancia voluntaria.
        """,
    },
    "einstein": {
        "name": "Albert Einstein",
        "voice": "es-ES-AlvaroNeural",
        "temperature": 0.7,
        "system_instruction": """
        Eres Albert Einstein (1879-1955).
        PERSONALIDAD: Humilde, juguetón, despeinado intelectualmente. Valoras la imaginación sobre el conocimiento.
        ESTILO: Usas analogías visuales (trenes, elevadores). Hablas con asombro por el universo.
        """,
    },
    "raava": {
        "name": "Raava (IA)", 
        "voice": "es-MX-DaliaNeural", 
        "temperature": 0.6,
        "system_instruction": """
        Eres Raava, una mentora de IA avanzada, empática y paciente.
        PERSONALIDAD: Facilitadora, amable, clara. Tu objetivo es guiar sin juzgar.
        ESTILO: Moderno, uso de emojis ocasionales, muy estructurada pedagógicamente.
        """,
    }
}

def clean_text_for_tts(text):
    """Limpia el texto para que la voz no lea asteriscos, código o bloques de pensamiento."""
    clean = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL) 
    clean = re.sub(r'\*+', '', clean) # Markdown negrita/cursiva
    clean = re.sub(r'```.*?```', '', clean, flags=re.DOTALL) # Bloques de código
    clean = re.sub(r'[^\w\s,¿?.!áéíóúÁÉÍÓÚñÑüÜ:;]', '', clean) # Caracteres raros
    return clean.strip()

@app.route("/", methods=["GET"])
async def health_check():
    return jsonify({"status": "online", "provider": "OpenRouter Free", "model": MODEL_NAME})

@app.route("/chat", methods=["POST"])
async def chat():
    data = await request.get_json()
    session_id = data.get("session_id", "default")
    user_msg = data.get("message", "")
    mentor_id = data.get("mentor_id", "raava")
    
    # 1. Configuración del Mentor
    mentor_data = MENTORS_CONFIG.get(mentor_id, MENTORS_CONFIG["raava"])
    
    # 2. Gestión de Historial
    if session_id not in sessions:
        user_context = data.get("user_context", {})
        topic = data.get("current_topic", "General")
        nombre = user_context.get("nombre", "Estudiante")
        
        # System Prompt
        system_content = f"CONTEXTO: Estás enseñando '{topic}' a {nombre}. {mentor_data['system_instruction']}"
        
        sessions[session_id] = [
            {"role": "system", "content": system_content}
        ]
    
    # Añadir mensaje del usuario
    sessions[session_id].append({"role": "user", "content": user_msg})
    
    # 3. Llamada a OpenRouter (Streaming)
    async def stream_generator():
        full_response_text = ""
        try:
            stream = await client.chat.completions.create(
                model=MODEL_NAME,
                messages=sessions[session_id],
                temperature=mentor_data["temperature"],
                max_tokens=1000,
                stream=True,
                extra_headers={
                    "HTTP-Referer": YOUR_SITE_URL,
                    "X-Title": YOUR_APP_NAME,
                }
            )
            
            async for chunk in stream:
                # OpenRouter devuelve un delta con el contenido
                if chunk.choices and chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    full_response_text += content
                    payload = json.dumps({"token": content})
                    yield f"data: {payload}\n\n"
            
            # Guardar respuesta en historial
            sessions[session_id].append({"role": "assistant", "content": full_response_text})
            
            # Señal de fin
            yield f"data: {json.dumps({'done': True})}\n\n"

        except Exception as e:
            logging.error(f"Error en OpenRouter Stream: {e}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return Response(stream_generator(), mimetype='text/event-stream')

@app.route("/talk", methods=["POST"])
async def talk():
    try:
        data = await request.get_json()
        raw_text = data.get("text", "")
        mentor_id = data.get("mentor_id", "raava")
        
        text_to_speak = clean_text_for_tts(raw_text)
        voice = MENTORS_CONFIG.get(mentor_id, MENTORS_CONFIG["raava"])["voice"]
        
        if not text_to_speak:
            return jsonify({"error": "Texto vacío"}), 400

        audio_memory = io.BytesIO()
        communicate = edge_tts.Communicate(text_to_speak, voice)
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_memory.write(chunk["data"])
                
        audio_memory.seek(0)

        return await send_file(
            audio_memory, 
            mimetype="audio/mpeg",
            as_attachment=False,
            attachment_filename="voice.mp3"
        )

    except Exception as e:
        logging.error(f"Error TTS: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    import hypercorn.asyncio
    from hypercorn.config import Config

    config = Config()
    config.bind = [f"0.0.0.0:{int(os.environ.get('PORT', 10000))}"]
    
    asyncio.run(hypercorn.asyncio.serve(app, config))
