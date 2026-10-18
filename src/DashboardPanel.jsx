import React, { useEffect, useRef, useState } from 'react';
import { apiGet } from './config';

const REFRESH_MS = 60 * 1000;

// Las horas se muestran en la zona horaria de JARVIS, no en la del dispositivo.
const time = (iso, timeZone) => {
  if (!iso || !iso.includes('T')) {
    return 'Todo el día';
  }
  if (!/([zZ]|[+-]\d\d:\d\d)$/.test(iso)) {
    return iso.substring(11, 16); // ya está en hora local de JARVIS (recordatorios)
  }
  return new Date(iso).toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit', timeZone });
};

const money = (amount, currency) =>
  new Intl.NumberFormat('es-ES', { style: 'currency', currency: currency || 'EUR' }).format(amount || 0);

// Los mismos colores con los que la app de WHOOP muestra la recuperación.
const ZONE_COLORS = { verde: '#16ec06', amarilla: '#ffde00', roja: '#ff0026' };

const hoursText = (minutes) => {
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return m ? `${h} h ${String(m).padStart(2, '0')}` : `${h} h`;
};

// [clave, abreviatura, cómo la nombra JARVIS en sus avisos]
const TIRE_ORDER = [
  ['front_left', 'DI', 'delantera izquierda'], ['front_right', 'DD', 'delantera derecha'],
  ['rear_left', 'TI', 'trasera izquierda'], ['rear_right', 'TD', 'trasera derecha'],
];

// Una línea legible para cada acción del registro.
const describeAction = (d) =>
  d.title || d.subject || (d.contact && d.text ? `${d.contact} · ${d.text}` : d.contact) || d.to || d.name || '';

const hexToRgb = (hex) => {
  const v = hex.replace('#', '');
  return `${parseInt(v.slice(0, 2), 16)},${parseInt(v.slice(2, 4), 16)},${parseInt(v.slice(4, 6), 16)}`;
};

// Los números suben hasta su valor al aparecer (no en las pruebas automáticas).
const useCountUp = (value, duration = 1100) => {
  const [shown, setShown] = useState(navigator.webdriver ? value : 0);
  const fromRef = useRef(0);
  useEffect(() => {
    if (value == null || navigator.webdriver) {
      setShown(value);
      return undefined;
    }
    const from = fromRef.current;
    const start = performance.now();
    let frame;
    const step = (now) => {
      const p = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - p, 3);
      setShown(from + (value - from) * eased);
      if (p < 1) frame = requestAnimationFrame(step);
      else fromRef.current = value;
    };
    frame = requestAnimationFrame(step);
    return () => cancelAnimationFrame(frame);
  }, [value, duration]);
  return shown;
};

const Card = ({ title, children, accent = '#25c8f2', testId, className = '' }) => (
  <div
    className={`holo-card ${className}`}
    style={{ '--accent': accent, '--accent-rgb': hexToRgb(accent) }}
    data-testid={testId}
  >
    <div className="holo-label">{title}</div>
    {children}
  </div>
);

// Indicador en arco de 270°, como los de un salpicadero.
const ArcGauge = ({ value, color, label, children }) => {
  const r = 46;
  const length = 2 * Math.PI * r * 0.75;
  const pct = Math.max(0, Math.min(100, value || 0));
  return (
    <div className="arc-gauge" style={{ color }}>
      <svg viewBox="0 0 112 112" aria-hidden="true">
        <circle className="ticks" cx="56" cy="56" r="53" strokeDasharray={`1 ${(2 * Math.PI * 53 * 0.75) / 40 - 1} `} />
        <circle className="track" cx="56" cy="56" r={r} strokeDasharray={`${length} 999`} />
        <circle className="fill" cx="56" cy="56" r={r} stroke={color} strokeDasharray={`${(length * pct) / 100} 999`} />
      </svg>
      <div className="arc-gauge-center">
        <div>
          {children}
          {label && <small>{label}</small>}
        </div>
      </div>
    </div>
  );
};

// Panel con el día de Nacho, en vivo. Cada tarjeta solo aparece si ese
// servicio está configurado en el backend.
const DashboardPanel = ({ refreshKey }) => {
  const [data, setData] = useState(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const result = await apiGet('/api/dashboard');
        if (!cancelled) {
          setData(result);
          setError(false);
        }
      } catch (e) {
        if (!cancelled) {
          setError(true);
        }
      }
    };
    load();
    const timer = setInterval(load, REFRESH_MS);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [refreshKey]);

  const fuel = useCountUp(data && data.car ? data.car.fuel_percent : null);
  const recoveryValue = useCountUp(data && data.health && data.health.recovery ? data.health.recovery.recovery_percent : null);
  const temp = useCountUp(data && data.weather ? data.weather.temperature_c : null, 900);

  if (!data) {
    return (
      <div className="hud-dash j-dash">
        <div className="holo-card span-6">
          <div className="holo-label">Enlace</div>
          <div className="holo-muted">{error ? 'No se puede conectar con JARVIS.' : 'Estableciendo enlace…'}</div>
        </div>
      </div>
    );
  }

  const { weather, car, health, calendar, email, store, tasks, actions, budget, timezone, city } = data;
  const recovery = health && health.recovery;
  const sleep = health && health.sleep;
  const strain = health && health.strain;
  const tireProblems = (car && car.tire_problems) || [];
  const carAlert = car && (car.locked === false || tireProblems.length > 0);
  const zoneColor = recovery ? ZONE_COLORS[recovery.zone] : '#25c8f2';
  const fuelColor = car && car.fuel_percent != null && car.fuel_percent <= 20 ? '#ff4d5e' : '#25c8f2';

  return (
    <div className="hud-dash j-dash" data-testid="dashboard">
      {car && (
        <Card title="Mercedes-AMG C 63" accent={carAlert ? '#ff4d5e' : '#25c8f2'} testId="card-car" className="span-4">
          <div className="car-stage holo-shimmer">
            <img className="holo-img holo-float" src="/holo/coche.webp" alt="" />
          </div>
          <div className="car-stats">
            {car.fuel_percent != null && (
              <ArcGauge value={fuel} color={fuelColor} label="DEPÓSITO">
                <div className="holo-big">{Math.round(fuel)}%</div>
              </ArcGauge>
            )}
            <div>
              {car.range_km != null && (
                <div className="holo-big" style={{ fontSize: 30 }}>
                  {Math.round(car.range_km)}<span className="holo-unit">KM</span>
                </div>
              )}
              {car.range_km != null && <div className="holo-muted">de autonomía</div>}
            </div>
            {car.locked != null && (
              <span className="lock-pill" style={{ color: car.locked ? '#3ddc84' : '#ff4d5e' }}>
                {car.locked ? 'CERRADO' : 'ABIERTO'}
              </span>
            )}
          </div>
          {car.tire_pressure_bar && (
            <div className="tires" data-testid="tires">
              {TIRE_ORDER.map(([key, label, name]) => {
                const v = car.tire_pressure_bar[key];
                const warn = tireProblems.some((p) => p.includes(name));
                return (
                  <span key={key} className={warn ? 'warn' : ''}>
                    {label} {v != null ? v.toFixed(1).replace('.', ',') : '—'}
                  </span>
                );
              })}
            </div>
          )}
          {tireProblems.map((p) => (
            <div key={p} className="car-warning">⚠ {p}</div>
          ))}
        </Card>
      )}

      {weather && (
        <Card title={city ? `Exterior · ${city}` : 'Exterior'} testId="card-weather" className={`weather-card ${car ? 'span-2' : 'span-3'}`}>
          <img className="holo-img weather-terrain" src="/holo/pirineos.webp" alt="" />
          <div className="weather-content">
            <div className="holo-big" style={{ fontSize: 54 }}>{Math.round(temp)}°</div>
          </div>
        </Card>
      )}

      {health && (
        <Card title="Biometría · WHOOP" accent={zoneColor} testId="card-health" className="span-3">
          <div className="health-wrap">
            <img className="holo-img health-body holo-float" src="/holo/cuerpo.webp" alt="" />
            <div className="health-stats">
              {recovery && (
                <ArcGauge value={recoveryValue} color={zoneColor} label="RECUPERACIÓN">
                  <div className="holo-big" style={{ color: zoneColor }}>{Math.round(recoveryValue)}%</div>
                </ArcGauge>
              )}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {sleep && sleep.minutes_asleep != null && (
                  <div className="health-mini">
                    <b>{hoursText(sleep.minutes_asleep)}</b>
                    <span>dormidas{sleep.minutes_needed ? ` de ${hoursText(sleep.minutes_needed)}` : ''}</span>
                  </div>
                )}
                {strain && strain.strain != null && (
                  <div className="health-mini">
                    <b>{strain.strain.toFixed(1).replace('.', ',')}</b>
                    <span>esfuerzo hoy</span>
                  </div>
                )}
              </div>
            </div>
          </div>
          {recovery && (
            <div className="tires">
              {recovery.hrv_ms != null && <span>VFC {recovery.hrv_ms} ms</span>}
              {recovery.resting_heart_rate != null && <span>Reposo {recovery.resting_heart_rate} ppm</span>}
              {sleep && sleep.performance_percent != null && <span>Sueño {Math.round(sleep.performance_percent)}%</span>}
              {strain && strain.kcal != null && <span>{strain.kcal} kcal</span>}
            </div>
          )}
        </Card>
      )}

      {calendar && (
        <Card title="Agenda de hoy" testId="card-calendar" className="span-3">
          {calendar.length === 0 && <div className="holo-muted">Sin citas.</div>}
          <div className="hud-list">
            {calendar.map((event) => (
              <div key={event.id} className="hud-list-row">
                <span className="hud-list-key">{time(event.start, timezone)}</span>
                <span className="hud-list-val">{event.title}</span>
              </div>
            ))}
          </div>
        </Card>
      )}

      {email && (
        <Card title={`Correo · ${email.unread_total} sin leer`} testId="card-email" className="span-3">
          <div className="hud-list">
            {email.emails.map((mail) => (
              <div key={mail.id} className="hud-list-row">
                <span className="hud-list-key">{mail.from}</span>
                <span className="hud-list-val">{mail.subject}</span>
              </div>
            ))}
          </div>
        </Card>
      )}

      {store && (
        <Card title="Tienda" accent="#ffb547" testId="card-store" className="span-3">
          <div className="hud-list">
            {store.today && (
              <div className="hud-list-row">
                <span className="hud-list-key">Hoy</span>
                <span className="hud-list-val">
                  {store.today.orders} pedidos · {money(store.today.revenue, store.today.currency)}
                </span>
              </div>
            )}
            {store.pending && (
              <div className="hud-list-row">
                <span className="hud-list-key">Por enviar</span>
                <span className="hud-list-val">{store.pending.count}</span>
              </div>
            )}
          </div>
        </Card>
      )}

      {tasks && (tasks.tasks.length > 0 || tasks.reminders.length > 0) && (
        <Card title="Pendiente" accent="#3ddc84" testId="card-tasks" className="span-3">
          <div className="hud-list">
            {tasks.reminders.map((r) => (
              <div key={`r${r.id}`} className="hud-list-row">
                <span className="hud-list-key">{time(r.remind_at, timezone)}</span>
                <span className="hud-list-val">{r.text}</span>
              </div>
            ))}
            {tasks.tasks.map((t) => (
              <div key={`t${t.id}`} className="hud-list-row">
                <span className="hud-list-key">{t.due_date || '—'}</span>
                <span className="hud-list-val">{t.text}</span>
              </div>
            ))}
          </div>
        </Card>
      )}

      {actions && actions.length > 0 && (
        <Card title="Hecho en tu nombre" accent="#ff4fd8" testId="card-actions" className="span-6">
          <div className="hud-list">
            {actions.slice(0, 6).map((a, i) => (
              <div key={i} className="hud-list-row">
                <span className="hud-list-key">{a.created_at.substring(11, 16)}</span>
                <span className="hud-list-val">{a.kind}: {describeAction(a.details)}</span>
              </div>
            ))}
          </div>
        </Card>
      )}

      <div className="hud-foot">
        {budget && `Gasto de hoy ${budget.usd.toFixed(2).replace('.', ',')} $ de ${budget.limit_usd} $ · `}
        Actualizado {time(data.updated_at, timezone)}
        {error && ' · sin conexión'}
      </div>
    </div>
  );
};

export default DashboardPanel;
