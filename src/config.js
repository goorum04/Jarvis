// Dónde está el backend y con qué token se habla con él. Ambos se pueden
// pasar una vez en la URL (?token=...&api=https://jarvis.sudominio.com) y
// quedan recordados en este navegador.
const params = new URLSearchParams(window.location.search);

const remember = (param, key) => {
  const value = params.get(param);
  if (value) {
    localStorage.setItem(key, value);
  }
  return value || localStorage.getItem(key) || '';
};

export const token = remember('token', 'jarvis_token');

export const apiBase = (
  remember('api', 'jarvis_api') || `${window.location.protocol}//${window.location.hostname}:8000`
).replace(/\/$/, '');

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
