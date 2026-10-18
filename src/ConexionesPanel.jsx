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

const copyText = async (text) => {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch (e) {
    // Navegadores antiguos: se copia seleccionando un campo oculto.
    const area = document.createElement('textarea');
    area.value = text;
    area.setAttribute('readonly', '');
    area.style.position = 'fixed';
    area.style.opacity = '0';
    document.body.appendChild(area);
    area.select();
    const copied = document.execCommand('copy');
    document.body.removeChild(area);
    return copied;
  }
};

const CopyRow = ({ label, value, testId }) => {
  const [copied, setCopied] = useState(false);
  return (
    <div style={styles.copyRow}>
      <span style={styles.fieldLabel}>{label}</span>
      <div style={styles.copyLine}>
        <code style={styles.copyValue} data-testid={testId}>{value}</code>
        <button
          type="button"
          style={styles.secondary}
          onClick={async () => {
            setCopied(await copyText(value));
            setTimeout(() => setCopied(false), 2000);
          }}
        >
          {copied ? 'Copiado ✓' : 'Copiar'}
        </button>
      </div>
    </div>
  );
};

// Quien instala JARVIS le manda a Nacho un solo código con la identidad de las
// apps de Google, Mercedes y WHOOP y los enlaces de los Atajos.
const SetupCodeCard = ({ pending, onChanged }) => {
  const [open, setOpen] = useState(pending);
  const [code, setCode] = useState('');
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState(null);

  useEffect(() => setOpen(pending), [pending]);

  const apply = async () => {
    setBusy(true);
    setMessage(null);
    try {
      const result = await apiPost('/api/conexiones/preparacion', { code });
      setCode('');
      await onChanged(true, `Preparado: ${result.prepared.join(', ')}. Ya puedes conectar tus cuentas.`);
    } catch (e) {
      setMessage(e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div style={{ ...styles.card, borderColor: pending ? '#ffaa0055' : '#00d4ff33' }} data-testid="codigo-preparacion">
      <button type="button" style={{ ...styles.linkButton, color: '#00d4ff', fontSize: '15px', fontWeight: 'bold' }} onClick={() => setOpen(!open)}>
        {open ? '▾' : '▸'} Código de preparación
      </button>
      {open && (
        <>
          <div style={styles.what}>
            Si quien te instala JARVIS te ha enviado un código que empieza por <code>JARVIS1:</code>, pégalo aquí. Deja listas
            de una vez las conexiones con Google, Mercedes y WHOOP, y los Atajos del iPhone.
          </div>
          <textarea
            style={{ ...styles.input, minHeight: '80px', resize: 'vertical' }}
            value={code}
            onChange={(e) => setCode(e.target.value)}
            placeholder="JARVIS1:…"
            autoCapitalize="off"
            autoCorrect="off"
            spellCheck={false}
            data-testid="campo-codigo"
          />
          <div style={styles.actions}>
            <button type="button" style={styles.primary} disabled={busy || !code.trim()} onClick={apply} data-testid="aplicar-codigo">
              {busy ? 'Aplicando…' : 'Aplicar'}
            </button>
          </div>
          {message && <div style={{ ...styles.message, color: '#ff8888' }}>{message}</div>}
        </>
      )}
    </div>
  );
};

// Para llevar JARVIS al iPhone: el panel por QR, y la dirección y el token que
// piden los Atajos al añadirlos.
const IphoneCard = ({ info }) => (
  <div style={styles.card} data-testid="tu-iphone">
    <div style={styles.cardHead}>
      <div style={styles.cardName}>Tu iPhone</div>
    </div>
    {!info.public_url ? (
      <div style={styles.note}>
        Falta el acceso desde fuera de casa (Tailscale). Cuando esté, aquí saldrá el código para abrir el panel en el iPhone.
      </div>
    ) : (
      <>
        <div style={styles.iphoneRow}>
          {info.qr_svg && (
            // El SVG lo genera el propio JARVIS (no viene de fuera).
            // eslint-disable-next-line react/no-danger
            <div style={styles.qr} dangerouslySetInnerHTML={{ __html: info.qr_svg }} data-testid="qr" />
          )}
          <div style={{ ...styles.what, flex: 1, minWidth: '180px' }}>
            <strong>Con la app JARVIS:</strong> ábrela, pulsa <em>Escanear el código</em> y apunta a este código. Listo.<br /><br />
            <strong>Sin la app:</strong> apunta la cámara del iPhone a este código y toca el enlace. En Safari, botón
            Compartir → <em>Añadir a pantalla de inicio</em>.
          </div>
        </div>
        <div style={styles.what}>
          <strong>3.</strong> Los Atajos te piden la dirección y el token al añadirlos. Cópialos desde aquí (mejor con este panel abierto en el iPhone):
        </div>
        <CopyRow label="Dirección" value={info.public_url} testId="direccion" />
        <CopyRow label="Token" value={info.token} testId="token" />
      </>
    )}
    <div style={styles.what}><strong>Atajos de JARVIS</strong></div>
    {info.shortcuts.map((shortcut) => (
      <div key={shortcut.name} style={styles.shortcutRow}>
        {shortcut.url ? (
          <a style={styles.primaryLink} href={shortcut.url} target="_blank" rel="noreferrer">Añadir «{shortcut.name}»</a>
        ) : (
          <span style={styles.pendingShortcut}>«{shortcut.name}»: te lo enviará quien te instala JARVIS</span>
        )}
        <span style={styles.help}>{shortcut.help}</span>
      </div>
    ))}
  </div>
);

// ── Avisos propios de JARVIS en este dispositivo (Web Push) ──
const isIOS = () => /iPhone|iPad|iPod/.test(navigator.userAgent)
  || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
const isStandalone = () => window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone === true;
const pushSupported = () => 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window;

const deviceName = () => {
  const ua = navigator.userAgent;
  if (/iPhone/.test(ua)) return 'iPhone';
  if (/iPad/.test(ua) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1)) return 'iPad';
  if (/Android/.test(ua)) return 'Android';
  if (/Mac/.test(ua)) return 'Mac';
  return 'Navegador';
};

const keyBytes = (base64) => {
  const padded = (base64 + '='.repeat((4 - (base64.length % 4)) % 4)).replace(/-/g, '+').replace(/_/g, '/');
  return Uint8Array.from(atob(padded), (c) => c.charCodeAt(0));
};

const PushCard = () => {
  const [state, setState] = useState('cargando');
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState(null);
  const [devices, setDevices] = useState([]);

  const refresh = useCallback(async () => {
    try {
      setDevices((await apiGet('/api/push/devices')).devices);
    } catch (e) {
      setDevices([]);
    }
    if (!pushSupported()) {
      setState(isIOS() && !isStandalone() ? 'instalar' : 'sin-soporte');
      return;
    }
    if (Notification.permission === 'denied') {
      setState('bloqueado');
      return;
    }
    const registration = await navigator.serviceWorker.ready;
    const subscription = await registration.pushManager.getSubscription();
    setState(subscription ? 'activo' : 'inactivo');
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  const run = async (action) => {
    setBusy(true);
    setMessage(null);
    try {
      await action();
    } catch (e) {
      setMessage({ error: true, text: e.message });
    } finally {
      setBusy(false);
      refresh();
    }
  };

  const enable = () => run(async () => {
    const permission = await Notification.requestPermission();
    if (permission !== 'granted') {
      throw new Error('No has dado permiso para los avisos.');
    }
    const { public_key: publicKey } = await apiGet('/api/push/key');
    const registration = await navigator.serviceWorker.ready;
    const subscription = await registration.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: keyBytes(publicKey) });
    await apiPost('/api/push/subscribe', { subscription: subscription.toJSON(), device: deviceName() });
    await apiPost('/api/push/test');
    setMessage({ error: false, text: 'Activados. Te he mandado un aviso de prueba.' });
  });

  const disable = () => run(async () => {
    const registration = await navigator.serviceWorker.ready;
    const subscription = await registration.pushManager.getSubscription();
    if (subscription) {
      await apiPost('/api/push/unsubscribe', { subscription: subscription.toJSON() });
      await subscription.unsubscribe();
    }
    setMessage({ error: false, text: 'Desactivados en este dispositivo.' });
  });

  const test = () => run(async () => {
    const result = await apiPost('/api/push/test');
    setMessage({ error: !result.ok, text: result.ok ? 'Aviso de prueba enviado.' : 'No se ha podido entregar.' });
  });

  return (
    <div style={styles.card} data-testid="avisos-dispositivo">
      <div style={styles.cardHead}>
        <div style={styles.cardName}>Avisos en este dispositivo</div>
        {state === 'activo' && <span style={{ ...styles.pill, color: '#00ff88', borderColor: '#00ff88' }}>ACTIVADOS</span>}
      </div>
      <div style={styles.what}>Los avisos de JARVIS (recordatorios, gasolina, correo importante, hora de salir) con su propio icono, sin apps aparte.</div>
      {state === 'instalar' && (
        <div style={styles.note}>
          En el iPhone, primero añade este panel a la pantalla de inicio (Compartir → <em>Añadir a pantalla de inicio</em>),
          ábrelo desde su icono y vuelve aquí.
        </div>
      )}
      {state === 'sin-soporte' && <div style={styles.note}>Este navegador no admite avisos.</div>}
      {state === 'bloqueado' && (
        <div style={styles.note}>Los avisos están bloqueados. Actívalos en Ajustes → Notificaciones → JARVIS.</div>
      )}
      <div style={styles.actions}>
        {state === 'inactivo' && (
          <button type="button" style={styles.primary} disabled={busy} onClick={enable} data-testid="activar-avisos">
            {busy ? 'Activando…' : 'Activar avisos aquí'}
          </button>
        )}
        {state === 'activo' && (
          <>
            <button type="button" style={styles.secondary} disabled={busy} onClick={test}>Probar</button>
            <button type="button" style={styles.danger} disabled={busy} onClick={disable}>Desactivar aquí</button>
          </>
        )}
      </div>
      {devices.length > 0 && (
        <div style={styles.help}>
          Activados en: {devices.map((d) => d.device).join(', ')}
        </div>
      )}
      {message && <div style={{ ...styles.message, color: message.error ? '#ff8888' : '#00ff88' }}>{message.text}</div>}
    </div>
  );
};

const ConexionesPanel = ({ onClose }) => {
  const [services, setServices] = useState(null);
  const [error, setError] = useState('');
  const [banner, setBanner] = useState(() => readReturn());
  const [restarting, setRestarting] = useState(false);
  const [iphone, setIphone] = useState(null);

  const load = useCallback(async () => {
    try {
      const [result, iphoneInfo] = await Promise.all([apiGet('/api/conexiones'), apiGet('/api/conexiones/iphone')]);
      setServices(result.services);
      setIphone(iphoneInfo);
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
  // El código hace falta mientras alguna app de Google, Mercedes o WHOOP siga sin preparar.
  const setupPending = !!services && services.some((s) => s.setup.length > 0 && !s.ready);

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

        {services && iphone && (
          <div style={styles.group}>
            <div style={styles.groupTitle}>PRIMEROS PASOS</div>
            <div style={styles.grid}>
              <SetupCodeCard pending={setupPending} onChanged={onChanged} />
              <IphoneCard info={iphone} />
              <PushCard />
            </div>
          </div>
        )}

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
  copyRow: { display: 'flex', flexDirection: 'column', gap: '4px' },
  copyLine: { display: 'flex', gap: '8px', alignItems: 'center', minWidth: 0 },
  copyValue: {
    flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
    background: 'rgba(0,0,0,0.5)', border: '1px solid rgba(0,212,255,0.25)', borderRadius: '6px',
    padding: '8px 10px', fontSize: '13px', color: '#e6f8ff',
  },
  iphoneRow: { display: 'flex', gap: '14px', alignItems: 'center', flexWrap: 'wrap' },
  qr: { width: '150px', height: '150px', background: '#ffffff', padding: '6px', borderRadius: '8px', flexShrink: 0 },
  shortcutRow: { display: 'flex', flexDirection: 'column', gap: '2px', alignItems: 'flex-start' },
  primaryLink: {
    ...button, background: '#00d4ff', color: '#001018', textDecoration: 'none', display: 'inline-block',
  },
  pendingShortcut: { fontSize: '13px', color: '#ffaa00' },
  message: { fontSize: '13px', whiteSpace: 'pre-wrap', overflowWrap: 'anywhere', lineHeight: 1.4 },
};

export default ConexionesPanel;
