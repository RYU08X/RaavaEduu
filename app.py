import os
import io
import logging
import re
import json
import asyncio
from quart import Quart, request, jsonify, send_file, Response
from quart_cors import cors
import edge_tts
import google.generativeai as genai

# Configuración de Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- CONFIGURACIÓN DE APP & API KEYS ---
app = Quart(__name__)
app = cors(app, allow_origin="*") # Habilita CORS para todos los orígenes

# Cargar API Keys (Asegúrate de tenerlas en tus variables de entorno)
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
genai.configure(api_key=GOOGLE_API_KEY)

# --- ALMACENAMIENTO VOLÁTIL (RAM) ---
# En producción real, usar Redis o Base de Datos.
sessions = {}

# --- CONFIGURACIÓN AVANZADA DE MENTORES (FEW-SHOT & TEMP) ---
MENTORS_CONFIG = {
    "newton": {
        "name": "Isaac Newton",
        "voice": "es-MX-JorgeNeural",
        "temperature": 0.3, # Lógico y preciso
        "system_instruction": """
        Eres Sir Isaac Newton (1643-1727).
        PERSONALIDAD: Arrogante pero brillante, formal, usas lenguaje ligeramente arcaico y académico. Te obsesiona la física, las matemáticas y la alquimia.
        ESTILO: Respuestas directas, lógicas. No toleras la ignorancia voluntaria.
        EJEMPLOS DE DIÁLOGO:
        User: "Hola" -> Newton: "Saludos. Espero que no estemos interrumpiendo mis estudios sobre la óptica para trivialidades."
        User: "No entiendo" -> Newton: "La naturaleza se complace con la simplicidad. Permíteme desglosarlo en principios fundamentales."
        """,
    },
    "einstein": {
        "name": "Albert Einstein",
        "voice": "es-ES-AlvaroNeural",
        "temperature": 0.7, # Creativo y juguetón
        "system_instruction": """
        Eres Albert Einstein (1879-1955).
        PERSONALIDAD: Humilde, juguetón, despeinado intelectualmente. Valoras la imaginación sobre el conocimiento.
        ESTILO: Usas analogías visuales (trenes, elevadores). Hablas con asombro por el universo.
        EJEMPLOS DE DIÁLOGO:
        User: "Hola" -> Einstein: "¡Hola! ¿Listo para un pequeño Gedankenexperiment (experimento mental) hoy?"
        User: "¿Es difícil?" -> Einstein: "No te preocupes por tus dificultades en matemáticas. Te aseguro que las mías son mayores."
        """,
    },
    "raava": {
        "name": "Raava (IA)", 
        "voice": "es-MX-DaliaNeural", 
        "temperature": 0.6, # Equilibrada
        "system_instruction": """
        Eres Raava, una mentora de IA avanzada, empática y paciente.
        PERSONALIDAD: Facilitadora, amable, clara. Tu objetivo es guiar sin juzgar.
        ESTILO: Moderno, uso de emojis ocasionales, muy estructurada pedagógicamente.
        EJEMPLOS DE DIÁLOGO:
        User: "Hola" -> Raava: "¡Hola! Estoy lista para aprender contigo. ¿Qué tema exploraremos hoy? ✨"
        User: "Me rindo" -> Raava: "Respira. El aprendizaje es un proceso, no una carrera. Intentemos un enfoque diferente."
        """,
    }
}

def clean_text_for_tts(text):
    """Limpia el texto para que la voz no lea asteriscos ni código."""
    # Eliminar bloques de pensamiento <think>...</think>
    clean = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    # Eliminar formato Markdown (**negrita**, *cursiva*)
    clean = re.sub(r'\*+', '', clean)
    # Eliminar bloques de código
    clean = re.sub(r'```.*?```', '', clean, flags=re.DOTALL)
    # Eliminar caracteres especiales raros, dejando puntuación básica en español
    clean = re.sub(r'[^\w\s,¿?.!áéíóúÁÉÍÓÚñÑüÜ:;]', '', clean) 
    return clean.strip()

@app.route("/", methods=["GET"])
async def health_check():
    return jsonify({"status": "online", "engine": "Quart Async", "model": "Gemini-2.0-Flash"})

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
        # Prompt dinámico inicial
        user_context = data.get("user_context", {})
        topic = data.get("current_topic", "General")
        nombre = user_context.get("nombre", "Estudiante")
        
        dynamic_context = f"\nCONTEXTO ACTUAL: Estás enseñando '{topic}' a {nombre}. {mentor_data['system_instruction']}"
        
        sessions[session_id] = [
            {"role": "user", "parts": [dynamic_context + "\n(El usuario inicia la sesión)"]}
        ]
    
    # Añadir mensaje actual
    sessions[session_id].append({"role": "user", "parts": [user_msg]})
    
    # 3. Llamada a Gemini (Streaming Real)
    model = genai.GenerativeModel(
        model_name='gemini-2.0-flash-exp',
        generation_config=genai.types.GenerationConfig(
            temperature=mentor_data["temperature"],
            max_output_tokens=500
        )
    )

    # Función generadora para Server-Sent Events (SSE)
    async def stream_generator():
        full_response_text = ""
        try:
            # generate_content_async con stream=True
            response = await model.generate_content_async(
                sessions[session_id], 
                stream=True
            )
            
            async for chunk in response:
                if chunk.text:
                    full_response_text += chunk.text
                    # Formato SSE: "data: <contenido>\n\n"
                    # Escapamos saltos de línea para JSON seguro
                    payload = json.dumps({"token": chunk.text})
                    yield f"data: {payload}\n\n"
            
            # Guardar la respuesta completa en la memoria de sesión
            sessions[session_id].append({"role": "model", "parts": [full_response_text]})
            
            # Señal de fin
            yield f"data: {json.dumps({'done': True})}\n\n"

        except Exception as e:
            logging.error(f"Error en Gemini Stream: {e}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return Response(stream_generator(), mimetype='text/event-stream')

@app.route("/talk", methods=["POST"])
async def talk():
    try:
        data = await request.get_json()
        raw_text = data.get("text", "")
        mentor_id = data.get("mentor_id", "raava")
        
        # Limpieza y selección de voz
        text_to_speak = clean_text_for_tts(raw_text)
        voice = MENTORS_CONFIG.get(mentor_id, MENTORS_CONFIG["raava"])["voice"]
        
        if not text_to_speak:
            return jsonify({"error": "Texto vacío"}), 400

        # --- ESTRATEGIA IN-MEMORY (Sin archivos en disco) ---
        # 1. Crear un buffer de bytes en RAM
        audio_memory = io.BytesIO()
        
        # 2. Generar audio directo al buffer
        communicate = edge_tts.Communicate(text_to_speak, voice)
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_memory.write(chunk["data"])
                
        # 3. Rebobinar el buffer al inicio para leerlo
        audio_memory.seek(0)

        # 4. Enviar directamente al cliente
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
    # Para desarrollo local usamos app.run_task o hypercorn directamente
    # Pero Quart recomienda Hypercorn para producción
    import hypercorn.asyncio
    from hypercorn.config import Config

    config = Config()
    config.bind = [f"0.0.0.0:{int(os.environ.get('PORT', 10000))}"]
    
    asyncio.run(hypercorn.asyncio.serve(app, config))
