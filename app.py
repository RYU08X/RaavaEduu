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
# Habilitar CORS para permitir peticiones desde cualquier origen (tu frontend React)
CORS(app)

# Configuración de Logging
logging.basicConfig(level=logging.INFO)

# Almacenamiento de sesiones en memoria (session_id -> historial de mensajes)
sessions = {}

# CLAVES DE API (Debes configurarlas en las variables de entorno de Render)
# Si no están, usará cadenas vacías y fallará, asegúrate de ponerlas en Render.
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY", "")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# =============================================================================
# CONFIGURACIÓN DE MENTORES (Personalidades y Voces)
# =============================================================================
MENTORS_CONFIG = {
    "newton": {
        "name": "Isaac Newton",
        "voice": "es-MX-JorgeNeural", # Voz masculina seria
        "system_prompt": (
            "Eres Isaac Newton. Eres un físico y matemático riguroso, formal y preciso. "
            "Hablas con autoridad académica pero eres paciente. "
            "Te gusta usar analogías relacionadas con la gravedad, el movimiento y la óptica. "
            "Tu objetivo es enseñar matemáticas fundamentales con rigor lógico. "
            "No uses jerga moderna excesiva. Mantén tus respuestas concisas (máximo 3 oraciones) a menos que expliques un teorema."
        )
    },
    "einstein": {
        "name": "Albert Einstein",
        "voice": "es-ES-AlvaroNeural", # Voz masculina más suave/europea
        "system_prompt": (
            "Eres Albert Einstein. Eres creativo, un poco disperso pero genial, y muy amable. "
            "Crees que la imaginación es más importante que el conocimiento. "
            "Usa el humor y ejemplos visuales locos (trenes, ascensores en el espacio). "
            "Tu tono es cálido y alentador. Si el estudiante se equivoca, dile que los errores son parte del descubrimiento. "
            "Mantén tus respuestas conversacionales y amigables."
        )
    },
    "raava": {
        "name": "Raava (IA)",
        "voice": "es-MX-DaliaNeural", # Voz femenina neutra y clara
        "system_prompt": (
            "Eres Raava, una Mentora de Inteligencia Artificial avanzada y empática. "
            "Tu estilo es adaptativo: si el usuario es breve, tú también; si necesita detalles, los das. "
            "Usas emojis ocasionalmente para ser expresiva ✨. "
            "Tu objetivo es guiar al estudiante paso a paso, asegurando que entienda antes de avanzar. "
            "Eres moderna, eficiente y muy clara."
        )
    }
}

# =============================================================================
# RUTAS DE LA API
# =============================================================================

@app.route("/", methods=["GET"])
def health_check():
    return jsonify({"status": "online", "message": "Fiscamp Education Backend Running"})

# 1. CHAT (LLM con OpenRouter)
@app.route("/chat", methods=["POST"])
def chat():
    data = request.json
    session_id = data.get("session_id", "default")
    user_msg = data.get("message", "")
    mentor_id = data.get("mentor_id", "raava") # newton, einstein, o raava

    if not user_msg:
        return jsonify({"error": "Mensaje vacío"}), 400

    # Recuperar configuración del mentor
    mentor_config = MENTORS_CONFIG.get(mentor_id, MENTORS_CONFIG["raava"])

    # Inicializar sesión si no existe O si cambiamos de mentor (para resetear el contexto)
    # Nota: En una app real, querrías mantener el historial pero cambiar el system prompt.
    # Aquí simplificamos: si la sesión es nueva, inyectamos el prompt.
    if session_id not in sessions:
        sessions[session_id] = [
            {"role": "system", "content": mentor_config["system_prompt"]}
        ]
    
    # Asegurar que el sistema sepa quién es (en caso de cambio de mentor en misma sesión)
    # Reemplazamos el mensaje system (índice 0) con el del mentor actual
    sessions[session_id][0] = {"role": "system", "content": mentor_config["system_prompt"]}

    # Agregar mensaje del usuario
    sessions[session_id].append({"role": "user", "content": user_msg})

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://fiscamp-edu.onrender.com", # Cambia esto por tu URL real
        "X-Title": "Fiscamp Education"
    }

    payload = {
        "model": "meta-llama/llama-3-8b-instruct", # Modelo rápido y eficiente
        "messages": sessions[session_id],
        "temperature": 0.7,
        "max_tokens": 300 # Respuestas no muy largas para chat fluido
    }

    try:
        response = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        result = response.json()
        
        reply = result["choices"][0]["message"]["content"]
        
        # Guardar respuesta en historial
        sessions[session_id].append({"role": "assistant", "content": reply})
        
        return jsonify({
            "reply": reply,
            "mentor": mentor_config["name"]
        })

    except Exception as e:
        logging.error(f"Error OpenRouter: {e}")
        return jsonify({"error": str(e), "reply": "Lo siento, perdí la conexión neuronal. ¿Intentamos de nuevo?"}), 500


# 2. LISTEN (STT con Deepgram) - Para enviar audios al mentor
@app.route("/listen", methods=["POST"])
def listen():
    if "audio" not in request.files:
        return jsonify({"error": "No se recibió archivo de audio"}), 400

    audio_file = request.files["audio"]
    
    headers = {
        "Authorization": f"Token {DEEPGRAM_API_KEY}",
        "Content-Type": "audio/wav" # Asegúrate que el frontend mande WAV o ajusta esto
    }

    # Usamos Nova-2 en español, optimizado para conversaciones
    url = "https://api.deepgram.com/v1/listen?model=nova-2&language=es&smart_format=true"

    try:
        response = requests.post(url, headers=headers, data=audio_file.read(), timeout=10)
        response.raise_for_status()
        data = response.json()
        
        transcript = data.get("results", {}).get("channels", [])[0].get("alternatives", [])[0].get("transcript", "")
        return jsonify({"text": transcript})
    
    except Exception as e:
        logging.error(f"Error Deepgram: {e}")
        return jsonify({"error": str(e)}), 500


# 3. TALK (TTS con Edge-TTS) - Para que el mentor te hable (Llamadas)
async def generate_tts(text, voice, output_path):
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_path)

@app.route("/talk", methods=["POST"])
def talk():
    data = request.json
    text = data.get("text", "")
    mentor_id = data.get("mentor_id", "raava")

    if not text:
        return jsonify({"error": "No text provided"}), 400

    # Seleccionar voz basada en el mentor
    mentor_config = MENTORS_CONFIG.get(mentor_id, MENTORS_CONFIG["raava"])
    voice = mentor_config["voice"]

    filename = f"{uuid.uuid4()}.mp3"
    filepath = os.path.join(tempfile.gettempdir(), filename)

    try:
        asyncio.run(generate_tts(text, voice, filepath))
        return send_file(filepath, mimetype="audio/mpeg")
    except Exception as e:
        logging.error(f"Error TTS: {e}")
        return jsonify({"error": str(e)}), 500

# Endpoint para reiniciar sesión (útil al cambiar de curso o salir del chat)
@app.route("/reset", methods=["POST"])
def reset():
    data = request.json
    session_id = data.get("session_id")
    if session_id in sessions:
        del sessions[session_id]
    return jsonify({"status": "cleared"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
