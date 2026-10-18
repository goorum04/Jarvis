import React, { useEffect, useState } from 'react';
import HoloCore from './HoloCore';
import { apiGet } from './config';

// Arranque de JARVIS al abrir el panel: el núcleo se monta, comprueba sus
// sistemas con datos reales y saluda. Una vez por sesión; un toque lo salta.

const greetingFor = (hour) => (hour >= 6 && hour < 13 ? 'Buenos días' : hour >= 13 && hour < 21 ? 'Buenas tardes' : 'Buenas noches');

const systemLines = (data) => {
  const lines = [['ENLACE SEGURO CON EL MAC', 'OK'], ['NÚCLEO DE IA', 'OK']];
  if (!data) {
    return lines;
  }
  const { calendar, email, car, health, store, weather } = data;
  if (calendar) lines.push(['AGENDA', `${calendar.length} ${calendar.length === 1 ? 'CITA' : 'CITAS'} HOY`]);
  if (email) lines.push(['CORREO', `${email.unread_total} SIN LEER`]);
  if (car) {
    const parts = [];
    if (car.fuel_percent != null) parts.push(`${Math.round(car.fuel_percent)} %`);
    if (car.locked != null) parts.push(car.locked ? 'CERRADO' : 'ABIERTO');
    lines.push(['MERCEDES-AMG C 63', parts.join(' · ') || 'EN LÍNEA', car.locked === false || (car.tire_problems || []).length]);
  }
  if (health && health.recovery) lines.push(['BIOMETRÍA · WHOOP', `RECUPERACIÓN ${Math.round(health.recovery.recovery_percent)} %`]);
  if (store && store.today) lines.push(['TIENDA', `${store.today.orders} PEDIDOS HOY`]);
  if (weather) lines.push(['EXTERIOR', `${Math.round(weather.temperature_c)}°`]);
  return lines;
};

const BootSequence = ({ onDone }) => {
  const [data, setData] = useState(null);
  const [shown, setShown] = useState(0);
  const [leaving, setLeaving] = useState(false);

  useEffect(() => {
    let cancelled = false;
    apiGet('/api/dashboard').then((d) => !cancelled && setData(d)).catch(() => {});
    return () => { cancelled = true; };
  }, []);

  const lines = systemLines(data);
  const total = lines.length + 1; // + el saludo

  useEffect(() => {
    if (shown < total) {
      const timer = setTimeout(() => setShown((s) => s + 1), shown === 0 ? 650 : 260);
      return () => clearTimeout(timer);
    }
    const timer = setTimeout(() => setLeaving(true), 1300);
    return () => clearTimeout(timer);
  }, [shown, total]);

  useEffect(() => {
    if (leaving) {
      const timer = setTimeout(onDone, 650);
      return () => clearTimeout(timer);
    }
    return undefined;
  }, [leaving, onDone]);

  const owner = (data && data.owner) || '';
  const hour = new Date().getHours();

  return (
    <div className={`boot ${leaving ? 'boot-out' : ''}`} onClick={() => setLeaving(true)} role="presentation" data-testid="boot">
      <div className="boot-core">
        <HoloCore status={shown >= total ? 'speaking' : 'processing'} getLevel={() => 0.35} size={260} showLabel={false} />
      </div>
      <div className="boot-title">J.A.R.V.I.S</div>
      <div className="boot-sub">INICIANDO SISTEMAS</div>
      <div className="boot-lines">
        {lines.slice(0, shown).map(([name, value, warn]) => (
          <div className="boot-line" key={name}>
            <span>{name}</span>
            <span className="boot-dots" />
            <span className={warn ? 'boot-warn' : 'boot-ok'}>{value}</span>
          </div>
        ))}
      </div>
      {shown >= total && (
        <div className="boot-greeting">{greetingFor(hour)}{owner ? `, ${owner}` : ''}.</div>
      )}
      <div className="boot-skip">Toca para entrar</div>
    </div>
  );
};

export default BootSequence;
