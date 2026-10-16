import React, { useEffect, useState } from 'react';
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

const Card = ({ title, children, accent = '#00d4ff', testId, grow = false }) => (
  <div style={{ ...styles.card, ...(grow ? { flex: 1 } : {}), borderColor: `${accent}55` }} data-testid={testId}>
    <div style={{ ...styles.cardTitle, color: accent }}>{title}</div>
    {children}
  </div>
);

// Panel permanente para la tablet: lo que JARVIS sabe del día, en vivo.
// Cada tarjeta solo aparece si ese servicio está configurado en el backend.
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

  if (!data) {
    return (
      <div style={styles.panel}>
        <div style={styles.muted}>{error ? 'No se puede conectar con JARVIS.' : 'Cargando…'}</div>
      </div>
    );
  }

  const { weather, car, calendar, email, store, tasks, timezone } = data;

  return (
    <div style={styles.panel} data-testid="dashboard">
      <div style={styles.cardRow}>
        {weather && (
          <Card title="EXTERIOR" testId="card-weather" grow>
            <div style={styles.big}>{Math.round(weather.temperature_c)}°</div>
          </Card>
        )}
        {car && (
          <Card title="MERCEDES" accent={car.locked === false ? '#ff3333' : '#00ff00'} testId="card-car" grow>
            {car.fuel_percent != null && (
              <>
                <div style={styles.big}>{Math.round(car.fuel_percent)}%</div>
                <div style={styles.gauge}>
                  <div style={{ ...styles.gaugeFill, width: `${Math.min(100, car.fuel_percent)}%` }} />
                </div>
                <div style={styles.muted}>{Math.round(car.range_km)} km de autonomía</div>
              </>
            )}
            {car.locked != null && (
              <div style={{ color: car.locked ? '#00ff00' : '#ff3333', marginTop: 6 }}>
                {car.locked ? 'Cerrado' : 'ABIERTO'}
              </div>
            )}
          </Card>
        )}
      </div>

      {calendar && (
        <Card title="AGENDA DE HOY" testId="card-calendar">
          {calendar.length === 0 && <div style={styles.muted}>Sin citas.</div>}
          {calendar.map((event) => (
            <div key={event.id} style={styles.row}>
              <span style={styles.rowTime}>{time(event.start, timezone)}</span>
              <span>{event.title}</span>
            </div>
          ))}
        </Card>
      )}

      {email && (
        <Card title={`CORREO · ${email.unread_total} SIN LEER`} testId="card-email">
          {email.emails.map((mail) => (
            <div key={mail.id} style={styles.row}>
              <span style={styles.rowTime}>{mail.from}</span>
              <span style={styles.ellipsis}>{mail.subject}</span>
            </div>
          ))}
        </Card>
      )}

      {store && (
        <Card title="TIENDA" accent="#ff6600" testId="card-store">
          {store.today && (
            <div style={styles.row}>
              <span style={styles.rowTime}>Hoy</span>
              <span>
                {store.today.orders} pedidos · {money(store.today.revenue, store.today.currency)}
              </span>
            </div>
          )}
          {store.pending && (
            <div style={styles.row}>
              <span style={styles.rowTime}>Por enviar</span>
              <span>{store.pending.count}</span>
            </div>
          )}
        </Card>
      )}

      {tasks && (tasks.tasks.length > 0 || tasks.reminders.length > 0) && (
        <Card title="PENDIENTE" accent="#00ff00" testId="card-tasks">
          {tasks.reminders.map((r) => (
            <div key={`r${r.id}`} style={styles.row}>
              <span style={styles.rowTime}>{time(r.remind_at, timezone)}</span>
              <span>{r.text}</span>
            </div>
          ))}
          {tasks.tasks.map((t) => (
            <div key={`t${t.id}`} style={styles.row}>
              <span style={styles.rowTime}>{t.due_date || '—'}</span>
              <span>{t.text}</span>
            </div>
          ))}
        </Card>
      )}

      <div style={styles.updated}>
        Actualizado {time(data.updated_at, timezone)}
        {error && ' · sin conexión'}
      </div>
    </div>
  );
};

const styles = {
  panel: {
    flex: 1,
    minWidth: '300px',
    display: 'flex',
    flexDirection: 'column',
    gap: '12px',
    overflowY: 'auto',
  },
  cardRow: {
    display: 'flex',
    gap: '12px',
    flexWrap: 'wrap',
  },
  card: {
    minWidth: '140px',
    padding: '12px 15px',
    background: 'rgba(0,212,255,0.04)',
    border: '1px solid',
    borderRadius: '8px',
    color: '#cfefff',
    fontSize: '14px',
  },
  cardTitle: {
    fontSize: '11px',
    letterSpacing: '2px',
    fontWeight: 'bold',
    marginBottom: '8px',
  },
  big: {
    fontSize: '34px',
    fontWeight: 'bold',
    color: '#00d4ff',
    lineHeight: 1.1,
  },
  gauge: {
    height: '6px',
    background: 'rgba(0,212,255,0.15)',
    borderRadius: '3px',
    margin: '6px 0',
    overflow: 'hidden',
  },
  gaugeFill: {
    height: '100%',
    background: '#00d4ff',
  },
  row: {
    display: 'flex',
    gap: '10px',
    padding: '4px 0',
    borderBottom: '1px solid rgba(0,212,255,0.08)',
  },
  rowTime: {
    color: '#00ff00',
    minWidth: '86px',
    maxWidth: '140px',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
  },
  ellipsis: {
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
  },
  muted: {
    opacity: 0.6,
    fontSize: '13px',
  },
  updated: {
    fontSize: '11px',
    opacity: 0.5,
    textAlign: 'right',
  },
};

export default DashboardPanel;
