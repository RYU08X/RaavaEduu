import os
import uuid
import asyncio
import tempfile
import logging
import re
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import requests
import edge_tts

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

sessions = {}

DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY", "")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "") 
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# Configuración de Mentores
MENTORS_BASE_CONFIG = {
    "newton": {"name": "Isaac Newton", "voice": "es-MX-JorgeNeural", "base_prompt": "Eres Isaac Newton..."},
    "einstein": {"name": "Albert Einstein", "voice": "es-ES-AlvaroNeural", "base_prompt": "Eres Albert Einstein..."},
    "raava": {
        "name": "Raava (IA)", 
        "voice": "es-MX-DaliaNeural", 
        "base_prompt": "Eres Raava, una mentora empática, paciente y amigable.✨"
    }
}

def clean_text_for_tts(text):
    # Eliminar bloques de pensamiento de DeepSeek
    clean = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    clean = clean.replace("**", "").replace("*", "")
    clean = re.sub(r'[^\w\s,¿?.!áéíóúÁÉÍÓÚñÑ]', '', clean) 
    return clean.strip()

def build_dynamic_system_prompt(mentor_id, user_data, current_topic):
    mentor_config = MENTORS_BASE_CONFIG.get(mentor_id, MENTORS_BASE_CONFIG["raava"])
    nombre = user_data.get("nombre", "Estudiante")
    pasion = user_data.get("pasion", "aprender")
    
    return f"{mentor_config['base_prompt']} Estás enseñando {current_topic} a {nombre}, a quien le gusta {pasion}. Sé breve y termina con una pregunta."

@app.route("/", methods=["GET"])
def health_check():
    return jsonify({"status": "online", "service": "RaavaEdu DeepSeek-R1"})

@app.route("/chat", methods=["POST"])
def chat():
    try:
        data = request.json
        session_id = data.get("session_id", "default")
        user_msg = data.get("message", "")
        mentor_id = data.get("mentor_id", "raava")
        
        if session_id not in sessions:
            user_context = data.get("user_context", {})
            topic = data.get("current_topic", "General")
            sys_prompt = build_dynamic_system_prompt(mentor_id, user_context, topic)
            sessions[session_id] = [{"role": "system", "content": sys_prompt}]
        
        sessions[session_id].append({"role": "user", "content": user_msg})

        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json"
        }

        # ID DE MODELO CORREGIDO PARA EVITAR 404
        payload = {
            "model": "deepseek/deepseek-r1-distill-llama-70b:free",
            "messages": sessions[session_id][-8:],
            "temperature": 0.6,
            "max_tokens": 800
        }

        response = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=40)
        
        if response.status_code != 200:
            logging.error(f"Error: {response.text}")
            return jsonify({"reply": "Perdón, mi conexión está fallando. ¿Podrías repetir?"})

        result = response.json()
        reply = result["choices"][0]["message"]["content"]
        sessions[session_id].append({"role": "assistant", "content": reply})
        
        return jsonify({"reply": reply, "mentor": MENTORS_BASE_CONFIG.get(mentor_id, {})["name"]})

    except Exception as e:
        logging.error(f"Error Fatal: {e}")
        return jsonify({"reply": "Hubo un error interno."}), 500

@app.route("/talk", methods=["POST"])
def talk():
    try:
        data = request.json
        text = clean_text_for_tts(data.get("text", ""))
        mentor_id = data.get("mentor_id", "raava")
        voice = MENTORS_BASE_CONFIG.get(mentor_id, MENTORS_BASE_CONFIG["raava"])["voice"]
        
        filepath = os.path.join(tempfile.gettempdir(), f"{uuid.uuid4().hex}.mp3")
        asyncio.run(edge_tts.Communicate(text, voice).save(filepath))
        
        return send_file(filepath, mimetype="audio/mpeg")
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
