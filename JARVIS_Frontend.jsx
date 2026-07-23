import React, { useState, useEffect, useRef } from 'react';

const JARVIS = () => {
  // Estados
  const [isListening, setIsListening] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [status, setStatus] = useState('ready');
  const [transcript, setTranscript] = useState('');
  const [response, setResponse] = useState('');
  const [useGPT, setUseGPT] = useState(false);
  const [history, setHistory] = useState([]);
  const [waveIntensity, setWaveIntensity] = useState(0);

  // Referencias
  const wsRef = useRef(null);
  const recognitionRef = useRef(null);
  const audioRef = useRef(null);
  const animationRef = useRef(null);
  // Ref para evitar closure obsoleto en onend de SpeechRecognition
  const transcriptRef = useRef('');

  // Inicializar WebSocket
  useEffect(() => {
    initializeWebSocket();
    initializeSpeechRecognition();

    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
      if (animationRef.current) {
        clearInterval(animationRef.current);
      }
    };
  }, []);

  const initializeWebSocket = () => {
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${wsProtocol}//localhost:8000/ws`;

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
        case 'response':
          setResponse(data.text);
          setHistory(prev => [...prev, { type: 'user', text: transcriptRef.current }, { type: 'assistant', text: data.text }]);
          
          if (data.audio) {
            playAudio(data.audio);
          }
          break;
        case 'error':
          console.error('Error:', data.message);
          setStatus('error');
          break;
        case 'proactive_reminder':
          setResponse(data.text);
          setStatus('reminder');
          if (data.audio) {
            playAudio(data.audio);
          }
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
      animateWaves();
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
      if (animationRef.current) {
        clearInterval(animationRef.current);
        animationRef.current = null;
      }
      setWaveIntensity(0);
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
        text: text || transcript,
        use_gpt: useGPT
      }));
      setStatus('processing');
    }
  };

  const playAudio = (base64Audio) => {
    const binaryString = atob(base64Audio);
    const bytes = new Uint8Array(binaryString.length);
    for (let i = 0; i < binaryString.length; i++) {
      bytes[i] = binaryString.charCodeAt(i);
    }
    const blob = new Blob([bytes], { type: 'audio/mp3' });
    const url = URL.createObjectURL(blob);

    const audio = new Audio(url);
    audio.onplay = () => {
      setIsSpeaking(true);
      animateWaves();
    };
    audio.onended = () => {
      setIsSpeaking(false);
      setStatus('ready');
      setWaveIntensity(0);
      if (animationRef.current) {
        clearInterval(animationRef.current);
        animationRef.current = null;
      }
    };
    audio.play();
  };

  const animateWaves = () => {
    if (animationRef.current) {
      clearInterval(animationRef.current);
    }
    animationRef.current = setInterval(() => {
      setWaveIntensity(Math.sin(Date.now() / 200) * 50 + 50);
    }, 50);
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
    if (isListening) {
      stopListening();
    } else {
      startListening();
    }
  };

  const getStatusColor = () => {
    switch (status) {
      case 'listening': return '#00d4ff';
      case 'processing': return '#ff6600';
      case 'error': return '#ff3333';
      case 'reminder': return '#ff00ff';
      default: return '#00ff00';
    }
  };

  const getStatusText = () => {
    switch (status) {
      case 'listening': return 'Escuchando...';
      case 'processing': return 'Procesando...';
      case 'error': return 'Error';
      case 'disconnected': return 'Desconectado';
      case 'reminder': return 'Recordatorio';
      default: return 'Listo';
    }
  };

  return (
    <div style={styles.container}>
      {/* Fondo animado */}
      <div style={styles.background}>
        <div style={styles.gridLines}></div>
        <div style={styles.particles}></div>
      </div>

      {/* Contenedor principal */}
      <div style={styles.mainContainer}>
        {/* Parte superior - Interfaz holográfica */}
        <div style={styles.holographicDisplay}>
          <div style={styles.header}>
            <div style={{ ...styles.statusIndicator, backgroundColor: getStatusColor() }}></div>
            <h1 style={styles.title}>⬤ J.A.R.V.I.S</h1>
            <div style={styles.headerInfo}>
              <span style={styles.version}>v2.0</span>
              <span style={styles.model}>{useGPT ? 'GPT-4' : 'Claude 3.5'}</span>
            </div>
          </div>

          {/* Visualizador de ondas */}
          <div style={styles.waveContainer}>
            <svg style={styles.waveSvg} viewBox="0 0 400 150" preserveAspectRatio="none">
              <defs>
                <linearGradient id="waveGradient" x1="0%" y1="0%" x2="0%" y2="100%">
                  <stop offset="0%" stopColor="#00d4ff" stopOpacity="0.8" />
                  <stop offset="100%" stopColor="#0088ff" stopOpacity="0.2" />
                </linearGradient>
              </defs>
              
              {/* Ondas animadas */}
              {[0, 1, 2].map((i) => (
                <path
                  key={i}
                  d={generateWavePath(i, waveIntensity)}
                  fill="none"
                  stroke="url(#waveGradient)"
                  strokeWidth="2"
                  opacity={1 - i * 0.25}
                />
              ))}
            </svg>

            {/* Círculo central pulsante */}
            <div
              style={{
                ...styles.centerPulse,
                boxShadow: `0 0 ${20 + waveIntensity}px ${5 + waveIntensity}px rgba(0, 212, 255, ${0.3 + waveIntensity / 300})`
              }}
            ></div>
          </div>

          {/* Transcripción */}
          <div style={styles.transcriptContainer}>
            <div style={styles.label}>INPUT:</div>
            <div style={styles.transcript}>
              {transcript || '...esperando entrada...'}
            </div>
          </div>

          {/* Respuesta */}
          <div style={styles.responseContainer}>
            <div style={styles.label}>OUTPUT:</div>
            <div style={styles.response}>
              {response || isSpeaking ? response : '...'}
            </div>
          </div>

          {/* Historial */}
          <div style={styles.historyContainer}>
            <div style={styles.label}>HISTORIAL:</div>
            <div style={styles.history}>
              {history.slice(-6).map((msg, i) => (
                <div key={i} style={{
                  ...styles.historyItem,
                  color: msg.type === 'user' ? '#00ff00' : '#00d4ff'
                }}>
                  <span style={{ opacity: 0.6 }}>
                    {msg.type === 'user' ? '→ TÚ: ' : '⬤ JARVIS: '}
                  </span>
                  {msg.text.substring(0, 50)}...
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Parte inferior - Controles */}
        <div style={styles.controlPanel}>
          {/* Botón micrófono grande */}
          <button
            onClick={handleMicClick}
            disabled={status === 'disconnected'}
            style={{
              ...styles.micButton,
              backgroundColor: isListening ? '#ff6600' : '#00d4ff',
              boxShadow: `0 0 ${40 + waveIntensity}px ${isListening ? '#ff6600' : '#00d4ff'}`
            }}
          >
            <span style={styles.micIcon}>
              {isListening ? '🎤' : '🎧'}
            </span>
          </button>

          {/* Toggle GPT/Claude */}
          <div style={styles.toggleContainer}>
            <button
              onClick={() => setUseGPT(false)}
              style={{
                ...styles.toggleButton,
                backgroundColor: !useGPT ? '#00d4ff' : '#1a1a2e',
                color: !useGPT ? '#0a0a0a' : '#00d4ff'
              }}
            >
              CLAUDE
            </button>
            <button
              onClick={() => setUseGPT(true)}
              style={{
                ...styles.toggleButton,
                backgroundColor: useGPT ? '#00d4ff' : '#1a1a2e',
                color: useGPT ? '#0a0a0a' : '#00d4ff'
              }}
            >
              GPT-4
            </button>
          </div>

          {/* Estado */}
          <div style={styles.statusContainer}>
            <div style={{ ...styles.statusDot, backgroundColor: getStatusColor() }}></div>
            <span style={styles.statusText}>{getStatusText()}</span>
          </div>

          {/* Botón limpiar */}
          <button
            onClick={() => {
              setHistory([]);
              setTranscript('');
              setResponse('');
            }}
            style={styles.clearButton}
          >
            LIMPIAR
          </button>
        </div>
      </div>

      {/* Estilos globales */}
      <style>{`
        * {
          margin: 0;
          padding: 0;
          box-sizing: border-box;
        }
        
        body {
          background: #0a0a0a;
          color: #00d4ff;
          font-family: 'Arial', sans-serif;
          overflow: hidden;
        }
        
        button:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }
        
        @keyframes float {
          0%, 100% { transform: translateY(0px); }
          50% { transform: translateY(-10px); }
        }
        
        @keyframes glow {
          0%, 100% { opacity: 0.3; }
          50% { opacity: 0.8; }
        }
      `}</style>
    </div>
  );
};

// Función para generar las ondas
const generateWavePath = (waveIndex, intensity) => {
  const points = [];
  const amplitude = 30 + (intensity * 0.3);
  const frequency = 0.05;
  const phase = waveIndex * Math.PI / 3;

  for (let x = 0; x <= 400; x += 10) {
    const y = 75 + Math.sin((x * frequency) + phase) * amplitude;
    points.push(`${x},${y}`);
  }

  return `M ${points.join(' L ')}`;
};

// Estilos
const styles = {
  container: {
    width: '100vw',
    height: '100vh',
    background: '#0a0a0a',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    overflow: 'hidden',
    position: 'relative'
  },
  background: {
    position: 'absolute',
    width: '100%',
    height: '100%',
    background: 'radial-gradient(circle at center, rgba(0,212,255,0.05) 0%, transparent 70%)',
    zIndex: 0
  },
  gridLines: {
    position: 'absolute',
    width: '100%',
    height: '100%',
    backgroundImage: `linear-gradient(0deg, transparent 24%, rgba(0,212,255,.1) 25%, rgba(0,212,255,.1) 26%, transparent 27%, transparent 74%, rgba(0,212,255,.1) 75%, rgba(0,212,255,.1) 76%, transparent 77%, transparent),
                      linear-gradient(90deg, transparent 24%, rgba(0,212,255,.1) 25%, rgba(0,212,255,.1) 26%, transparent 27%, transparent 74%, rgba(0,212,255,.1) 75%, rgba(0,212,255,.1) 76%, transparent 77%, transparent)`,
    backgroundSize: '50px 50px',
    opacity: 0.1
  },
  particles: {
    position: 'absolute',
    width: '100%',
    height: '100%'
  },
  mainContainer: {
    width: '90%',
    maxWidth: '1000px',
    height: '90%',
    background: 'linear-gradient(135deg, rgba(26,26,46,0.8) 0%, rgba(10,10,20,0.9) 100%)',
    border: '2px solid #00d4ff',
    borderRadius: '15px',
    boxShadow: '0 0 40px rgba(0,212,255,0.3), inset 0 0 40px rgba(0,212,255,0.05)',
    zIndex: 10,
    display: 'flex',
    flexDirection: 'column',
    padding: '30px',
    gap: '20px',
    overflow: 'auto'
  },
  holographicDisplay: {
    flex: 1,
    display: 'flex',
    flexDirection: 'column',
    gap: '15px',
    minHeight: 0
  },
  header: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingBottom: '15px',
    borderBottom: '1px solid rgba(0,212,255,0.3)',
    gap: '20px'
  },
  statusIndicator: {
    width: '12px',
    height: '12px',
    borderRadius: '50%',
    animation: 'glow 2s infinite'
  },
  title: {
    fontSize: '24px',
    color: '#00d4ff',
    fontWeight: 'bold',
    letterSpacing: '3px',
    flex: 1
  },
  headerInfo: {
    display: 'flex',
    gap: '15px',
    fontSize: '12px',
    opacity: 0.7
  },
  version: {
    color: '#00ff00'
  },
  model: {
    color: '#ff6600'
  },
  waveContainer: {
    height: '150px',
    position: 'relative',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    margin: '20px 0'
  },
  waveSvg: {
    width: '100%',
    height: '100%'
  },
  centerPulse: {
    position: 'absolute',
    width: '20px',
    height: '20px',
    borderRadius: '50%',
    backgroundColor: '#00d4ff',
    left: '50%',
    top: '50%',
    transform: 'translate(-50%, -50%)'
  },
  transcriptContainer: {
    flex: 0.8
  },
  responseContainer: {
    flex: 1
  },
  historyContainer: {
    flex: 0.6,
    overflowY: 'auto'
  },
  label: {
    fontSize: '11px',
    color: '#00ff00',
    letterSpacing: '2px',
    marginBottom: '8px',
    opacity: 0.7,
    fontWeight: 'bold'
  },
  transcript: {
    padding: '10px 15px',
    background: 'rgba(0,255,0,0.05)',
    border: '1px solid rgba(0,255,0,0.2)',
    borderRadius: '5px',
    color: '#00ff00',
    fontSize: '14px',
    minHeight: '30px',
    fontStyle: 'italic'
  },
  response: {
    padding: '10px 15px',
    background: 'rgba(0,212,255,0.05)',
    border: '1px solid rgba(0,212,255,0.2)',
    borderRadius: '5px',
    color: '#00d4ff',
    fontSize: '14px',
    minHeight: '60px',
    overflowY: 'auto'
  },
  history: {
    display: 'flex',
    flexDirection: 'column',
    gap: '5px',
    fontSize: '12px',
    maxHeight: '100px',
    overflowY: 'auto',
    paddingRight: '10px'
  },
  historyItem: {
    padding: '5px 10px',
    background: 'rgba(0,100,150,0.1)',
    borderRadius: '3px',
    wordBreak: 'break-word'
  },
  controlPanel: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '30px',
    padding: '20px',
    borderTop: '1px solid rgba(0,212,255,0.3)',
    flexWrap: 'wrap'
  },
  micButton: {
    width: '80px',
    height: '80px',
    borderRadius: '50%',
    border: '2px solid #00d4ff',
    background: '#00d4ff',
    color: '#0a0a0a',
    fontSize: '40px',
    cursor: 'pointer',
    transition: 'all 0.3s ease',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontWeight: 'bold'
  },
  micIcon: {
    display: 'block',
    lineHeight: '1'
  },
  toggleContainer: {
    display: 'flex',
    gap: '10px',
    background: 'rgba(0,0,0,0.3)',
    padding: '5px',
    borderRadius: '5px',
    border: '1px solid rgba(0,212,255,0.2)'
  },
  toggleButton: {
    padding: '8px 16px',
    border: 'none',
    borderRadius: '3px',
    cursor: 'pointer',
    fontSize: '12px',
    fontWeight: 'bold',
    letterSpacing: '1px',
    transition: 'all 0.3s ease'
  },
  statusContainer: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    padding: '8px 15px',
    background: 'rgba(0,0,0,0.3)',
    borderRadius: '5px',
    border: '1px solid rgba(0,212,255,0.2)'
  },
  statusDot: {
    width: '8px',
    height: '8px',
    borderRadius: '50%',
    animation: 'glow 1.5s infinite'
  },
  statusText: {
    fontSize: '12px',
    letterSpacing: '1px',
    fontWeight: 'bold'
  },
  clearButton: {
    padding: '8px 16px',
    background: 'rgba(255,102,0,0.2)',
    border: '1px solid #ff6600',
    color: '#ff6600',
    borderRadius: '5px',
    cursor: 'pointer',
    fontSize: '12px',
    fontWeight: 'bold',
    letterSpacing: '1px',
    transition: 'all 0.3s ease'
  }
};

export default JARVIS;
