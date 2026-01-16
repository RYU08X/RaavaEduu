import React, { useState, useRef, useEffect } from 'react';
import { 
  BookOpen, FolderGit2, Clock, User, Settings, LogOut, Search, MoreVertical, Star, 
  ChevronRight, ChevronLeft, CheckCircle, Lock, PlayCircle, FileText, Video, 
  HelpCircle, UserCheck, Sparkles, Brain, Atom, Phone, Send, Mic, 
  Info, Image, Heart, Smile, Camera, Volume2, StopCircle, X, MicOff,
  Plus, Trash2, Calendar, Layout, List, Github, ExternalLink, ArrowRight, ArrowLeft,
  Copy, Check
} from 'lucide-react';

// --- CONFIGURACIÓN BACKEND ---
const BACKEND_URL = "https://raavaeduu-1.onrender.com";

// --- UTILIDAD: FORMATO DE TEXTO SIMPLE (MARKDOWN LIGHT) ---
// Esto permite que la IA use negritas (**texto**) y listas (- elemento) sin librerías externas.
const FormattedText = ({ text }) => {
  if (!text) return null;
  
  return (
    <div className="text-sm leading-relaxed space-y-2">
      {text.split('\n').map((line, i) => {
        // Manejo de listas
        if (line.trim().startsWith('- ')) {
          return (
            <div key={i} className="flex gap-2 ml-2">
              <span className="text-blue-500 font-bold">•</span>
              <span dangerouslySetInnerHTML={{ 
                __html: line.substring(2).replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>') 
              }} />
            </div>
          );
        }
        // Párrafos normales con negritas
        if (line.trim() === "") return <br key={i} />;
        return (
          <p key={i} dangerouslySetInnerHTML={{ 
            __html: line.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>') 
          }} />
        );
      })}
    </div>
  );
};

// Datos de los cursos
const initialCourses = [
  { id: 1, title: "Pensamiento Matemático", progress: 70, instructor: "Ing. García", color: "bg-blue-500" },
  { id: 2, title: "Fundamentos de La Vida", progress: 30, instructor: "Dra. López", color: "bg-purple-500" },
  { id: 3, title: "Taller de Comunicación", progress: 10, instructor: "Lic. Martínez", color: "bg-yellow-500" },
  { id: 4, title: "Ciencias Sociales", progress: 90, instructor: "Dr. Rodríguez", color: "bg-red-500" },
  { id: 5, title: "Cultura Digital", progress: 45, instructor: "Prof. Smith", color: "bg-green-500" },
  { id: 6, title: "Humanidades", progress: 60, instructor: "Lic. Fernández", color: "bg-teal-500" },
  { id: 7, title: "Física", progress: 20, instructor: "Ing. Newton", color: "bg-orange-500" },
];

// Datos iniciales para Proyectos (Kanban)
const initialProjects = [
  { id: 101, title: "Portafolio Web", desc: "Sitio personal con React", status: "done", tech: "React", date: "2023-10-15" },
  { id: 102, title: "App de Tareas", desc: "CRUD con LocalStorage", status: "progress", tech: "JS", date: "2023-11-20" },
  { id: 103, title: "Análisis de Datos", desc: "Visualización con Python", status: "todo", tech: "Python", date: "2023-12-01" },
  { id: 104, title: "E-commerce UI", desc: "Maquetación con Tailwind", status: "progress", tech: "CSS", date: "2023-11-25" },
];

// Módulos específicos para Pensamiento Matemático
const mathModules = [
  { id: 1, title: "Toma de Decisiones y Datos", topics: "Análisis de datos, Azar e incertidumbre", status: "completed" },
  { id: 2, title: "Fundamentos Estadísticos", topics: "Población, muestra y recolección de datos", status: "completed" },
  { id: 3, title: "Representaciones Gráficas", topics: "Tablas de frecuencia y tipos de gráficas", status: "completed" },
  { id: 4, title: "Medidas de Tendencia Central", topics: "Media, mediana y moda", status: "completed" },
  { id: 5, title: "Medidas de Dispersión", topics: "Rango, varianza y desviación estándar", status: "completed" },
  { id: 6, title: "Probabilidad Clásica", topics: "Regla de Laplace, Frecuencia relativa", status: "completed" },
  { id: 7, title: "Probabilidad Avanzada", topics: "Probabilidad condicional e independencia", status: "completed" },
  { id: 8, title: "Fundamentos Algebraicos", topics: "Lenguaje algebraico, variables y números reales", status: "current" },
  { id: 9, title: "Modelación Lineal", topics: "Ecuaciones lineales y sus propiedades", status: "locked" },
  { id: 10, title: "Sistemas de Ecuaciones", topics: "Resolución de sistemas de ecuaciones lineales", status: "locked" },
];

// Datos de los Mentores
const mentorsData = [
  { 
    id: 'newton', 
    name: 'Isaac Newton', 
    role: 'Físico y Matemático', 
    description: 'Enfoque riguroso basado en principios fundamentales y cálculo.',
    icon: <Atom size={32} className="text-orange-600" />,
    avatar: "https://upload.wikimedia.org/wikipedia/commons/3/39/GodfreyKneller-IsaacNewton-1689.jpg", 
    color: 'bg-orange-50 border-orange-200 hover:border-orange-400',
    buttonColor: 'bg-orange-600 hover:bg-orange-700',
    welcomeMessage: "Saludos. La naturaleza es un libro escrito en lenguaje matemático. Estoy aquí para ayudarte a leerlo con precisión.",
    suggestions: ["¿Qué son los números reales?", "Explícame el lenguaje algebraico", "Diferencia entre variable y constante"]
  },
  { 
    id: 'raava', 
    name: 'Raava', 
    role: 'Mentora IA', 
    description: 'Guía adaptativa que evoluciona contigo y tu estilo de aprendizaje.',
    icon: <Sparkles size={32} className="text-indigo-600" />,
    avatar: "https://img.freepik.com/free-vector/ai-technology-microchip-background-vector-digital-transformation-concept_53876-112222.jpg", 
    color: 'bg-indigo-50 border-indigo-200 hover:border-indigo-400',
    buttonColor: 'bg-indigo-600 hover:bg-indigo-700',
    welcomeMessage: "Hola 👋 He analizado tu progreso. Estoy lista para adaptar la lección a tu ritmo.",
    suggestions: ["Resumir el tema actual", "Dame un ejemplo práctico", "¿Cómo se aplica esto en la vida real?"]
  },
  { 
    id: 'einstein', 
    name: 'Albert Einstein', 
    role: 'Físico Teórico', 
    description: 'Aprendizaje a través de la imaginación, la curiosidad y el pensamiento creativo.',
    icon: <Brain size={32} className="text-teal-600" />,
    avatar: "https://upload.wikimedia.org/wikipedia/commons/d/d3/Albert_Einstein_Head.jpg", 
    color: 'bg-teal-50 border-teal-200 hover:border-teal-400',
    buttonColor: 'bg-teal-600 hover:bg-teal-700',
    welcomeMessage: "¡Hola! 🎻 Recuerda que la imaginación es más importante que el conocimiento.",
    suggestions: ["Imagina un escenario para este tema", "Explícalo como si tuviera 5 años", "¿Por qué esto es importante?"]
  }
];

export default function App() {
  const [activeTab, setActiveTab] = useState('cursos');
  const [selectedCourse, setSelectedCourse] = useState(null);
  const [selectedModule, setSelectedModule] = useState(null); 
  
  // Estados de Flujo
  const [showMentorSelection, setShowMentorSelection] = useState(false);
  const [showOnboarding, setShowOnboarding] = useState(false);
  const [activeMentor, setActiveMentor] = useState(null); 
  
  // Estados de Chat y Audio
  const [sessionId] = useState(() => "user_" + Math.random().toString(36).substr(2, 9));
  const [chatMessages, setChatMessages] = useState([]);
  const [inputText, setInputText] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [voiceMode, setVoiceMode] = useState(false); 
  const [copiedIndex, setCopiedIndex] = useState(null); // Feedback de copiado
  
  // Estados de Proyectos (Kanban)
  const [projects, setProjects] = useState(initialProjects);
  const [newProjectName, setNewProjectName] = useState("");

  // Estado para Búsqueda (Solución Genérica)
  const [searchTerm, setSearchTerm] = useState("");
  
  // Datos del Onboarding
  const [userData, setUserData] = useState({
    nombre: "",
    pasion: "",
    meta: "",
    aprendizaje: "visual" 
  });

  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const chatEndRef = useRef(null);

  useEffect(() => {
    // Scroll mejorado: espera un tick para asegurar que el DOM se actualizó
    setTimeout(() => {
      chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }, 100);
  }, [chatMessages, isLoading]);

  // --- LOGICA DE PROYECTOS (KANBAN) ---
  const addProject = () => {
    if (!newProjectName.trim()) return;
    const newProj = {
      id: Date.now(),
      title: newProjectName,
      desc: "Nuevo proyecto personal",
      status: "todo",
      tech: "General",
      date: new Date().toISOString().split('T')[0]
    };
    setProjects([...projects, newProj]);
    setNewProjectName("");
  };

  const deleteProject = (id) => {
    setProjects(projects.filter(p => p.id !== id));
  };

  const moveProject = (id, direction) => {
    const statusOrder = ["todo", "progress", "done"];
    setProjects(projects.map(p => {
      if (p.id === id) {
        const currentIndex = statusOrder.indexOf(p.status);
        const newIndex = currentIndex + direction;
        if (newIndex >= 0 && newIndex < statusOrder.length) {
          return { ...p, status: statusOrder[newIndex] };
        }
      }
      return p;
    }));
  };

  // --- FUNCIONES DE COMUNICACIÓN CON BACKEND ---
  const initSessionInBackend = async () => {
    setIsLoading(true);
    try {
      await fetch(`${BACKEND_URL}/init_session`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          mentor_id: activeMentor.id,
          user_data: userData,
          current_topic: selectedModule ? `${selectedModule.title}: ${selectedModule.description}` : "General"
        })
      });
      setChatMessages([{ role: 'assistant', content: activeMentor.welcomeMessage }]);
    } catch (error) {
      console.error("Error iniciando sesión:", error);
      // Fallback para demo si falla el backend
      setChatMessages([{ role: 'assistant', content: activeMentor.welcomeMessage + " (Modo Offline)" }]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSendMessage = async (textOverride = null) => {
    const messageToSend = textOverride || inputText;
    if (!messageToSend.trim()) return;
    
    setInputText(""); 
    setChatMessages(prev => [...prev, { role: 'user', content: messageToSend }]);
    setIsLoading(true);
    
    try {
      const response = await fetch(`${BACKEND_URL}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          message: messageToSend,
          mentor_id: activeMentor.id,
          user_context: userData, 
          current_topic: selectedModule ? selectedModule.title : "General"
        })
      });
      const data = await response.json();
      if (data.error) throw new Error(data.error);
      setChatMessages(prev => [...prev, { role: 'assistant', content: data.reply }]);
      if (voiceMode) handleSpeak(data.reply);
    } catch (error) {
      console.error("Error sending message:", error);
      setChatMessages(prev => [...prev, { role: 'system', content: "Lo siento, tuve un problema de conexión. ¿Puedes intentarlo de nuevo?" }]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSpeak = async (text) => {
    try {
      const response = await fetch(`${BACKEND_URL}/talk`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: text, mentor_id: activeMentor.id })
      });
      if (!response.ok) throw new Error("Error generating audio");
      const blob = await response.blob();
      const audioUrl = URL.createObjectURL(blob);
      const audio = new Audio(audioUrl);
      audio.play();
    } catch (error) {
      console.error("Error TTS:", error);
    }
  };

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaRecorderRef.current = new MediaRecorder(stream);
      audioChunksRef.current = [];
      mediaRecorderRef.current.ondataavailable = (event) => audioChunksRef.current.push(event.data);
      mediaRecorderRef.current.onstop = async () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/wav' });
        await sendAudioToBackend(audioBlob);
      };
      mediaRecorderRef.current.start();
      setIsRecording(true);
    } catch (error) {
      console.error("Error accessing microphone:", error);
      alert("No se pudo acceder al micrófono.");
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
      mediaRecorderRef.current.stream.getTracks().forEach(track => track.stop());
    }
  };

  const sendAudioToBackend = async (audioBlob) => {
    setIsLoading(true);
    const formData = new FormData();
    formData.append("audio", audioBlob);
    try {
      const response = await fetch(`${BACKEND_URL}/listen`, { method: 'POST', body: formData });
      const data = await response.json();
      if (data.text) {
        if (voiceMode) {
            setChatMessages(prev => [...prev, { role: 'user', content: data.text }]);
            const chatRes = await fetch(`${BACKEND_URL}/chat`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                  session_id: sessionId,
                  message: data.text,
                  mentor_id: activeMentor.id,
                  user_context: userData, 
                  current_topic: selectedModule ? selectedModule.title : "General"
                })
            });
            const chatData = await chatRes.json();
            setChatMessages(prev => [...prev, { role: 'assistant', content: chatData.reply }]);
            handleSpeak(chatData.reply);
        } else {
            setInputText(data.text);
        }
      }
    } catch (error) {
      console.error("Error STT:", error);
    } finally {
      setIsLoading(false);
    }
  };

  const toggleRecording = () => {
    if (isRecording) stopRecording();
    else startRecording();
  };

  const copyToClipboard = (text, idx) => {
    navigator.clipboard.writeText(text);
    setCopiedIndex(idx);
    setTimeout(() => setCopiedIndex(null), 2000);
  };

  // --- NAVEGACIÓN ---
  const handleStartLesson = () => setShowMentorSelection(true);
  const handleMentorSelect = (mentor) => {
    setActiveMentor(mentor);
    setShowMentorSelection(false);
    setShowOnboarding(true); 
  };
  const finishOnboarding = () => {
    if (!userData.nombre) { alert("Por favor dinos tu nombre para continuar."); return; }
    setShowOnboarding(false);
    initSessionInBackend(); 
  };

  // --- VISTAS AUXILIARES ---
  const renderOnboarding = () => (
    <div className="flex flex-col items-center justify-center min-h-[60vh] animate-in fade-in zoom-in-95 duration-500">
        <div className="w-full max-w-lg bg-white rounded-2xl shadow-xl border border-gray-100 p-8">
            <div className="text-center mb-8">
                <div className="mx-auto w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center mb-4 text-blue-600"><UserCheck size={32} /></div>
                <h2 className="text-2xl font-bold text-gray-800">Configuremos tu Experiencia</h2>
                <p className="text-gray-500 text-sm mt-2">Ayuda a {activeMentor?.name} a entenderte mejor para personalizar la lección de <span className="font-semibold text-blue-600"> {selectedModule?.title}</span>.</p>
            </div>
            <div className="space-y-5">
                <div><label className="block text-sm font-medium text-gray-700 mb-1">¿Cómo te llamas?</label><input type="text" value={userData.nombre || ""} onChange={(e) => setUserData({...userData, nombre: e.target.value})} className="w-full border border-gray-300 rounded-lg p-3 focus:ring-2 focus:ring-blue-500 focus:outline-none" placeholder="Tu nombre o apodo"/></div>
                <div><label className="block text-sm font-medium text-gray-700 mb-1">¿Qué te apasiona?</label><input type="text" value={userData.pasion || ""} onChange={(e) => setUserData({...userData, pasion: e.target.value})} className="w-full border border-gray-300 rounded-lg p-3 focus:ring-2 focus:ring-blue-500 focus:outline-none" placeholder="Ej. Fútbol, Música, Videojuegos, Arte..."/></div>
                <div><label className="block text-sm font-medium text-gray-700 mb-1">¿Cuál es tu meta con este curso?</label><input type="text" value={userData.meta || ""} onChange={(e) => setUserData({...userData, meta: e.target.value})} className="w-full border border-gray-300 rounded-lg p-3 focus:ring-2 focus:ring-blue-500 focus:outline-none" placeholder="Ej. Aprobar el examen, Entender álgebra..."/></div>
                <div><label className="block text-sm font-medium text-gray-700 mb-2">Tu estilo de aprendizaje</label><div className="grid grid-cols-2 gap-3">{['Visual 👁️', 'Auditivo 👂', 'Práctico ✋', 'Teórico 📚'].map((style) => (<button key={style} onClick={() => setUserData({...userData, aprendizaje: style})} className={`p-3 rounded-lg text-sm border transition-all ${userData.aprendizaje === style ? 'bg-blue-50 border-blue-500 text-blue-700 font-medium' : 'border-gray-200 hover:bg-gray-50 text-gray-600'}`}>{style}</button>))}</div></div>
                <button onClick={finishOnboarding} className="w-full bg-blue-600 hover:bg-blue-700 text-white font-bold py-3.5 rounded-xl shadow-md transition-all mt-4 flex items-center justify-center gap-2">Comenzar Lección <ChevronRight size={20} /></button>
            </div>
        </div>
    </div>
  );

  const renderCallInterface = () => (
    <div className="fixed inset-0 z-50 bg-gray-900 flex flex-col items-center justify-between p-6 animate-in slide-in-from-bottom duration-500">
        <div className="w-full flex justify-between items-center text-white/80">
            <button onClick={() => setVoiceMode(false)} className="p-2 bg-white/10 rounded-full hover:bg-white/20"><ChevronLeft /></button>
            <div className="flex flex-col items-center"><span className="text-sm font-medium tracking-wide uppercase text-green-400 flex items-center gap-2"><span className="w-2 h-2 bg-green-400 rounded-full animate-pulse"></span> En llamada</span><span className="text-xs opacity-60">Fiscamp Audio Secure</span></div>
            <button className="p-2 bg-white/10 rounded-full hover:bg-white/20"><MoreVertical /></button>
        </div>
        <div className="flex-1 flex flex-col items-center justify-center w-full max-w-md relative">
            <div className="absolute inset-0 flex items-center justify-center pointer-events-none"><div className={`w-64 h-64 rounded-full border border-white/10 ${isLoading ? 'animate-ping' : ''}`}></div><div className={`w-80 h-80 rounded-full border border-white/5 absolute ${isLoading ? 'animate-pulse' : ''}`}></div></div>
            <div className="relative z-10 flex flex-col items-center">
                <div className="w-32 h-32 rounded-full overflow-hidden border-4 border-white/20 shadow-2xl mb-6"><div className="w-full h-full bg-gradient-to-br from-gray-700 to-gray-900 flex items-center justify-center">{React.cloneElement(activeMentor.icon, { size: 64, className: "text-white" })}</div></div>
                <h2 className="text-3xl font-bold text-white mb-2">{activeMentor.name}</h2>
                <p className="text-white/60 text-lg text-center px-4">{isLoading ? "Pensando..." : isRecording ? "Escuchando..." : "Mentor Virtual"}</p>
                {(isLoading || isRecording) && (<div className="flex gap-1 mt-8 h-8 items-center">{[...Array(5)].map((_, i) => (<div key={i} className="w-2 bg-white rounded-full animate-music" style={{ height: `${Math.random() * 100}%`, animationDelay: `${i * 0.1}s` }}></div>))}</div>)}
            </div>
        </div>
        <div className="w-full max-w-md bg-white/10 backdrop-blur-md rounded-3xl p-6 flex justify-around items-center">
            <button className="p-4 rounded-full bg-white/10 hover:bg-white/20 text-white transition-all"><Volume2 size={24} /></button>
            <button onClick={toggleRecording} className={`p-6 rounded-full transition-all shadow-lg transform active:scale-95 ${isRecording ? 'bg-red-500 text-white hover:bg-red-600 ring-4 ring-red-500/30' : 'bg-white text-gray-900 hover:bg-gray-100'}`}>{isRecording ? <StopCircle size={32} /> : <Mic size={32} />}</button>
            <button onClick={() => setVoiceMode(false)} className="p-4 rounded-full bg-red-500/80 hover:bg-red-600 text-white transition-all"><Phone size={24} className="rotate-[135deg]" /></button>
        </div>
        <style>{`@keyframes music { 0%, 100% { height: 20%; opacity: 0.5; } 50% { height: 100%; opacity: 1; } } .animate-music { animation: music 0.8s ease-in-out infinite; }`}</style>
    </div>
  );

  const renderChatInterface = () => (
    <div className="flex flex-col h-[calc(100vh-140px)] bg-white animate-in fade-in duration-300 relative rounded-2xl overflow-hidden shadow-lg border border-gray-100">
      {voiceMode && renderCallInterface()}
      
      {/* Header del Chat */}
      <div className="px-5 py-3 border-b border-gray-100 flex justify-between items-center bg-white sticky top-0 z-10 shadow-sm backdrop-blur-sm bg-white/90">
        <div className="flex items-center gap-4">
            <button onClick={() => setActiveMentor(null)} className="hover:bg-gray-50 rounded-full p-2 -ml-2 transition-colors text-gray-600 hover:text-gray-900">
                <ChevronLeft size={24} />
            </button>
            <div className="relative cursor-pointer group">
                <div className="w-10 h-10 rounded-full overflow-hidden bg-gray-50 flex items-center justify-center border border-gray-200 transition-transform group-hover:scale-105">
                    {React.cloneElement(activeMentor.icon, { size: 20 })}
                </div>
                <div className="absolute bottom-0 right-0 w-3 h-3 bg-green-500 border-2 border-white rounded-full"></div>
            </div>
            <div className="flex flex-col cursor-pointer">
                <h3 className="font-bold text-gray-900 text-sm leading-tight flex items-center gap-1">
                    {activeMentor.name}
                    <span className="text-[10px] bg-blue-50 text-blue-600 px-1.5 py-0.5 rounded font-medium tracking-wide">AI</span>
                </h3>
                <p className="text-xs text-gray-400 font-medium truncate max-w-[150px]">{selectedModule?.title || "Conversación General"}</p>
            </div>
        </div>
        <div className="flex items-center gap-2 text-gray-500">
            <button onClick={() => setVoiceMode(true)} className="p-2.5 rounded-full transition-all hover:bg-green-50 text-gray-500 hover:text-green-600" title="Iniciar llamada de voz">
                <Phone size={20} strokeWidth={2} />
            </button>
            <button className="p-2.5 rounded-full hover:bg-gray-50 hover:text-gray-700 transition-colors">
                <Video size={20} strokeWidth={2} className="opacity-50" />
            </button>
        </div>
      </div>

      {/* Area de Mensajes */}
      <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-6 bg-gradient-to-b from-gray-50/50 to-white">
        <div className="flex justify-center mb-6">
            <span className="px-3 py-1 bg-gray-100 text-gray-400 rounded-full text-[10px] font-bold tracking-wider uppercase shadow-sm">
                Hoy, {new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}
            </span>
        </div>
        
        {chatMessages.map((msg, idx) => (
          <div key={idx} className={`flex items-start gap-3 group ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}>
            
            {/* Avatar */}
            <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 mt-1 shadow-sm ${msg.role === 'assistant' ? 'bg-white border border-gray-100' : 'bg-blue-600 text-white'}`}>
                {msg.role === 'assistant' ? React.cloneElement(activeMentor.icon, { size: 16, className: "text-gray-700" }) : <User size={16} />}
            </div>

            {/* Burbuja de Mensaje */}
            <div className={`relative flex flex-col gap-1 max-w-[80%] sm:max-w-[70%]`}>
                <div className={`px-5 py-3.5 rounded-2xl text-[15px] shadow-sm leading-relaxed ${
                    msg.role === 'user' 
                    ? 'bg-blue-600 text-white rounded-tr-sm' 
                    : 'bg-white text-gray-800 border border-gray-100 rounded-tl-sm'
                }`}>
                    {/* Renderizado con Formato */}
                    <FormattedText text={msg.content} />
                </div>
                
                {/* Botones de utilidad para el Asistente */}
                {msg.role === 'assistant' && (
                    <div className="flex gap-2 opacity-0 group-hover:opacity-100 transition-opacity ml-1">
                        <button 
                            onClick={() => copyToClipboard(msg.content, idx)}
                            className="text-gray-400 hover:text-blue-500 transition-colors flex items-center gap-1 text-xs"
                        >
                            {copiedIndex === idx ? <Check size={12}/> : <Copy size={12}/>}
                            {copiedIndex === idx ? "Copiado" : "Copiar"}
                        </button>
                    </div>
                )}
            </div>
          </div>
        ))}

        {/* Indicador de "Pensando..." */}
        {isLoading && (
            <div className="flex items-start gap-3 animate-pulse">
                <div className="w-8 h-8 rounded-full bg-white border border-gray-100 flex items-center justify-center flex-shrink-0 mt-1 shadow-sm">
                    {React.cloneElement(activeMentor.icon, { size: 16, className: "text-gray-400" })}
                </div>
                <div className="bg-white border border-gray-100 px-4 py-3 rounded-2xl rounded-tl-sm shadow-sm flex items-center gap-2">
                    <span className="text-xs text-gray-400 font-medium">Pensando</span>
                    <div className="flex gap-1">
                        <div className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce"></div>
                        <div className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce delay-100"></div>
                        <div className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce delay-200"></div>
                    </div>
                </div>
            </div>
        )}
        <div ref={chatEndRef} />
      </div>

      {/* Input Area */}
      <div className="p-4 bg-white border-t border-gray-100">
        
        {/* Sugerencias Rápidas (Chips) */}
        {!isLoading && chatMessages.length < 4 && (
            <div className="flex gap-2 mb-3 overflow-x-auto pb-1 hide-scrollbar">
                {activeMentor.suggestions.map((suggestion, idx) => (
                    <button 
                        key={idx} 
                        onClick={() => handleSendMessage(suggestion)}
                        className="whitespace-nowrap px-3 py-1.5 bg-gray-50 border border-gray-200 rounded-full text-xs text-gray-600 hover:bg-blue-50 hover:text-blue-600 hover:border-blue-200 transition-all flex-shrink-0"
                    >
                        {suggestion}
                    </button>
                ))}
            </div>
        )}

        <div className="flex items-end gap-2 bg-gray-50 p-2 rounded-3xl border border-gray-200 focus-within:border-blue-300 focus-within:ring-4 focus-within:ring-blue-50 transition-all shadow-sm">
           <button className="p-2.5 text-gray-400 hover:text-blue-500 hover:bg-white rounded-full transition-colors flex-shrink-0 active:scale-95">
             <Plus size={20} strokeWidth={2.5} />
           </button>
           
           <div className="flex-1 py-2.5">
             <input 
                type="text" 
                value={inputText || ""} 
                onChange={(e) => setInputText(e.target.value)} 
                onKeyDown={(e) => e.key === 'Enter' && handleSendMessage()} 
                placeholder={isRecording ? "Escuchando tu voz..." : `Mensaje a ${activeMentor.name}...`} 
                disabled={isRecording || isLoading} 
                className="w-full bg-transparent border-none focus:ring-0 p-0 text-sm text-gray-900 placeholder-gray-400" 
             />
           </div>

           <div className="flex items-center gap-1 pr-1">
               {inputText.trim() ? (
                   <button 
                      onClick={() => handleSendMessage()} 
                      disabled={isLoading}
                      className="p-2 bg-blue-600 text-white rounded-full hover:bg-blue-700 shadow-md transform active:scale-90 transition-all flex items-center justify-center"
                   >
                      <Send size={18} className="ml-0.5" />
                   </button>
               ) : (
                   <button 
                      onClick={toggleRecording} 
                      className={`p-2.5 rounded-full transition-all ${isRecording ? 'bg-red-100 text-red-500 animate-pulse' : 'text-gray-400 hover:text-gray-600 hover:bg-white'}`}
                   >
                      {isRecording ? <StopCircle size={22} /> : <Mic size={22} />}
                   </button>
               )}
           </div>
        </div>
        <div className="text-center mt-2">
            <p className="text-[10px] text-gray-300">Raava AI puede cometer errores. Verifica la información importante.</p>
        </div>
      </div>
    </div>
  );

  // --- VISTA KANBAN (PROYECTOS) ---
  const renderProjectsKanban = () => {
    const columns = [
      { id: 'todo', title: '💡 Ideas / Por hacer', color: 'border-yellow-400', bg: 'bg-yellow-50' },
      { id: 'progress', title: '🔨 En Desarrollo', color: 'border-blue-400', bg: 'bg-blue-50' },
      { id: 'done', title: '✅ Completado', color: 'border-green-400', bg: 'bg-green-50' }
    ];

    return (
      <div className="h-full flex flex-col animate-in fade-in duration-500">
        <div className="flex justify-between items-center mb-6">
          <div>
            <h2 className="text-2xl font-bold text-gray-800">Mis Proyectos</h2>
            <p className="text-sm text-gray-500">Organiza tus tareas y portafolio.</p>
          </div>
          <div className="flex gap-2">
             <input 
                type="text" 
                value={newProjectName || ""}
                onChange={(e) => setNewProjectName(e.target.value)}
                placeholder="Nuevo proyecto..."
                className="px-4 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
             />
             <button onClick={addProject} className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg flex items-center gap-2 text-sm font-medium transition-colors">
                <Plus size={18} /> Crear
             </button>
          </div>
        </div>

        <div className="flex-1 overflow-x-auto">
          <div className="flex gap-6 min-w-[800px] h-full pb-4">
            {columns.map(col => (
              <div key={col.id} className={`flex-1 min-w-[280px] bg-gray-50 rounded-xl p-4 border-t-4 ${col.color} shadow-sm flex flex-col`}>
                <h3 className="font-bold text-gray-700 mb-4 flex justify-between items-center">
                  {col.title}
                  <span className="bg-white px-2 py-0.5 rounded-full text-xs text-gray-500 shadow-sm border border-gray-100">
                    {projects.filter(p => p.status === col.id).length}
                  </span>
                </h3>
                
                <div className="flex-1 overflow-y-auto space-y-3">
                  {projects.filter(p => p.status === col.id).map(proj => (
                    <div key={proj.id} className="bg-white p-4 rounded-lg shadow-sm border border-gray-100 hover:shadow-md transition-shadow group">
                      <div className="flex justify-between items-start mb-2">
                         <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase bg-gray-100 text-gray-600">{proj.tech}</span>
                         <button onClick={() => deleteProject(proj.id)} className="text-gray-300 hover:text-red-500 transition-colors opacity-0 group-hover:opacity-100">
                           <Trash2 size={14} />
                         </button>
                      </div>
                      <h4 className="font-semibold text-gray-800 mb-1">{proj.title}</h4>
                      <p className="text-xs text-gray-500 mb-3">{proj.desc}</p>
                      
                      <div className="flex items-center justify-between text-xs text-gray-400 mt-2 pt-2 border-t border-gray-50">
                        <span className="flex items-center gap-1"><Calendar size={12} /> {proj.date}</span>
                        <div className="flex gap-1">
                          {col.id !== 'todo' && (
                            <button onClick={() => moveProject(proj.id, -1)} className="p-1 hover:bg-gray-100 rounded text-gray-600" title="Mover atrás"><ArrowLeft size={14}/></button>
                          )}
                          {col.id !== 'done' && (
                            <button onClick={() => moveProject(proj.id, 1)} className="p-1 hover:bg-gray-100 rounded text-gray-600" title="Mover adelante"><ArrowRight size={14}/></button>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                  {projects.filter(p => p.status === col.id).length === 0 && (
                    <div className="text-center py-8 text-gray-400 text-sm italic border-2 border-dashed border-gray-200 rounded-lg">
                      Vacío
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  };

  // --- ROUTING PRINCIPAL ---

  const renderCourseModules = () => (
    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
      <button onClick={() => setSelectedCourse(null)} className="flex items-center gap-2 text-gray-500 hover:text-blue-600 transition-colors mb-4">
        <ArrowLeft size={20} /> Volver a Mis Cursos
      </button>

      <div className="bg-white p-6 rounded-2xl border border-gray-100 shadow-sm relative overflow-hidden">
        <div className={`absolute top-0 left-0 w-2 h-full ${selectedCourse.color}`}></div>
        <h2 className="text-2xl font-bold text-gray-800 mb-2">{selectedCourse.title}</h2>
        <div className="flex items-center gap-4 text-sm text-gray-500">
           <span className="flex items-center gap-1"><User size={16}/> {selectedCourse.instructor}</span>
           <span className="flex items-center gap-1"><Clock size={16}/> 45 min restantes</span>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4">
        <h3 className="font-semibold text-gray-700 ml-1">Temario del Curso</h3>
        {mathModules.map((module) => (
          <div key={module.id} className={`bg-white p-5 rounded-xl border transition-all ${module.status === 'locked' ? 'border-gray-100 opacity-70' : 'border-gray-200 hover:border-blue-300 hover:shadow-md'}`}>
             <div className="flex justify-between items-start mb-3">
               <div>
                 <h4 className="font-bold text-gray-800 text-lg flex items-center gap-2">
                    {module.status === 'completed' && <CheckCircle size={18} className="text-green-500"/>}
                    {module.status === 'locked' && <Lock size={18} className="text-gray-400"/>}
                    {module.title}
                 </h4>
                 <p className="text-sm text-gray-500 mt-1">{module.topics}</p>
               </div>
             </div>
             <button 
                onClick={() => { 
                    if(module.status !== 'locked') {
                        setSelectedModule(module); 
                        setShowMentorSelection(true); 
                    }
                }} 
                disabled={module.status === 'locked'}
                className={`w-full py-2.5 rounded-lg font-medium text-sm flex items-center justify-center gap-2 transition-colors ${module.status === 'locked' ? 'bg-gray-100 text-gray-400 cursor-not-allowed' : 'bg-blue-50 text-blue-600 hover:bg-blue-600 hover:text-white'}`}
             >
               {module.status === 'locked' ? 'Bloqueado' : 'Comenzar Lección'} <ChevronRight size={16}/>
             </button>
          </div>
        ))}
      </div>
    </div>
  );

  const renderMentorSelection = () => (
    <div className="animate-in zoom-in-95 duration-300">
       <button onClick={() => { setShowMentorSelection(false); setSelectedModule(null); }} className="mb-6 flex items-center text-gray-500 hover:text-gray-700 gap-2">
         <ArrowLeft size={20}/> Cambiar de tema
       </button>
       
       <div className="text-center mb-10">
           <h2 className="text-3xl font-bold text-gray-800">Elige tu Guía</h2>
           <p className="text-gray-500 mt-2">Selecciona quién te acompañará en <span className="text-blue-600 font-medium">{selectedModule?.title}</span></p>
       </div>

       <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
         {mentorsData.map((mentor) => (
           <div key={mentor.id} onClick={() => handleMentorSelect(mentor)} className={`cursor-pointer bg-white p-6 rounded-2xl border-2 transition-all hover:-translate-y-2 hover:shadow-xl group ${mentor.color}`}>
              <div className="w-20 h-20 mx-auto bg-white rounded-full flex items-center justify-center mb-4 shadow-sm group-hover:scale-110 transition-transform">
                {mentor.icon}
              </div>
              <h3 className="text-xl font-bold text-center text-gray-800">{mentor.name}</h3>
              <p className="text-center text-xs font-bold uppercase tracking-wider text-blue-600 mb-3">{mentor.role}</p>
              <p className="text-center text-sm text-gray-600 italic">"{mentor.description}"</p>
              <div className={`mt-6 py-2 rounded-lg text-center text-sm font-bold text-white opacity-0 group-hover:opacity-100 transition-opacity ${mentor.buttonColor}`}>
                  Seleccionar
              </div>
           </div>
         ))}
       </div>
    </div>
  );

  const renderModuleDetail = () => (
     renderMentorSelection() 
  );
  
  const renderContent = () => {
    if (activeMentor && showOnboarding) return renderOnboarding();
    if (activeMentor) return renderChatInterface();
    if (showMentorSelection) return renderMentorSelection();
    if (selectedModule) return renderModuleDetail();
    if (selectedCourse) return renderCourseModules();

    switch (activeTab) {
      case 'cursos':
        return (
          <div className="space-y-6 animate-in fade-in duration-500">
            <div className="flex justify-between items-center">
              <h2 className="text-2xl font-bold text-gray-800">Mis Cursos Activos</h2>
              {/* SOLUCIÓN GENÉRICA Y FUNCIONAL: Búsqueda controlada */}
              <div className="relative">
                <input 
                  type="text" 
                  value={searchTerm || ""} 
                  onChange={(e) => setSearchTerm(e.target.value)} 
                  placeholder="Buscar curso..." 
                  className="pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
                />
                <Search className="absolute left-3 top-2.5 h-4 w-4 text-gray-400" />
              </div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {/* Filtrado de cursos */}
              {initialCourses
                .filter(course => course.title.toLowerCase().includes(searchTerm.toLowerCase()))
                .map((course) => (
                <div key={course.id} className="bg-white rounded-xl shadow-sm border border-gray-100 hover:shadow-md transition-shadow duration-200 overflow-hidden flex flex-col h-full">
                  <div className={`h-3 ${course.color} w-full`}></div>
                  <div className="p-6 flex-1 flex flex-col">
                    <div className="flex justify-between items-start mb-4"><div className={`p-2 rounded-lg ${course.color} bg-opacity-10`}><BookOpen className={`h-6 w-6 ${course.color.replace('bg-', 'text-')}`} /></div><button className="text-gray-400 hover:text-gray-600"><MoreVertical size={18} /></button></div>
                    <h3 className="font-semibold text-lg text-gray-800 mb-1">{course.title}</h3>
                    <p className="text-sm text-gray-500 mb-4">{course.instructor}</p>
                    <div className="mt-auto">
                      <div className="flex justify-between text-xs text-gray-500 mb-1"><span>Progreso</span><span>{course.progress}%</span></div>
                      <div className="w-full bg-gray-100 rounded-full h-2 mb-4"><div className={`h-2 rounded-full ${course.color}`} style={{ width: `${course.progress}%` }}></div></div>
                      <button onClick={() => { if (course.title === "Pensamiento Matemático") { setSelectedCourse(course); setSelectedModule(null); setShowMentorSelection(false); setActiveMentor(null); } else { alert("Solo 'Pensamiento Matemático' tiene módulos detallados."); } }} className="w-full py-2 px-4 border border-gray-200 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-50 hover:text-blue-600 transition-colors flex items-center justify-center gap-2">Continuar <ChevronRight size={16} /></button>
                    </div>
                  </div>
                </div>
              ))}
              {/* Mensaje si no hay resultados */}
              {initialCourses.filter(course => course.title.toLowerCase().includes(searchTerm.toLowerCase())).length === 0 && (
                <div className="col-span-full text-center py-10 text-gray-400 italic">No se encontraron cursos.</div>
              )}
            </div>
          </div>
        );
      case 'proyectos':
        return renderProjectsKanban();
      case 'consultas':
        return <div className="flex flex-col items-center justify-center h-[60vh] text-center space-y-4 animate-in fade-in duration-500"><Clock className="h-12 w-12 text-yellow-600" /><h2 className="text-xl font-semibold text-gray-800">Consultas Recientes</h2><p className="text-gray-500">En construcción.</p></div>;
      default: return null;
    }
  };

  return (
    <div className="flex h-screen bg-gray-50 font-sans">
      <aside className="w-64 bg-white border-r border-gray-200 flex flex-col flex-shrink-0 hidden md:flex">
        <div className="p-6 border-b border-gray-100">
          <div className="flex items-center gap-3 mb-4"><div className="h-12 w-12 rounded-full bg-blue-100 flex items-center justify-center border-2 border-white shadow-sm text-blue-600"><User size={24} /></div><div><h3 className="font-bold text-gray-800 text-sm">Usuario Estudiante</h3><span className="text-xs text-green-600 font-medium bg-green-50 px-2 py-0.5 rounded-full">Online</span></div></div>
          <div className="flex gap-2"><button className="flex-1 text-xs bg-gray-100 hover:bg-gray-200 text-gray-600 py-1.5 rounded transition-colors text-center">Perfil</button><button className="p-1.5 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded transition-colors"><Settings size={16} /></button></div>
        </div>
        <nav className="flex-1 overflow-y-auto py-6 px-3 space-y-1">
          <p className="px-3 text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">Principal</p>
          <button onClick={() => { setActiveTab('cursos'); setSelectedCourse(null); setSelectedModule(null); setShowMentorSelection(false); setActiveMentor(null); setShowOnboarding(false); }} className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${activeTab === 'cursos' && !selectedCourse ? 'bg-blue-50 text-blue-700' : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'}`}><BookOpen size={20} /> Mis Cursos</button>
          <button onClick={() => setActiveTab('proyectos')} className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${activeTab === 'proyectos' ? 'bg-purple-50 text-purple-700' : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'}`}><FolderGit2 size={20} /> Proyectos Personales</button>
          <button onClick={() => setActiveTab('consultas')} className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${activeTab === 'consultas' ? 'bg-yellow-50 text-yellow-700' : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'}`}><Clock size={20} /> Consultas Recientes</button>
        </nav>
        <div className="p-4 border-t border-gray-100"><button className="w-full flex items-center gap-3 px-3 py-2 text-sm font-medium text-red-600 hover:bg-red-50 rounded-lg transition-colors"><LogOut size={20} /> Cerrar Sesión</button></div>
      </aside>
      <main className="flex-1 overflow-y-auto p-4 md:p-8 relative">
        <header className="mb-8 flex justify-between items-center">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">{activeMentor ? 'Sala de Estudio' : showMentorSelection ? 'Configuración de Aprendizaje' : selectedModule ? 'Lección en Curso' : selectedCourse ? 'Detalle del Curso' : activeTab === 'cursos' ? 'Panel de Aprendizaje' : activeTab === 'proyectos' ? 'Gestión de Proyectos' : 'Historial'}</h1>
            <p className="text-gray-500 text-sm mt-1">{activeMentor ? `Conversando con ${activeMentor.name}` : showMentorSelection ? 'Elige a tu guía para comenzar.' : selectedModule ? `Estudiando: ${selectedModule.title}` : selectedCourse ? `Explorando el contenido de ${selectedCourse.title}` : 'Bienvenido de nuevo.'}</p>
          </div>
          <div className="flex items-center gap-3"><button className="p-2 text-gray-400 hover:text-yellow-500 hover:bg-yellow-50 rounded-full transition-colors"><Star size={20} /></button><div className="h-8 w-8 bg-gray-200 rounded-full border-2 border-white shadow-sm flex items-center justify-center text-xs font-bold text-gray-500">US</div></div>
        </header>
        {renderContent()}
      </main>
    </div>
  );
}
