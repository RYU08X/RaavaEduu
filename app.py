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

# =============================================================================
# CONFIGURACIÓN GENERAL
# =============================================================================
app = Flask(__name__)
# CORS Permisivo para evitar problemas durante la demo
CORS(app, resources={r"/*": {"origins": "*"}})
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

sessions = {}

# Variables de Entorno (Asegúrate de configurar OPENROUTER_API_KEY en Render)
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY", "")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "") # ¡Tu clave va en las variables de entorno de Render!
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# =============================================================================
# 🧠 CEREBRO DEL CURRÍCULO (Mapa de ruta para la IA)
# =============================================================================
TOPIC_CURRICULUM = {
    "Fundamentos Algebraicos": [
        "1. Traducir lenguaje común a lenguaje algebraico (ej. 'un número más cinco')",
        "2. Diferencia entre variables (letras) y constantes (números)",
        "3. Clasificación básica de números reales",
        "4. Partes de un término algebraico (signo, coeficiente, literal, exponente)"
    ],
    "Probabilidad Clásica": [
        "1. Concepto de espacio muestral",
        "2. Regla de Laplace (casos favorables / casos totales)",
        "3. Diferencia entre eventos posibles e imposibles"
    ],
    # Fallback genérico inteligente
    "General": [
        "1. Identificar dudas principales",
        "2. Explicar conceptos clave",
        "3. Dar ejemplos prácticos"
    ]
}

# =============================================================================
# CONFIGURACIÓN DE MENTORES (Raava Actualizada)
# =============================================================================
MENTORS_BASE_CONFIG = {
    "newton": {
        "name": "Isaac Newton",
        "voice": "es-MX-JorgeNeural",
        "base_prompt": (
            "Eres Isaac Newton. Tu tono es solemne pero educativo. "
            "Explicas el universo a través de reglas y lógica. "
            "Usa analogías físicas breves."
        )
    },
    "einstein": {
        "name": "Albert Einstein",
        "voice": "es-ES-AlvaroNeural",
        "base_prompt": (
            "Eres Albert Einstein. Eres humilde, curioso y un poco juguetón. "
            "Valoras la imaginación más que el conocimiento estricto. "
            "Habla con calidez."
        )
    },
    "raava": {
        "name": "Raava (IA)",
        "voice": "es-MX-DaliaNeural",
        "base_prompt": (
            "Eres Raava, una mentora extremadamente empática, paciente y amigable. ✨ "
            "Tu personalidad es cálida y alentadora, como una excelente profesora que realmente se preocupa. "
            "Tu superpoder es hacer que las matemáticas parezcan fáciles y menos intimidantes. "
            "Validas siempre el esfuerzo del estudiante antes de corregir. Usas emojis ocasionalmente para suavizar el tono."
        )
    }
}

# =============================================================================
# UTILIDADES
# =============================================================================

def clean_text_for_tts(text):
    """
    Limpia el texto para que el audio suene natural.
    IMPORTANTE: Elimina el bloque <think> de DeepSeek R1.
    """
    # 1. Eliminar pensamientos internos de DeepSeek (<think>...</think>)
    # re.DOTALL permite que el punto (.) coincida también con saltos de línea
    clean = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    
    # 2. Eliminar markdown básico
    clean = clean.replace("**", "").replace("*", "")
    clean = clean.replace("###", "").replace("##", "")
    clean = clean.replace("- ", "")
    
    # 3. Eliminar emojis y caracteres raros (dejando puntuación básica en español)
    clean = re.sub(r'[^\w\s,¿?.!áéíóúÁÉÍÓÚñÑ]', '', clean) 
    
    # 4. Eliminar espacios múltiples que puedan quedar
    clean = re.sub(r'\s+', ' ', clean).strip()
    
    return clean

def build_dynamic_system_prompt(mentor_id, user_data, current_topic):
    mentor_config = MENTORS_BASE_CONFIG.get(mentor_id, MENTORS_BASE_CONFIG["raava"])
    base = mentor_config["base_prompt"]
    
    nombre = user_data.get("nombre", "Estudiante")
    pasion = user_data.get("pasion", "aprender")
    estilo = user_data.get("aprendizaje", "visual")
    
    # Buscar si hay un "mapa" para este tema
    topic_key = next((key for key in TOPIC_CURRICULUM if key in current_topic), "General")
    learning_path = TOPIC_CURRICULUM.get(topic_key, TOPIC_CURRICULUM["General"])
    formatted_path = "\n".join(learning_path)

    prompt = f"""
    {base}
    
    CONTEXTO DEL ESTUDIANTE:
    - Nombre: {nombre}
    - Le gusta: {pasion} (¡Úsalo para ejemplos! Ej: Si le gusta el fútbol, explica álgebra con goles).
    - Estilo: {estilo}
    
    TU MISIÓN ACTUAL - TEMA: "{current_topic}"
    Tu objetivo no es solo responder, es GUIAR al estudiante a través de estos puntos clave:
    {formatted_path}
    
    REGLAS DE INTERACCIÓN (SÍGUELAS SIEMPRE):
    1. **EMPATÍA RADICAL:** Si el usuario se equivoca, di algo como "¡Es una confusión muy común! No te preocupes, veámoslo así...". Nunca seas seca.
    2. **EXPLICACIÓN + EJEMPLO:** No des solo la definición. Da la definición simple y luego un ejemplo relacionado con {pasion}.
    3. **LONGITUD PERFECTA:** No escribas un libro, pero tampoco seas telegráfica. Usa unos 2 párrafos cortos. Explica bien.
    4. **CHECK DE COMPRENSIÓN:** Termina casi siempre con una pregunta para asegurar que entendió o para invitarle a probar un ejercicio. Ej: "¿Te hace sentido esto?" o "¿Te animas a intentar uno?"
    
    SI EL USUARIO DICE "NO SÉ" O SALUDA:
    No digas "¿En qué te ayudo?". En su lugar, toma la iniciativa: "¡Hola {nombre}! Hoy vamos a dominar {current_topic}. ¿Te parece si empezamos por entender [Primer punto del temario]?"
    """
    return prompt

# =============================================================================
# RUTAS DE LA API
# =============================================================================

@app.route("/", methods=["GET"])
def health_check():
    return jsonify({"status": "online", "service": "RaavaEdu Backend (DeepSeek R1 Powered)"})

# 1. INICIALIZAR SESIÓN
@app.route("/init_session", methods=["POST"])
def init_session():
    try:
        data = request.json
        session_id = data.get("session_id")
        mentor_id = data.get("mentor_id", "raava")
        user_data = data.get("user_data", {})
        current_topic = data.get("current_topic", "General")

        system_prompt = build_dynamic_system_prompt(mentor_id, user_data, current_topic)

        sessions[session_id] = [
            {"role": "system", "content": system_prompt}
        ]
        
        logging.info(f"✅ Sesión iniciada: {session_id} | Mentor: {mentor_id}")
        return jsonify({"status": "ok"})
    except Exception as e:
        logging.error(f"❌ Error init_session: {e}")
        return jsonify({"error": str(e)}), 500

# 2. CHAT (LLM) - AHORA CON DEEPSEEK R1 (FREE)
@app.route("/chat", methods=["POST"])
def chat():
    try:
        data = request.json
        session_id = data.get("session_id", "default")
        user_msg = data.get("message", "")
        mentor_id = data.get("mentor_id", "raava")
        
        # Contexto de respaldo
        if session_id not in sessions:
            user_context = data.get("user_context", {})
            topic = data.get("current_topic", "General")
            sys_prompt = build_dynamic_system_prompt(mentor_id, user_context, topic)
            sessions[session_id] = [{"role": "system", "content": sys_prompt}]
        
        sessions[session_id].append({"role": "user", "content": user_msg})

        # Verifica que la KEY exista
        if not OPENROUTER_API_KEY:
            logging.error("❌ FALTA LA API KEY DE OPENROUTER")
            return jsonify({"reply": "Error de configuración: Falta la API Key en el servidor."})

        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://raavaedu.app", 
            "X-Title": "Raava Edu"
        }

        # --- CAMBIO IMPORTANTE: MODELO DEEPSEEK R1 ---
        payload = {
            "model": "deepseek/deepseek-r1:free",  # ID de DeepSeek R1 Gratis en OpenRouter
            "messages": sessions[session_id][-8:], # Memoria
            "temperature": 0.6,
            "max_tokens": 1000 # R1 necesita más tokens porque "piensa" antes de escribir
        }

        logging.info(f"📤 Enviando a OpenRouter (DeepSeek R1)...")
        response = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=40) # Timeout más largo para R1
        
        if response.status_code != 200:
            logging.error(f"OpenRouter Error Status {response.status_code}: {response.text}")
            if response.status_code == 429:
                return jsonify({"reply": "¡Vaya! Mi cerebro está un poco saturado ahora mismo (Error 429). DeepSeek está muy solicitado. Intenta en 10 seg."})
            return jsonify({"reply": "¡Ups! Hubo un pequeño error de conexión con mi cerebro digital 🧠. ¿Podrías repetirlo?"})

        result = response.json()
        
        if 'error' in result:
             logging.error(f"API Error JSON: {result['error']}")
             return jsonify({"reply": "Lo siento, estoy teniendo problemas técnicos momentáneos con el proveedor de IA."})

        # Obtenemos la respuesta completa (incluyendo <think>)
        full_reply = result["choices"][0]["message"]["content"]
        
        # OPCIONAL: Si quieres guardar la respuesta limpia en el chat history para ahorrar tokens después:
        # clean_reply = re.sub(r'<think>.*?</think>', '', full_reply, flags=re.DOTALL).strip()
        
        # Guardamos la respuesta tal cual (o limpia) en el historial
        sessions[session_id].append({"role": "assistant", "content": full_reply})
        
        return jsonify({
            "reply": full_reply, # El frontend puede decidir si mostrar o ocultar el <think>
            "mentor": MENTORS_BASE_CONFIG.get(mentor_id, {}).get("name", "Mentor")
        })

    except Exception as e:
        logging.error(f"❌ Error CHAT Fatal: {e}")
        return jsonify({"reply": "Tuve un error interno de conexión. Intenta de nuevo en unos segundos."}), 500

# 3. LISTEN (STT)
@app.route("/listen", methods=["POST"])
def listen():
    if "audio" not in request.files:
        return jsonify({"error": "No audio"}), 400

    try:
        audio_file = request.files["audio"]
        headers = { 
            "Authorization": f"Token {DEEPGRAM_API_KEY}", 
            "Content-Type": "audio/wav" 
        }
        url = "https://api.deepgram.com/v1/listen?model=nova-2&language=es&smart_format=true"

        logging.info("🎤 Procesando audio...")
        response = requests.post(url, headers=headers, data=audio_file.read(), timeout=10)
        response.raise_for_status()
        
        data = response.json()
        transcript = data.get("results", {}).get("channels", [])[0].get("alternatives", [])[0].get("transcript", "")
        
        logging.info(f"🗣️ Transcripción: {transcript}")
        return jsonify({"text": transcript})

    except Exception as e:
        logging.error(f"❌ Error Deepgram: {e}")
        return jsonify({"text": "", "error": str(e)}), 500

# 4. TALK (TTS)
async def generate_tts_file(text, voice, output_path):
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_path)

@app.route("/talk", methods=["POST"])
def talk():
    try:
        data = request.json
        text = data.get("text", "")
        mentor_id = data.get("mentor_id", "raava")

        if not text: 
            return jsonify({"error": "No text provided"}), 400

        # IMPORTANTE: Aquí se limpia el <think> para que NO se escuche en el audio
        text_clean = clean_text_for_tts(text)
        voice = MENTORS_BASE_CONFIG.get(mentor_id, MENTORS_BASE_CONFIG["raava"])["voice"]
        
        filename = f"tts_{uuid.uuid4().hex}.mp3"
        filepath = os.path.join(tempfile.gettempdir(), filename)

        asyncio.run(generate_tts_file(text_clean, voice, filepath))
        
        return send_file(filepath, mimetype="audio/mpeg")

    except Exception as e:
        logging.error(f"❌ Error TTS Fatal: {str(e)}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
