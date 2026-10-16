import React from 'react';
import ReactDOM from 'react-dom/client';
import JARVIS from './JARVIS_Frontend';

// Sin StrictMode: en desarrollo monta los efectos dos veces y el WebSocket
// cerrado de la primera vez marcaría la pantalla como desconectada.
ReactDOM.createRoot(document.getElementById('root')).render(<JARVIS />);
