import os
import uuid
import asyncio
import tempfile
import logging
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import requests
import edge_tts

# =============================================================================
# CONFIGURACIÓN
# =============================================================================
app = Flask(__name__)
CORS(app)
logging.basicConfig(level=logging.INFO)

sessions = {}

DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY", "")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# =============================================================================
# CONFIGURACIÓN BASE DE MENTORES
# =============================================================================
MENTORS_BASE_CONFIG = {
    "newton": {
        "name": "Isaac Newton",
        "voice": "es-MX-JorgeNeural",
        "base_prompt": (
            "Eres Isaac Newton, físico y matemático riguroso. "
            "Tu objetivo es enseñar matemáticas fundamentales con precisión lógica. "
        )
    },
    "einstein": {
        "name": "Albert Einstein",
        "voice": "es-ES-AlvaroNeural",
        "base_prompt": (
            "Eres Albert Einstein, físico teórico creativo y curioso. "
            "Crees que la imaginación es más importante que el conocimiento. "
        )
    },
    "raava": {
        "name": "Raava (IA)",
        "voice": "es-MX-DaliaNeural",
        "base_prompt": (
            "Eres Raava, una Mentora de Inteligencia Artificial avanzada y empática. "
            "Te adaptas al ritmo del estudiante y eres muy clara. "
        )
    }
}

# =============================================================================
# FUNCIONES AUXILIARES
# =============================================================================

def build_dynamic_system_prompt(mentor_id, user_data, current_topic):
    """
    Construye un prompt de sistema ULTRA ESPECÍFICO basado en el usuario y el tema.
    """
    mentor_config = MENTORS_BASE_CONFIG.get(mentor_id, MENTORS_BASE_CONFIG["raava"])
    base = mentor_config["base_prompt"]
    
    # Extraer datos del onboarding
    nombre = user_data.get("nombre", "Estudiante")
    pasion = user_data.get("pasion", "aprender")
    meta = user_data.get("meta", "mejorar")
    estilo = user_data.get("aprendizaje", "general")

    prompt = f"""
    {base}
    
    PERFIL DEL ESTUDIANTE:
    - Nombre: {nombre}
    - Pasión: {pasion} (Usa esto para dar ejemplos/analogías que le interesen).
    - Meta Personal: {meta} (Motívalo recordando su meta).
    - Estilo de Aprendizaje: {estilo}.
    
    CONTEXTO OBLIGATORIO (CRÍTICO):
    El tema actual de la lección es: "{current_topic}".
    
    INSTRUCCIONES DE COMPORTAMIENTO:
    1. CÉNTRATE EXCLUSIVAMENTE EN EL TEMA ACTUAL. Si el usuario se desvía, tráelo de vuelta al tema "{current_topic}" con amabilidad.
    2. No hables de temas no relacionados (política, cocina, etc.) a menos que sea una analogía directa con {pasion} para explicar {current_topic}.
    3. Adapta tu explicación para alguien con estilo de aprendizaje {estilo}.
    4. Sé conciso y fomenta la curiosidad.
    """
    return prompt

# =============================================================================
# RUTAS DE LA API
# =============================================================================

@app.route("/", methods=["GET"])
def health_check():
    return jsonify({"status": "online", "message": "Fiscamp Education Backend Running"})

# 1. INICIALIZAR SESIÓN (Onboarding)
@app.route("/init_session", methods=["POST"])
def init_session():
    data = request.json
    session_id = data.get("session_id")
    mentor_id = data.get("mentor_id", "raava")
    user_data = data.get("user_data", {})
    current_topic = data.get("current_topic", "General")

    # Construir el prompt personalizado
    system_prompt = build_dynamic_system_prompt(mentor_id, user_data, current_topic)

    # Guardar en memoria
    sessions[session_id] = [
        {"role": "system", "content": system_prompt}
    ]
    
    logging.info(f"Sesión {session_id} inicializada para tema: {current_topic}")
    return jsonify({"status": "ok", "message": "Sesión configurada"})

# 2. CHAT (LLM)
@app.route("/chat", methods=["POST"])
def chat():
    data = request.json
    session_id = data.get("session_id", "default")
    user_msg = data.get("message", "")
    mentor_id = data.get("mentor_id", "raava")
    
    # Datos opcionales por si se perdió la sesión (Stateless fallback)
    user_context = data.get("user_context", {})
    current_topic = data.get("current_topic", "General")

    if not user_msg:
        return jsonify({"error": "Mensaje vacío"}), 400

    # Si la sesión no existe, la creamos al vuelo con los datos del contexto
    if session_id not in sessions:
        sys_prompt = build_dynamic_system_prompt(mentor_id, user_context, current_topic)
        sessions[session_id] = [{"role": "system", "content": sys_prompt}]
    
    # Agregar mensaje del usuario
    sessions[session_id].append({"role": "user", "content": user_msg})

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://fiscamp-edu.onrender.com", 
        "X-Title": "Fiscamp Education"
    }

    payload = {
        "model": "meta-llama/llama-3-8b-instruct",
        "messages": sessions[session_id],
        "temperature": 0.5, # Temperatura baja para mantener el foco en el tema
        "max_tokens": 300
    }

    try:
        response = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        result = response.json()
        
        reply = result["choices"][0]["message"]["content"]
        sessions[session_id].append({"role": "assistant", "content": reply})
        
        return jsonify({
            "reply": reply,
            "mentor": MENTORS_BASE_CONFIG.get(mentor_id, {}).get("name", "Mentor")
        })

    except Exception as e:
        logging.error(f"Error OpenRouter: {e}")
        return jsonify({"error": str(e), "reply": "Lo siento, hubo un error de conexión."}), 500

# 3. LISTEN (STT)
@app.route("/listen", methods=["POST"])
def listen():
    if "audio" not in request.files:
        return jsonify({"error": "No audio"}), 400

    audio_file = request.files["audio"]
    headers = { "Authorization": f"Token {DEEPGRAM_API_KEY}", "Content-Type": "audio/wav" }
    url = "https://api.deepgram.com/v1/listen?model=nova-2&language=es&smart_format=true"

    try:
        response = requests.post(url, headers=headers, data=audio_file.read(), timeout=10)
        response.raise_for_status()
        return jsonify({"text": response.json().get("results", {}).get("channels", [])[0].get("alternatives", [])[0].get("transcript", "")})
    except Exception as e:
        logging.error(f"Error Deepgram: {e}")
        return jsonify({"error": str(e)}), 500

# 4. TALK (TTS)
async def generate_tts(text, voice, output_path):
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_path)

@app.route("/talk", methods=["POST"])
def talk():
    data = request.json
    text = data.get("text", "")
    mentor_id = data.get("mentor_id", "raava")

    if not text: return jsonify({"error": "No text"}), 400

    voice = MENTORS_BASE_CONFIG.get(mentor_id, MENTORS_BASE_CONFIG["raava"])["voice"]
    filename = f"{uuid.uuid4()}.mp3"
    filepath = os.path.join(tempfile.gettempdir(), filename)

    try:
        asyncio.run(generate_tts(text, voice, filepath))
        return send_file(filepath, mimetype="audio/mpeg")
    except Exception as e:
        logging.error(f"Error TTS: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/reset", methods=["POST"])
def reset():
    data = request.json
    session_id = data.get("session_id")
    if session_id in sessions: del sessions[session_id]
    return jsonify({"status": "cleared"})

if _name_ == "_main_":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
