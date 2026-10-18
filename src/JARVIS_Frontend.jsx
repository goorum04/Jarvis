import React, { useCallback, useEffect, useRef, useState } from 'react';
import BootSequence from './BootSequence';
import ConexionesPanel from './ConexionesPanel';
import DashboardPanel from './DashboardPanel';
import HoloCore from './HoloCore';
import { apiBase, wsUrl } from './config';
import './hud.css';

const STATUS_COLORS = {
  listening: '#ffb547',
  processing: '#25c8f2',
  speaking: '#bff3ff',
  error: '#ff4d5e',
  disconnected: '#7fa3b5',
  reminder: '#ff4fd8',
  ready: '#3ddc84',
};

const STATUS_TEXT = {
  listening: 'Escuchando',
  processing: 'Procesando',
  speaking: 'Hablando',
  error: 'Error',
  disconnected: 'Desconectado',
  reminder: 'Recordatorio',
  ready: 'Listo',
};

// El arranque se ve una vez por sesión. En las pruebas automáticas no sale
// (salvo con ?boot=1, para verlo).
const shouldBoot = () => {
  const forced = new URLSearchParams(window.location.search).get('boot') === '1';
  if (forced) return true;
  if (navigator.webdriver) return false;
  try {
    return !sessionStorage.getItem('jarvis_booted');
  } catch (e) {
    return true;
  }
};

const MicIcon = ({ listening, speaking }) => {
  if (listening) {
    return (
      <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><rect x="7" y="7" width="10" height="10" rx="2" /></svg>
    );
  }
  if (speaking) {
    return (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" aria-hidden="true">
        <path d="M4 10v4M8 7v10M12 4v16M16 7v10M20 10v4" />
      </svg>
    );
  }
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" aria-hidden="true">
      <rect x="9" y="3" width="6" height="11" rx="3" fill="currentColor" />
      <path d="M5 11a7 7 0 0 0 14 0M12 18v3M8.5 21h7" />
    </svg>
  );
};

const Clock = () => {
  const [now, setNow] = useState(new Date());
  useEffect(() => {
    const timer = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);
  return (
    <>
      <span className="hud-date">{now.toLocaleDateString('es-ES', { weekday: 'long', day: 'numeric', month: 'long' }).toUpperCase()}</span>
      <span className="hud-clock">{now.toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}</span>
    </>
  );
};

const JARVIS = () => {
  // Estados
  const [isListening, setIsListening] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [status, setStatus] = useState('ready');
  const [transcript, setTranscript] = useState('');
  const [response, setResponse] = useState('');
  const [history, setHistory] = useState([]);
  // Cambia cuando JARVIS termina de hablar: el panel se refresca por si algo cambió.
  const [refreshKey, setRefreshKey] = useState(0);
  // Sección «Conexiones»: se abre con el botón o al volver de conectar una cuenta.
  const [showConexiones, setShowConexiones] = useState(window.location.hash === '#conexiones');
  const [booting, setBooting] = useState(() => shouldBoot() && window.location.hash !== '#conexiones');

  // Referencias
  const wsRef = useRef(null);
  const recognitionRef = useRef(null);
  // Ref para evitar closure obsoleto en onend de SpeechRecognition
  const transcriptRef = useRef('');
  // Frases de audio pendientes de reproducir, en orden de llegada
  const audioQueueRef = useRef([]);
  const playingRef = useRef(false);
  const responseDoneRef = useRef(true);
  const responseTextRef = useRef('');
  // Análisis de la voz de JARVIS para que el núcleo «hable» con ella
  const audioCtxRef = useRef(null);
  const analyserRef = useRef(null);
  const levelBufRef = useRef(null);
  const routedRef = useRef(false);

  // Inicializar WebSocket
  useEffect(() => {
    initializeWebSocket();
    initializeSpeechRecognition();

    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
    // Solo al montar: conectar una vez el WebSocket y el reconocimiento de voz.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // El contexto de audio solo puede arrancar tras un toque del usuario.
  const ensureAudio = () => {
    const Ctx = window.AudioContext || window.webkitAudioContext;
    if (!Ctx) return null;
    if (!audioCtxRef.current) {
      try {
        audioCtxRef.current = new Ctx();
        analyserRef.current = audioCtxRef.current.createAnalyser();
        analyserRef.current.fftSize = 512;
        analyserRef.current.connect(audioCtxRef.current.destination);
        levelBufRef.current = new Uint8Array(analyserRef.current.fftSize);
      } catch (e) {
        audioCtxRef.current = null;
        return null;
      }
    }
    if (audioCtxRef.current.state === 'suspended') {
      audioCtxRef.current.resume().catch(() => {});
    }
    return audioCtxRef.current;
  };

  // Pequeños sonidos de interfaz, sintetizados (sin archivos).
  const chirp = (up) => {
    const ctx = ensureAudio();
    if (!ctx || ctx.state !== 'running') return;
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    const t = ctx.currentTime;
    osc.type = 'sine';
    osc.frequency.setValueAtTime(up ? 520 : 1040, t);
    osc.frequency.exponentialRampToValueAtTime(up ? 1040 : 520, t + 0.14);
    gain.gain.setValueAtTime(0.0001, t);
    gain.gain.exponentialRampToValueAtTime(0.06, t + 0.02);
    gain.gain.exponentialRampToValueAtTime(0.0001, t + 0.18);
    osc.connect(gain).connect(ctx.destination);
    osc.start(t);
    osc.stop(t + 0.2);
  };

  const getLevel = useCallback(() => {
    const analyser = analyserRef.current;
    if (!playingRef.current) return 0;
    if (!analyser || !routedRef.current) {
      // Sin análisis (p. ej. sin permiso de audio todavía): un pulso parecido a una voz.
      const t = Date.now() / 1000;
      return 0.35 + 0.25 * Math.abs(Math.sin(t * 7.3) * Math.sin(t * 3.1));
    }
    const buf = levelBufRef.current;
    analyser.getByteTimeDomainData(buf);
    let sum = 0;
    for (let i = 0; i < buf.length; i += 1) {
      const v = (buf[i] - 128) / 128;
      sum += v * v;
    }
    return Math.min(1, Math.sqrt(sum / buf.length) * 3.4);
  }, []);

  const initializeWebSocket = () => {
    wsRef.current = new WebSocket(wsUrl);

    wsRef.current.onopen = () => {
      console.log('✅ Conectado a JARVIS');
      setStatus('ready');
    };

    wsRef.current.onmessage = (event) => {
      const data = JSON.parse(event.data);

      switch (data.type) {
        case 'status':
          setStatus(data.status);
          break;
        case 'response_chunk':
          if (responseDoneRef.current) {
            responseDoneRef.current = false;
            responseTextRef.current = '';
          }
          responseTextRef.current = `${responseTextRef.current} ${data.text}`.trim();
          setResponse(responseTextRef.current);
          if (data.audio) {
            enqueueAudio(data.audio);
          }
          break;
        case 'response_done':
          responseDoneRef.current = true;
          setHistory(prev => [...prev, { type: 'user', text: transcriptRef.current }, { type: 'assistant', text: responseTextRef.current }]);
          setRefreshKey(k => k + 1);
          if (!playingRef.current) {
            setStatus('ready');
          }
          break;
        case 'error':
          console.error('Error:', data.message);
          setStatus('error');
          break;
        case 'proactive_reminder':
          setResponse(data.text);
          setStatus('reminder');
          setRefreshKey(k => k + 1);
          if (data.audio) {
            enqueueAudio(data.audio);
          }
          break;
        default:
          break;
      }
    };

    wsRef.current.onerror = (error) => {
      console.error('WebSocket error:', error);
      setStatus('error');
    };

    wsRef.current.onclose = () => {
      console.log('❌ Desconectado de JARVIS');
      setStatus('disconnected');
    };
  };

  const initializeSpeechRecognition = () => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      console.error('Speech Recognition no soportado');
      return;
    }

    recognitionRef.current = new SpeechRecognition();
    recognitionRef.current.continuous = false;
    recognitionRef.current.interimResults = true;
    recognitionRef.current.lang = 'es-ES';

    recognitionRef.current.onstart = () => {
      setIsListening(true);
      setStatus('listening');
    };

    recognitionRef.current.onresult = (event) => {
      let interimTranscript = '';
      let finalTranscript = '';

      for (let i = event.resultIndex; i < event.results.length; i++) {
        const transcriptSegment = event.results[i][0].transcript;
        if (event.results[i].isFinal) {
          finalTranscript += transcriptSegment + ' ';
        } else {
          interimTranscript += transcriptSegment;
        }
      }

      if (finalTranscript) {
        transcriptRef.current = finalTranscript.trim();
        setTranscript(finalTranscript.trim());
      } else {
        transcriptRef.current = interimTranscript;
        setTranscript(interimTranscript);
      }
    };

    recognitionRef.current.onend = () => {
      setIsListening(false);
      chirp(false);
      if (transcriptRef.current && wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        sendMessage(transcriptRef.current);
      }
    };

    recognitionRef.current.onerror = (event) => {
      console.error('Speech Recognition error:', event.error);
      setStatus('error');
    };
  };

  const sendMessage = (text) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        type: 'audio',
        text: text || transcript
      }));
      setStatus('processing');
    }
  };

  const enqueueAudio = (base64Audio) => {
    audioQueueRef.current.push(base64Audio);
    if (!playingRef.current) {
      playNextAudio();
    }
  };

  const playNextAudio = () => {
    const base64Audio = audioQueueRef.current.shift();
    if (!base64Audio) {
      playingRef.current = false;
      setIsSpeaking(false);
      if (responseDoneRef.current) {
        setStatus('ready');
      }
      return;
    }

    playingRef.current = true;
    const binaryString = atob(base64Audio);
    const bytes = new Uint8Array(binaryString.length);
    for (let i = 0; i < binaryString.length; i++) {
      bytes[i] = binaryString.charCodeAt(i);
    }
    const url = URL.createObjectURL(new Blob([bytes], { type: 'audio/mp3' }));

    const audio = new Audio(url);
    // Solo se pasa por el analizador si el audio ya está desbloqueado: si no,
    // se oiría en silencio.
    routedRef.current = false;
    const ctx = audioCtxRef.current;
    if (ctx && ctx.state === 'running' && analyserRef.current) {
      try {
        ctx.createMediaElementSource(audio).connect(analyserRef.current);
        routedRef.current = true;
      } catch (e) {
        routedRef.current = false;
      }
    }
    audio.onplay = () => {
      setIsSpeaking(true);
    };
    const next = () => {
      URL.revokeObjectURL(url);
      playNextAudio();
    };
    audio.onended = next;
    audio.onerror = next;
    audio.play().catch(next);
  };

  const startListening = () => {
    if (recognitionRef.current) {
      setTranscript('');
      recognitionRef.current.start();
    }
  };

  const stopListening = () => {
    if (recognitionRef.current) {
      recognitionRef.current.stop();
    }
  };

  const handleMicClick = () => {
    ensureAudio();
    if (isListening) {
      stopListening();
    } else {
      chirp(true);
      startListening();
    }
  };

  const coreStatus = isSpeaking ? 'speaking' : (STATUS_TEXT[status] ? status : 'ready');
  const statusColor = STATUS_COLORS[coreStatus];
  const statusText = STATUS_TEXT[status] || 'Listo';

  return (
    <div className="hud j-container">
      <div className="hud-bg j-background" aria-hidden="true">
        <div className="hud-bg-image" style={{ backgroundImage: 'url(/holo/fondo.webp)' }} />
        <div className="hud-grid" />
        <div className="hud-scan" />
        <div className="hud-vignette" />
      </div>

      <div className="hud-main j-main">
        <header className="hud-header">
          <div className="hud-brand">
            <span className="hud-dot" style={{ color: statusColor, background: statusColor }} />
            <h1 className="hud-title" data-text="J.A.R.V.I.S">J.A.R.V.I.S</h1>
          </div>
          <div className="hud-meta j-headerinfo">
            <Clock />
          </div>
        </header>

        <div className="hud-row j-row">
          {/* Izquierda: el núcleo y la conversación */}
          <section className="hud-left j-holo">
            <div className="hud-core-wrap">
              <HoloCore status={coreStatus} getLevel={getLevel} size={420} />
            </div>

            <div className="holo-card hud-comms">
              <div className="holo-label" style={{ '--accent': '#ffb547', '--accent-rgb': '255,181,71' }}>Entrada</div>
              <div className="hud-transcript">{transcript || '…esperando entrada…'}</div>
              <div className="holo-label" style={{ marginTop: 6 }}>Salida</div>
              <div className="hud-response">{response || '…'}</div>
            </div>

            {history.length > 0 && (
              <div className="holo-card hud-history j-history">
                <div className="holo-label">Registro</div>
                {history.slice(-8).map((msg, i) => (
                  <div key={i} className="hud-history-item" style={{ color: msg.type === 'user' ? '#ffd79a' : '#bff3ff' }}>
                    <span>{msg.type === 'user' ? 'TÚ ›' : 'JARVIS ›'}</span>
                    {msg.text.length > 120 ? `${msg.text.substring(0, 120)}…` : msg.text}
                  </div>
                ))}
              </div>
            )}
          </section>

          {/* Derecha: el día de Nacho */}
          <DashboardPanel refreshKey={refreshKey} />
        </div>

        {/* Controles */}
        <footer className="hud-controls j-controls">
          <button
            onClick={handleMicClick}
            disabled={status === 'disconnected'}
            className={`hud-mic ${isListening ? 'is-listening' : ''}`}
            aria-label={isListening ? 'Terminar de hablar' : 'Hablar con JARVIS'}
            data-testid="mic"
          >
            <MicIcon listening={isListening} speaking={isSpeaking} />
          </button>

          <div className="hud-status j-status" style={{ color: statusColor }}>
            <i />
            <span>{statusText}</span>
          </div>

          <button
            onClick={() => {
              window.history.replaceState(null, '', `${window.location.pathname}${window.location.search}#conexiones`);
              setShowConexiones(true);
            }}
            className="hud-btn j-btn-conexiones"
            data-testid="abrir-conexiones"
          >
            Conexiones
          </button>

          <a href={`${apiBase}/guia/`} className="hud-btn j-btn-guia" data-testid="abrir-guia">
            Guía
          </a>

          <button
            onClick={() => {
              setHistory([]);
              setTranscript('');
              setResponse('');
            }}
            className="hud-btn hud-btn-warn j-clear"
          >
            Limpiar
          </button>
        </footer>
      </div>

      {showConexiones && (
        <ConexionesPanel
          onClose={() => {
            window.history.replaceState(null, '', `${window.location.pathname}${window.location.search}`);
            setShowConexiones(false);
            setRefreshKey((k) => k + 1);
          }}
        />
      )}

      {booting && (
        <BootSequence
          onDone={() => {
            try { sessionStorage.setItem('jarvis_booted', '1'); } catch (e) { /* sin almacenamiento */ }
            setBooting(false);
          }}
        />
      )}
    </div>
  );
};

export default JARVIS;
