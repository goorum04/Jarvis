// Dónde está el backend y con qué token se habla con él. El token se pasa
// una vez en la URL (?token=...) y queda recordado en este navegador.
const params = new URLSearchParams(window.location.search);

const remember = (param, key) => {
  const value = params.get(param);
  if (value) {
    localStorage.setItem(key, value);
  }
  return value || localStorage.getItem(key) || '';
};

export const token = remember('token', 'jarvis_token');

// Normalmente el propio JARVIS sirve el panel, así que el backend está en la
// misma dirección. Solo en desarrollo (npm start, puerto 3000) va aparte.
const defaultApi = window.location.port === '3000'
  ? `${window.location.protocol}//${window.location.hostname}:8000`
  : window.location.origin;

export const apiBase = (remember('api', 'jarvis_api') || defaultApi).replace(/\/$/, '');

export const wsUrl = `${apiBase.replace(/^http/, 'ws')}/ws?token=${encodeURIComponent(token)}`;

export const apiGet = async (path) => {
  const response = await fetch(`${apiBase}${path}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  return response.json();
};

export const apiPost = async (path, body = {}) => {
  const response = await fetch(`${apiBase}${path}`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.detail || `HTTP ${response.status}`);
  }
  return data;
};
