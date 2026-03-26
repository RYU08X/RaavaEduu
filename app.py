import os
import logging
import re
import tempfile
import uuid
import time
import asyncio
from typing import Dict, Optional
from collections import defaultdict

from fastapi import FastAPI, UploadFile, File, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, validator
import aiohttp
import edge_tts

# =============================================================================
# CONFIG
# =============================================================================

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

DEEPGRAM_API_KEY   = os.getenv("DEEPGRAM_API_KEY", "")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
ENVIRONMENT        = os.getenv("ENVIRONMENT", "production")

MODEL_NAME     = "google/gemini-2.0-flash-001"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

ALLOWED_ORIGINS = [
    "https://campeche.raavaedu.com",
    "http://campeche.raavaedu.com",
    "http://localhost:3000",
    "http://localhost:5173",
    "http://localhost:5174",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5174",
]

RATE_WINDOW      = 60
RATE_CHAT        = 30
RATE_LISTEN      = 15
RATE_TALK        = 20
RATE_INIT        = 10
RATE_GENERAL     = 60
MAX_SESSIONS     = 5000
MAX_HISTORY      = 30
SESSION_TTL      = 3600
MAX_MSG_LEN      = 2000
MAX_AUDIO_SIZE   = 10 * 1024 * 1024

# =============================================================================
# RATE LIMITER
# =============================================================================

class RateLimiter:
    def __init__(self):
        self.requests: Dict[str, list] = defaultdict(list)

    def is_allowed(self, key: str, limit: int, window: int = RATE_WINDOW) -> bool:
        now = time.time()
        self.requests[key] = [t for t in self.requests[key] if now - t < window]
        if len(self.requests[key]) >= limit:
            return False
        self.requests[key].append(now)
        return True

    def cleanup(self):
        now = time.time()
        stale = [k for k, v in self.requests.items() if all(now - t > RATE_WINDOW * 2 for t in v)]
        for k in stale:
            del self.requests[k]

rate_limiter = RateLimiter()

# =============================================================================
# APP
# =============================================================================

app = FastAPI(
    title="Raava Edu API",
    version="3.1.0",
    docs_url="/docs" if ENVIRONMENT == "development" else None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
    max_age=600,
)

@app.middleware("http")
async def security_headers(request: Request, call_next):
    if request.method == "OPTIONS":
        return await call_next(request)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if ENVIRONMENT == "production":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers.pop("server", None)
    return response

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    if request.method == "OPTIONS":
        return await call_next(request)
    ip = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    if not ip:
        ip = request.client.host if request.client else "unknown"
    if not rate_limiter.is_allowed(f"g:{ip}", RATE_GENERAL):
        return JSONResponse(status_code=429, content={"error": "Demasiadas solicitudes. Intenta en un momento."})
    limits = {"/chat": RATE_CHAT, "/init_session": RATE_INIT, "/listen": RATE_LISTEN, "/talk": RATE_TALK}
    path = request.url.path
    if path in limits and not rate_limiter.is_allowed(f"{path}:{ip}", limits[path]):
        return JSONResponse(status_code=429, content={"error": "Demasiadas solicitudes para este servicio."})
    return await call_next(request)

@app.middleware("http")
async def size_limit(request: Request, call_next):
    if request.method == "OPTIONS":
        return await call_next(request)
    cl = request.headers.get("content-length")
    if cl and int(cl) > MAX_AUDIO_SIZE:
        return JSONResponse(status_code=413, content={"error": "Archivo demasiado grande. Máximo 10MB."})
    return await call_next(request)

# =============================================================================
# MENTORS
# =============================================================================

MENTORS = {
    "raava":    {"name": "Raava",          "voice": "es-MX-DaliaNeural", "base_prompt": "Eres Raava, una mentora IA empática, paciente y clara. Tu objetivo es guiar sin juzgar."},
    "newton":   {"name": "Isaac Newton",   "voice": "es-MX-JorgeNeural", "base_prompt": "Eres Sir Isaac Newton. Eres riguroso y te obsesiona la precisión. Usas analogías físicas."},
    "einstein": {"name": "Albert Einstein", "voice": "es-ES-AlvaroNeural", "base_prompt": "Eres Albert Einstein. Eres humilde, curioso y usas analogías visuales y experimentos mentales."},
}

sessions: Dict[str, dict] = {}

# =============================================================================
# MODELS
# =============================================================================

class InitSessionRequest(BaseModel):
    session_id: str
    mentor_id: str = "raava"
    user_data: dict
    current_topic: str = "General"
    topic_id: Optional[str] = None
    topic_data: Optional[dict] = None
    materia_title: Optional[str] = None

    @validator("session_id")
    def val_sid(cls, v):
        if len(v) > 100 or not re.match(r'^[a-zA-Z0-9_\-]+$', v):
            raise ValueError("session_id inválido")
        return v
    @validator("mentor_id")
    def val_mid(cls, v):
        return v if v in MENTORS else "raava"
    @validator("current_topic")
    def val_ct(cls, v):
        return v[:200] if v else "General"

class ChatRequest(BaseModel):
    session_id: str
    message: str
    mentor_id: str = "raava"
    user_context: Optional[dict] = {}
    topic_title: Optional[str] = None

    @validator("session_id")
    def val_sid(cls, v):
        if len(v) > 100: raise ValueError("session_id demasiado largo")
        return v
    @validator("message")
    def val_msg(cls, v):
        if not v or not v.strip(): raise ValueError("Mensaje vacío")
        if len(v) > MAX_MSG_LEN: raise ValueError(f"Máximo {MAX_MSG_LEN} caracteres")
        return v.strip()
    @validator("mentor_id")
    def val_mid(cls, v):
        return v if v in MENTORS else "raava"

class TalkRequest(BaseModel):
    text: str
    mentor_id: str = "raava"

    @validator("text")
    def val_txt(cls, v):
        if not v or not v.strip(): raise ValueError("Texto vacío")
        if len(v) > 3000: raise ValueError("Texto demasiado largo")
        return v.strip()
    @validator("mentor_id")
    def val_mid(cls, v):
        return v if v in MENTORS else "raava"

# =============================================================================
# HELPERS
# =============================================================================

def sanitize(s: str, mx: int = 500) -> str:
    if not s: return ""
    return re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', s[:mx]).strip()

def build_prompt(session, mentor):
    ud = session.get("user_data", {})
    td = session.get("topic_data", {})
    nombre  = sanitize(ud.get("nombre", "Estudiante"), 50)
    pasion  = sanitize(ud.get("pasion", "aprender"), 100)
    meta    = sanitize(ud.get("meta", "entender el tema"), 200)
    estilo  = sanitize(ud.get("aprendizaje", "visual"), 50)
    title   = sanitize(td.get("title", session.get("current_topic", "General")), 200)
    obj     = sanitize(td.get("objective", ""), 500)
    crit    = sanitize(td.get("success_criteria", ""), 500)
    guide   = sanitize(td.get("prompt", ""), 2000)
    materia = sanitize(session.get("materia_title", ""), 100)

    guide_block = f"\n    --- GUÍA PEDAGÓGICA ---\n    {guide}" if guide else ""

    return f"""
    {mentor['base_prompt']}

    --- ALUMNO ---
    Nombre: {nombre}
    Pasión: {pasion} (usa esto para analogías)
    Meta: "{meta}"
    Estilo: {estilo}

    --- TEMA ---
    Materia: {materia}
    Tema: {title}
    {"Objetivo: " + obj if obj else ""}
    {"Criterio de éxito: " + crit if crit else ""}
    {guide_block}

    --- INSTRUCCIONES ---
    1. Enseña ESPECÍFICAMENTE sobre "{title}".
    2. Máx 3-4 oraciones por turno. Conversa, no des cátedra.
    3. Analogías con "{pasion}".
    4. Pregunta de comprobación al final de cada turno.
    5. Si no entiende, reexplica con otro ejemplo.
    6. Si entendió, avanza al siguiente concepto.
    7. Celebra logros. Sé cálido.
    8. Español (salvo que el tema sea inglés).
    9. No inventes datos falsos.
    """

def cleanup_sessions():
    now = time.time()
    stale = [s for s, d in sessions.items() if now - d.get("last_active", 0) > SESSION_TTL]
    for s in stale: del sessions[s]
    if stale: logging.info(f"🧹 {len(stale)} sesiones limpiadas, {len(sessions)} activas")
    rate_limiter.cleanup()

def rm_temp(path: str):
    try: os.remove(path)
    except: pass

def clean_tts(text: str) -> str:
    return re.sub(r'[*_`#]', '', text.replace("[[NEXT_TOPIC]]", "")).strip()

# =============================================================================
# ENDPOINTS
# =============================================================================

@app.get("/")
async def health():
    return {"status": "online", "version": "3.1.0", "sessions": len(sessions), "env": ENVIRONMENT}

@app.post("/init_session")
async def init_session(req: InitSessionRequest):
    if len(sessions) > MAX_SESSIONS: cleanup_sessions()
    title = (req.topic_data or {}).get("title") or req.current_topic or "General"
    logging.info(f"🆕 {req.user_data.get('nombre','?')} → {title}")
    sessions[req.session_id] = {
        "history": [], "user_data": req.user_data,
        "topic_data": req.topic_data or {}, "current_topic": title,
        "materia_title": req.materia_title or "", "mentor_id": req.mentor_id,
        "last_active": time.time(),
    }
    return {"status": "success", "topic": title}

@app.post("/chat")
async def chat(req: ChatRequest):
    try:
        if not OPENROUTER_API_KEY:
            return JSONResponse(status_code=503, content={"error": "API no configurada."})
        if req.session_id not in sessions:
            sessions[req.session_id] = {
                "history": [], "user_data": req.user_context or {},
                "topic_data": {"title": req.topic_title or "General"},
                "current_topic": req.topic_title or "General",
                "materia_title": "", "mentor_id": req.mentor_id,
                "last_active": time.time(),
            }
        sess = sessions[req.session_id]
        sess["last_active"] = time.time()
        if req.user_context:
            sess["user_data"].update({k: v for k, v in req.user_context.items() if v})
        if len(sess["history"]) > MAX_HISTORY:
            sess["history"] = sess["history"][-MAX_HISTORY:]

        mentor = MENTORS.get(req.mentor_id, MENTORS["raava"])
        msgs = [{"role": "system", "content": build_prompt(sess, mentor)}]
        msgs.extend(sess["history"][-10:])
        msgs.append({"role": "user", "content": req.message})

        async with aiohttp.ClientSession() as client:
            async with client.post(
                OPENROUTER_URL,
                json={"model": MODEL_NAME, "messages": msgs, "temperature": 0.4, "max_tokens": 400},
                headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json", "HTTP-Referer": "https://raava.edu"},
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status == 429:
                    return JSONResponse(status_code=429, content={"error": "La IA está ocupada. Intenta en unos segundos."})
                if resp.status != 200:
                    logging.error(f"OpenRouter {resp.status}: {(await resp.text())[:200]}")
                    return JSONResponse(status_code=502, content={"error": "La IA no respondió."})
                data = await resp.json()
                if not data.get("choices"):
                    return JSONResponse(status_code=502, content={"error": "Respuesta vacía."})
                reply = data["choices"][0]["message"]["content"].replace("[[NEXT_TOPIC]]", "").strip()

        sess["history"].append({"role": "user", "content": req.message})
        sess["history"].append({"role": "assistant", "content": reply})
        return {"reply": reply}

    except asyncio.TimeoutError:
        return JSONResponse(status_code=504, content={"error": "Timeout. Intenta de nuevo."})
    except Exception as e:
        logging.error(f"Chat error: {e}")
        return JSONResponse(status_code=500, content={"error": "Error interno."})

@app.post("/listen")
async def listen(audio: UploadFile = File(...)):
    try:
        if not DEEPGRAM_API_KEY:
            return JSONResponse(status_code=503, content={"error": "STT no configurado."})
        content = await audio.read()
        if len(content) > MAX_AUDIO_SIZE:
            return JSONResponse(status_code=413, content={"error": "Audio muy grande."})
        if len(content) < 100:
            return {"text": ""}
        async with aiohttp.ClientSession() as client:
            async with client.post(
                "https://api.deepgram.com/v1/listen?model=nova-2&smart_format=true&language=es",
                headers={"Authorization": f"Token {DEEPGRAM_API_KEY}", "Content-Type": audio.content_type or "audio/wav"},
                data=content, timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status != 200:
                    return {"text": ""}
                data = await resp.json()
                transcript = data.get('results', {}).get('channels', [{}])[0].get('alternatives', [{}])[0].get('transcript', "")
                logging.info(f"🎤 {transcript[:100]}")
        return {"text": transcript}
    except asyncio.TimeoutError:
        return {"text": ""}
    except Exception as e:
        logging.error(f"Listen error: {e}")
        return {"text": ""}

@app.post("/talk")
async def talk(req: TalkRequest, background_tasks: BackgroundTasks):
    try:
        text = clean_tts(req.text)
        if not text:
            return JSONResponse(status_code=400, content={"error": "Texto vacío"})
        voice = MENTORS.get(req.mentor_id, MENTORS["raava"])["voice"]
        path = os.path.join(tempfile.gettempdir(), f"tts_{uuid.uuid4().hex}.mp3")
        await edge_tts.Communicate(text, voice).save(path)
        background_tasks.add_task(rm_temp, path)
        return FileResponse(path, media_type="audio/mpeg", filename="voice.mp3")
    except Exception as e:
        logging.error(f"Talk error: {e}")
        return JSONResponse(status_code=500, content={"error": "Error generando audio."})

@app.on_event("startup")
async def startup():
    logging.info(f"🚀 Raava v3.1.0 ({ENVIRONMENT}) | CORS: {ALLOWED_ORIGINS}")
    if not OPENROUTER_API_KEY: logging.warning("⚠️ OPENROUTER_API_KEY no configurada")
    if not DEEPGRAM_API_KEY: logging.warning("⚠️ DEEPGRAM_API_KEY no configurada")
    async def periodic():
        while True:
            await asyncio.sleep(600)
            cleanup_sessions()
    asyncio.create_task(periodic())

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
