import os
import logging
import json
import re
import asyncio
import tempfile
import requests
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import edge_tts

# =============================================================================
# CONFIGURACIÓN GENERAL
# =============================================================================
app = Flask(__name__)
# CORS Permisivo para evitar problemas de "Failed to fetch"
CORS(app, resources={r"/*": {"origins": "*"}})
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- VARIABLES DE ENTORNO ---
# ¡Asegúrate de poner estas en Render!
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY", "")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# Modelo: Usamos Llama 3.3 70B Free como pediste (o puedes cambiar a Gemini)
MODEL_NAME = "meta-llama/llama-3.3-70b-instruct:free"

# Memoria Volátil
sessions = {}

# =============================================================================
# 🧠 CEREBRO DEL CURRÍCULO (Tu lógica original)
# =============================================================================
TOPIC_CURRICULUM = {
    "Fundamentos Algebraicos": [
        "1. Traducir lenguaje común a lenguaje algebraico (ej. 'un número más cinco')",
        "2. Identificar variables, constantes y coeficientes",
        "3. Evaluar expresiones simples"
    ],
    "Pensamiento Matemático": [
        "1. Entender la diferencia entre datos y opinión",
        "2. Tipos de gráficas y cuándo usarlas",
        "3. Media, mediana y moda con ejemplos cotidianos"
    ]
}

# Configuración de Mentores (Voces y Prompts)
MENTORS_CONFIG = {
    "raava": {
        "name": "Raava",
        "voice": "es-MX-DaliaNeural",
        "system_instruction": "Eres Raava, una mentora IA empática, paciente y clara. Tu objetivo es guiar sin juzgar. Usa emojis ocasionales. Estás enseñando a un principiante."
    },
    "newton": {
        "name": "Isaac Newton",
        "voice": "es-MX-JorgeNeural",
        "system_instruction": "Eres Sir Isaac Newton. Eres riguroso, algo arrogante pero brillante. Te obsesiona la precisión y las leyes fundamentales. No toleras la pereza mental."
    },
    "einstein": {
        "name": "Albert Einstein",
        "voice": "es-ES-AlvaroNeural",
        "system_instruction": "Eres Albert Einstein. Eres humilde, curioso y usas analogías visuales (trenes, luz). Valoras la imaginación más que el conocimiento."
    }
}

# =============================================================================
# FUNCIONES AUXILIARES
# =============================================================================

def clean_text_for_tts(text):
    """Limpia el texto para que el audio no lea asteriscos ni código."""
    # Eliminar bloques de pensamiento <think>
    clean = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    # Eliminar markdown
    clean = clean.replace("**", "").replace("*", "").replace("`", "")
    clean = clean.replace("#", "")
    return clean.strip()

async def generate_audio_file(text, voice):
    """Genera audio temporal usando Edge-TTS (Async wrapper)"""
    communicate = edge_tts.Communicate(text, voice)
    # Crear archivo temporal
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
        temp_path = fp.name
    await communicate.save(temp_path)
    return temp_path

# =============================================================================
# RUTAS (ENDPOINTS)
# =============================================================================

@app.route("/", methods=["GET"])
def health_check():
    return jsonify({"status": "online", "backend": "Flask + Deepgram + Llama"})

# 1. INICIALIZAR SESIÓN (Crucial para tu Frontend)
@app.route("/init_session", methods=["POST"])
def init_session():
    try:
        data = request.json
        session_id = data.get("session_id")
        user_data = data.get("user_data", {})
        mentor_id = data.get("mentor_id", "raava")
        topic_title = data.get("current_topic", "General")
        
        logging.info(f"🆕 Iniciando sesión {session_id} con {mentor_id}")

        # Buscar currículo
        topic_guide = "Conceptos generales."
        for key, value in TOPIC_CURRICULUM.items():
            if key in topic_title:
                topic_guide = "\n".join(value)
                break
        
        mentor_info = MENTORS_CONFIG.get(mentor_id, MENTORS_CONFIG["raava"])
        
        # System Prompt Robusto
        system_prompt = f"""
        {mentor_info['system_instruction']}
        
        CONTEXTO ACTUAL:
        Estás enseñando: {topic_title}
        Alumno: {user_data.get('nombre', 'Estudiante')}
        Intereses: {user_data.get('pasion', 'General')}
        Estilo Aprendizaje: {user_data.get('aprendizaje', 'Visual')}
        
        GUÍA DE TEMAS (CURRÍCULO):
        {topic_guide}
        
        INSTRUCCIÓN:
        1. Saluda brevemente por su nombre.
        2. Introduce el primer punto del currículo relacionándolo con su pasión si es posible.
        3. Mantén respuestas concisas (máximo 3 párrafos).
        """

        sessions[session_id] = [
            {"role": "system", "content": system_prompt}
        ]
        
        return jsonify({"status": "success", "message": "Sesión configurada"})

    except Exception as e:
        logging.error(f"Error init_session: {e}")
        return jsonify({"error": str(e)}), 500

# 2. CHAT (Conectar con OpenRouter usando Requests)
@app.route("/chat", methods=["POST"])
def chat():
    try:
        data = request.json
        session_id = data.get("session_id", "default")
        user_msg = data.get("message", "")
        
        if session_id not in sessions:
            sessions[session_id] = [{"role": "system", "content": "Eres un tutor útil."}]
            
        sessions[session_id].append({"role": "user", "content": user_msg})
        
        # Configurar Payload para OpenRouter
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://tu-app-render.com",
            "X-Title": "Raava Edu"
        }
        
        payload = {
            "model": MODEL_NAME,
            "messages": sessions[session_id][-10:], # Memoria de últimos 10 mensajes
            "temperature": 0.6,
            "max_tokens": 500
        }

        # Llamada Síncrona (Requests) - Como en tu código original
        response = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=30)
        
        if response.status_code != 200:
            logging.error(f"OpenRouter Error: {response.text}")
            return jsonify({"reply": "Tuve un error de conexión mental. ¿Me repites?"})

        result = response.json()
        reply = result["choices"][0]["message"]["content"]
        
        sessions[session_id].append({"role": "assistant", "content": reply})
        
        return jsonify({"reply": reply})

    except Exception as e:
        logging.error(f"Chat Error: {e}")
        return jsonify({"error": str(e)}), 500

# 3. LISTEN (Deepgram STT) - ¡El que faltaba!
@app.route("/listen", methods=["POST"])
def listen():
    try:
        if 'audio' not in request.files:
            return jsonify({"error": "No audio"}), 400
            
        audio_file = request.files['audio']
        
        # Llamada directa a la API de Deepgram (sin instalar SDK pesado si no quieres)
        deepgram_url = "https://api.deepgram.com/v1/listen?model=nova-2&smart_format=true&language=es"
        
        headers = {
            "Authorization": f"Token {DEEPGRAM_API_KEY}",
            "Content-Type": "audio/wav" # O el formato que envíe tu frontend
        }
        
        logging.info("👂 Enviando audio a Deepgram...")
        response = requests.post(deepgram_url, headers=headers, data=audio_file.read(), timeout=15)
        
        if response.status_code != 200:
            logging.error(f"Deepgram Error: {response.text}")
            return jsonify({"text": ""}) # Fallo silencioso
            
        result = response.json()
        transcript = result['results']['channels'][0]['alternatives'][0]['transcript']
        logging.info(f"🗣️ Transcripción: {transcript}")
        
        return jsonify({"text": transcript})

    except Exception as e:
        logging.error(f"Listen Error: {e}")
        return jsonify({"error": str(e)}), 500

# 4. TALK (Edge TTS)
@app.route("/talk", methods=["POST"])
def talk():
    try:
        data = request.json
        raw_text = data.get("text", "")
        mentor_id = data.get("mentor_id", "raava")
        
        clean_text = clean_text_for_tts(raw_text)
        if not clean_text:
            return jsonify({"error": "Texto vacío"}), 400
            
        voice = MENTORS_CONFIG.get(mentor_id, MENTORS_CONFIG["raava"])["voice"]
        
        # Ejecutar async TTS dentro de Flask sync
        temp_file = asyncio.run(generate_audio_file(clean_text, voice))
        
        # Enviar archivo y luego Flask lo limpiará (o el SO)
        return send_file(temp_file, mimetype="audio/mpeg", as_attachment=False)

    except Exception as e:
        logging.error(f"TTS Error: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    # En local
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)), debug=True)
