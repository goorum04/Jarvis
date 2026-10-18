import React from 'react';
import ReactDOM from 'react-dom/client';
import JARVIS from './JARVIS_Frontend';
import { token } from './config';

// Al añadir el panel a la pantalla de inicio, el icono abre JARVIS ya con su
// acceso: el manifiesto lleva el token (allí no se comparte lo que recordaba Safari).
const manifest = document.getElementById('manifest');
if (manifest && token) {
  manifest.href = `/manifest.webmanifest?token=${encodeURIComponent(token)}`;
}

// Avisos propios y pantalla de «JARVIS está descansando» si el Mac no responde.
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').catch((e) => console.warn('Sin service worker:', e));
  });
}

// Sin StrictMode: en desarrollo monta los efectos dos veces y el WebSocket
// cerrado de la primera vez marcaría la pantalla como desconectada.
ReactDOM.createRoot(document.getElementById('root')).render(<JARVIS />);
