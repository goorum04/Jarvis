import React, { useCallback, useEffect, useState } from 'react';
import { apiBase, apiGet, apiPost } from './config';

// Sección «Conexiones»: Nacho conecta él mismo sus cuentas (iniciando sesión)
// y pega sus claves. Las claves van directas a su Mac; el panel nunca las
// vuelve a ver, solo sabe si están puestas.

const OWN_ACCOUNTS = ['google', 'mercedes', 'whoop', 'woocommerce', 'shopify'];

const SERVICE_NAMES = {
  google: 'Gmail, Calendar y Docs',
  mercedes: 'Mercedes me',
  whoop: 'la pulsera WHOOP',
  woocommerce: 'la tienda',
};

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

// Tras guardar algo, JARVIS se reinicia para aplicarlo: se espera a que vuelva.
const waitForRestart = async () => {
  await sleep(2500);
  for (let i = 0; i < 40; i += 1) {
    try {
      const response = await fetch(`${apiBase}/health`, { cache: 'no-store' });
      if (response.ok) {
        return true;
      }
    } catch (e) {
      // todavía arrancando
    }
    await sleep(1500);
  }
  return false;
};

// Mensaje al volver de iniciar sesión en Google, Mercedes o la tienda.
const readReturn = () => {
  const params = new URLSearchParams(window.location.search);
  const service = params.get('conexion');
  if (!service) {
    return null;
  }
  const failed = params.get('estado') === 'error';
  const name = SERVICE_NAMES[service] || service;
  const errorText = params.get('mensaje') || `No se ha podido conectar ${name}.`;
  // Se limpia la dirección para que el aviso no vuelva a salir al recargar.
  ['conexion', 'estado', 'mensaje'].forEach((key) => params.delete(key));
  const query = params.toString();
  window.history.replaceState(null, '', `${window.location.pathname}${query ? `?${query}` : ''}#conexiones`);
  return failed
    ? { error: true, text: errorText }
    : { error: false, text: `${name.charAt(0).toUpperCase()}${name.slice(1)}: conectado.` };
};

const Field = ({ field, value, onChange }) => (
  <label style={styles.field}>
    <span style={styles.fieldLabel}>
      {field.label}
      {field.optional && <span style={styles.optional}> (opcional)</span>}
    </span>
    <input
      style={styles.input}
      type={field.secret ? 'password' : 'text'}
      autoComplete="off"
      autoCapitalize="off"
      autoCorrect="off"
      spellCheck={false}
      value={value}
      placeholder={field.set ? (field.secret ? '•••••••• guardada' : field.value) : ''}
      onChange={(e) => onChange(field.env, e.target.value)}
      data-testid={`campo-${field.env}`}
    />
    {field.help && <span style={styles.help}>{field.help}</span>}
  </label>
);

const ServiceCard = ({ service, onChanged }) => {
  const [values, setValues] = useState({});
  const [busy, setBusy] = useState('');
  const [message, setMessage] = useState(null);
  const [showSetup, setShowSetup] = useState(!service.ready);

  const setValue = (env, value) => setValues((current) => ({ ...current, [env]: value }));
  const typed = (fields) => fields.some((f) => (values[f.env] || '').trim());

  const run = async (label, action) => {
    setBusy(label);
    setMessage(null);
    try {
      await action();
    } catch (e) {
      setMessage({ error: true, text: e.message });
    } finally {
      setBusy('');
    }
  };

  const save = (fields) => run('guardar', async () => {
    const payload = {};
    fields.forEach((f) => {
      if ((values[f.env] || '').trim()) {
        payload[f.env] = values[f.env];
      }
    });
    const result = await apiPost(`/api/conexiones/${service.id}/guardar`, { values: payload });
    setValues({});
    await onChanged(result.restarting, 'Guardado.');
  });

  const connect = () => run('conectar', async () => {
    const { url } = await apiPost(`/api/conexiones/${service.id}/iniciar`, { origin: window.location.origin });
    window.location.href = url;
  });

  const disconnect = () => run('desconectar', async () => {
    const result = await apiPost(`/api/conexiones/${service.id}/desconectar`);
    await onChanged(result.restarting, 'Desconectado.');
  });

  const test = () => run('probar', async () => {
    const result = await apiPost(`/api/conexiones/${service.id}/probar`);
    setMessage({
      error: !result.ok,
      text: result.results.map((r) => `${r.name}: ${r.detail}${r.fix && r.status !== 'ok' ? ` → ${r.fix}` : ''}`).join('\n'),
    });
  });

  const prepareCalls = () => run('preparar', async () => {
    const result = await apiPost('/api/conexiones/llamadas/preparar');
    await onChanged(true, result.output || (result.ok ? 'Listo.' : 'No se pudo preparar.'));
  });

  const status = service.connected
    ? { text: 'CONECTADO', color: '#00ff88' }
    : service.ready
      ? { text: 'SIN CONECTAR', color: '#ffaa00' }
      : { text: 'FALTA PREPARAR', color: '#ff6666' };

  const canConnect = service.kind !== 'keys';
  const fieldsSaved = service.fields.every((f) => f.optional || f.set);

  return (
    <div style={{ ...styles.card, borderColor: `${status.color}55` }} data-testid={`conexion-${service.id}`}>
      <div style={styles.cardHead}>
        <div style={styles.cardName}>{service.name}</div>
        <span style={{ ...styles.pill, color: status.color, borderColor: status.color }}>{status.text}</span>
      </div>
      <div style={styles.what}>{service.what}</div>
      {service.connected && service.account && (
        <div style={styles.account}>
          {service.account}
          {service.since && ` · desde ${service.since.substring(0, 10).split('-').reverse().join('/')}`}
        </div>
      )}

      {service.setup.length > 0 && (
        <div style={styles.setup}>
          <button type="button" style={styles.linkButton} onClick={() => setShowSetup(!showSetup)}>
            {showSetup ? '▾' : '▸'} Preparación (la hace una vez quien instala JARVIS)
          </button>
          {showSetup && (
            <>
              {service.setup.map((f) => <Field key={f.env} field={f} value={values[f.env] || ''} onChange={setValue} />)}
              <button type="button" style={styles.secondary} disabled={!!busy || !typed(service.setup)} onClick={() => save(service.setup)}>
                {busy === 'guardar' ? 'Guardando…' : 'Guardar preparación'}
              </button>
            </>
          )}
        </div>
      )}

      {service.fields.map((f) => <Field key={f.env} field={f} value={values[f.env] || ''} onChange={setValue} />)}
      {service.note && !service.connected && <div style={styles.note}>{service.note}</div>}
      {service.id === 'woocommerce' && service.needs_public_url && (
        <div style={styles.note}>Para conectar la tienda, JARVIS tiene que tener activa su dirección pública (Tailscale).</div>
      )}

      <div style={styles.actions}>
        {service.fields.length > 0 && (
          <button type="button" style={canConnect ? styles.secondary : styles.primary} disabled={!!busy || !typed(service.fields)} onClick={() => save(service.fields)}>
            {busy === 'guardar' ? 'Guardando…' : 'Guardar'}
          </button>
        )}
        {canConnect && (
          <button
            type="button"
            style={styles.primary}
            disabled={!!busy || !service.ready || !fieldsSaved || typed(service.fields) || (service.id === 'woocommerce' && service.needs_public_url)}
            onClick={connect}
            data-testid={`conectar-${service.id}`}
          >
            {busy === 'conectar' ? 'Abriendo…' : service.connected ? 'Volver a conectar' : 'Conectar'}
          </button>
        )}
        {service.id === 'llamadas' && service.keys_saved && !service.connected && (
          <button type="button" style={styles.primary} disabled={!!busy} onClick={prepareCalls}>
            {busy === 'preparar' ? 'Preparando…' : 'Preparar llamadas'}
          </button>
        )}
        {service.connected && (
          <button type="button" style={styles.secondary} disabled={!!busy} onClick={test}>
            {busy === 'probar' ? 'Probando…' : 'Probar'}
          </button>
        )}
        {service.connected && (
          <button type="button" style={styles.danger} disabled={!!busy} onClick={disconnect}>
            {busy === 'desconectar' ? 'Quitando…' : 'Desconectar'}
          </button>
        )}
        {service.link && (
          <a style={styles.link} href={service.link} target="_blank" rel="noreferrer">Dónde conseguir la clave ↗</a>
        )}
      </div>
      {message && (
        <div style={{ ...styles.message, color: message.error ? '#ff8888' : '#00ff88' }}>{message.text}</div>
      )}
    </div>
  );
};

const ConexionesPanel = ({ onClose }) => {
  const [services, setServices] = useState(null);
  const [error, setError] = useState('');
  const [banner, setBanner] = useState(() => readReturn());
  const [restarting, setRestarting] = useState(false);

  const load = useCallback(async () => {
    try {
      const result = await apiGet('/api/conexiones');
      setServices(result.services);
      setError('');
    } catch (e) {
      setError(e.message === 'HTTP 401'
        ? 'Este navegador no tiene el acceso de JARVIS. Abre el panel con el enlace que incluye el token.'
        : 'No se puede conectar con JARVIS.');
    }
  }, []);

  useEffect(() => {
    // Al volver de conectar Mercedes o la tienda, JARVIS puede estar reiniciándose.
    const start = async () => {
      if (banner && !banner.error) {
        setRestarting(true);
        await waitForRestart();
        setRestarting(false);
      }
      load();
    };
    start();
    // Solo al abrir.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const onChanged = async (restartingNow, text) => {
    if (restartingNow) {
      setRestarting(true);
      await waitForRestart();
      setRestarting(false);
    }
    setBanner({ error: false, text });
    await load();
  };

  const groups = services && [
    ['SUS CUENTAS', services.filter((s) => OWN_ACCOUNTS.includes(s.id))],
    ['SERVICIOS DE JARVIS', services.filter((s) => !OWN_ACCOUNTS.includes(s.id))],
  ];
  const connected = services ? services.filter((s) => s.connected).length : 0;

  return (
    <div style={styles.overlay} data-testid="conexiones">
      <div style={styles.inner}>
        <div style={styles.header}>
          <div>
            <h2 style={styles.title}>CONEXIONES</h2>
            {services && <div style={styles.subtitle}>{connected} de {services.length} conectadas</div>}
          </div>
          <button type="button" style={styles.close} onClick={onClose} aria-label="Cerrar">✕</button>
        </div>
        <p style={styles.intro}>
          Conecta tus cuentas iniciando sesión, o pega tus claves. Todo se guarda solo en tu Mac:
          nadie más las ve, ni siquiera desde este panel.
        </p>

        {restarting && <div style={styles.banner}>Aplicando los cambios: JARVIS se está reiniciando…</div>}
        {banner && !restarting && (
          <div style={{ ...styles.banner, borderColor: banner.error ? '#ff6666' : '#00ff88', color: banner.error ? '#ff9999' : '#00ff88' }}>
            {banner.text}
          </div>
        )}
        {error && <div style={{ ...styles.banner, borderColor: '#ff6666', color: '#ff9999' }}>{error}</div>}
        {!services && !error && <div style={styles.muted}>Cargando…</div>}

        {groups && groups.map(([title, list]) => (
          <div key={title} style={styles.group}>
            <div style={styles.groupTitle}>{title}</div>
            <div style={styles.grid}>
              {list.map((service) => <ServiceCard key={service.id} service={service} onChanged={onChanged} />)}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

const button = {
  padding: '9px 14px',
  borderRadius: '6px',
  fontSize: '13px',
  fontWeight: 'bold',
  letterSpacing: '1px',
  cursor: 'pointer',
  border: '1px solid #00d4ff',
};

const styles = {
  overlay: {
    position: 'fixed',
    inset: 0,
    zIndex: 50,
    background: 'rgba(5, 8, 12, 0.97)',
    overflowY: 'auto',
    WebkitOverflowScrolling: 'touch',
    paddingTop: 'env(safe-area-inset-top, 0px)',
    paddingBottom: 'env(safe-area-inset-bottom, 0px)',
  },
  inner: {
    maxWidth: '1100px',
    margin: '0 auto',
    paddingBlock: '24px',
    paddingLeft: 'max(16px, env(safe-area-inset-left, 0px))',
    paddingRight: 'max(16px, env(safe-area-inset-right, 0px))',
    color: '#cfefff',
  },
  header: { display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '12px' },
  title: { color: '#00d4ff', letterSpacing: '4px', fontSize: '22px', textShadow: '0 0 12px rgba(0,212,255,0.6)' },
  subtitle: { fontSize: '12px', opacity: 0.7, marginTop: '4px', letterSpacing: '1px' },
  close: { ...button, background: 'transparent', color: '#00d4ff', fontSize: '16px', padding: '6px 12px' },
  intro: { margin: '12px 0 16px', fontSize: '14px', opacity: 0.8, lineHeight: 1.5, maxWidth: '65ch' },
  banner: {
    border: '1px solid #00d4ff', borderRadius: '8px', padding: '10px 14px', marginBottom: '14px',
    fontSize: '14px', color: '#00d4ff', whiteSpace: 'pre-wrap',
  },
  muted: { opacity: 0.6, fontSize: '14px' },
  group: { marginTop: '18px' },
  groupTitle: { fontSize: '11px', letterSpacing: '3px', color: '#00d4ff', fontWeight: 'bold', marginBottom: '10px' },
  grid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(min(100%, 320px), 1fr))', gap: '12px' },
  card: {
    border: '1px solid', borderRadius: '10px', padding: '14px 16px', background: 'rgba(0,212,255,0.04)',
    display: 'flex', flexDirection: 'column', gap: '10px', minWidth: 0,
  },
  cardHead: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '8px', flexWrap: 'wrap' },
  cardName: { fontSize: '16px', fontWeight: 'bold', color: '#e6f8ff' },
  pill: { fontSize: '10px', letterSpacing: '1.5px', border: '1px solid', borderRadius: '10px', padding: '2px 8px', fontWeight: 'bold' },
  what: { fontSize: '13px', opacity: 0.75, lineHeight: 1.4 },
  account: { fontSize: '13px', color: '#00ff88', overflowWrap: 'anywhere' },
  setup: { display: 'flex', flexDirection: 'column', gap: '10px', borderLeft: '2px solid rgba(255,102,102,0.4)', paddingLeft: '10px' },
  field: { display: 'flex', flexDirection: 'column', gap: '4px' },
  fieldLabel: { fontSize: '12px', letterSpacing: '0.5px', opacity: 0.85 },
  optional: { opacity: 0.6 },
  input: {
    background: 'rgba(0,0,0,0.5)', border: '1px solid rgba(0,212,255,0.35)', borderRadius: '6px',
    color: '#e6f8ff', padding: '9px 10px', fontSize: '16px', width: '100%', fontFamily: 'monospace',
  },
  help: { fontSize: '12px', opacity: 0.6 },
  note: { fontSize: '12px', opacity: 0.75, lineHeight: 1.4, borderLeft: '2px solid #ffaa00', paddingLeft: '8px' },
  actions: { display: 'flex', flexWrap: 'wrap', gap: '8px', alignItems: 'center' },
  primary: { ...button, background: '#00d4ff', color: '#001018' },
  secondary: { ...button, background: 'transparent', color: '#00d4ff' },
  danger: { ...button, background: 'transparent', color: '#ff8888', borderColor: '#ff8888' },
  linkButton: { background: 'none', border: 'none', color: '#ff9999', cursor: 'pointer', fontSize: '12px', textAlign: 'left', padding: 0 },
  link: { color: '#00d4ff', fontSize: '12px' },
  message: { fontSize: '13px', whiteSpace: 'pre-wrap', overflowWrap: 'anywhere', lineHeight: 1.4 },
};

export default ConexionesPanel;
