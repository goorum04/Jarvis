import React, { useEffect, useRef } from 'react';

// El núcleo holográfico de JARVIS, dibujado en tiempo real. Cambia con lo que
// está haciendo: en reposo gira despacio en cian; escuchando se vuelve ámbar y
// lanza ondas; pensando acelera; hablando, el anillo de onda sigue su voz real
// (getLevel devuelve el volumen de 0 a 1).

const PALETTES = {
  ready: { main: [37, 200, 242], hot: [191, 243, 255] },
  listening: { main: [255, 181, 71], hot: [255, 232, 190] },
  processing: { main: [37, 200, 242], hot: [255, 255, 255] },
  speaking: { main: [37, 200, 242], hot: [210, 250, 255] },
  reminder: { main: [255, 79, 216], hot: [255, 210, 245] },
  error: { main: [255, 77, 94], hot: [255, 200, 205] },
  disconnected: { main: [120, 140, 155], hot: [190, 205, 215] },
};

const SPEED = { ready: 1, listening: 1.6, processing: 4.2, speaking: 1.4, reminder: 2, error: 0.4, disconnected: 0.25 };

const LABELS = {
  ready: 'SISTEMAS EN LÍNEA',
  listening: 'ESCUCHANDO',
  processing: 'PROCESANDO',
  speaking: 'TRANSMITIENDO',
  reminder: 'RECORDATORIO',
  error: 'ERROR DE SISTEMA',
  disconnected: 'SIN ENLACE',
};

const rgba = (c, a) => `rgba(${c[0]},${c[1]},${c[2]},${a})`;

const makeParticles = (n) => Array.from({ length: n }, () => ({
  r: 0.35 + Math.random() * 0.62,
  a: Math.random() * Math.PI * 2,
  v: (0.04 + Math.random() * 0.18) * (Math.random() < 0.5 ? -1 : 1),
  size: 0.6 + Math.random() * 1.6,
  tw: Math.random() * Math.PI * 2,
}));

const HoloCore = ({ status = 'ready', getLevel, size = 360, showLabel = true }) => {
  const canvasRef = useRef(null);
  const stateRef = useRef({ status, getLevel });
  stateRef.current = { status, getLevel };

  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    const particles = makeParticles(70);
    const ripples = [];
    let frame = 0;
    let last = performance.now();
    let phase = 0;          // rotación acumulada (sigue la velocidad del estado)
    let smoothLevel = 0;
    let lastRipple = 0;
    let colorMix = { main: [...PALETTES.ready.main], hot: [...PALETTES.ready.hot] };

    const resize = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      // Tamaño de maqueta (clientWidth), no el visual: durante la animación de
      // entrada el lienzo está escalado y getBoundingClientRect lo vería pequeño.
      canvas.width = Math.max(1, Math.round(canvas.clientWidth * dpr));
      canvas.height = Math.max(1, Math.round(canvas.clientHeight * dpr));
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    resize();
    const observer = new ResizeObserver(resize);
    observer.observe(canvas);

    const draw = (now) => {
      frame = requestAnimationFrame(draw);
      if (document.hidden) {
        return;
      }
      const dt = Math.min(0.05, (now - last) / 1000);
      last = now;
      const t = now / 1000;
      const { status: st, getLevel: level } = stateRef.current;
      const target = PALETTES[st] || PALETTES.ready;
      // Los colores cambian suavemente de un estado a otro.
      colorMix = {
        main: colorMix.main.map((v, i) => v + (target.main[i] - v) * Math.min(1, dt * 4)),
        hot: colorMix.hot.map((v, i) => v + (target.hot[i] - v) * Math.min(1, dt * 4)),
      };
      const main = colorMix.main.map(Math.round);
      const hot = colorMix.hot.map(Math.round);
      phase += dt * (SPEED[st] || 1);

      const raw = st === 'speaking' && level ? level() : st === 'listening' ? 0.35 + 0.25 * Math.sin(t * 5) : 0;
      smoothLevel += (raw - smoothLevel) * Math.min(1, dt * 12);

      const w = canvas.clientWidth;
      const h = canvas.clientHeight;
      const cx = w / 2;
      const cy = h / 2;
      const R = Math.min(w, h) / 2 * 0.94;

      ctx.clearRect(0, 0, w, h);
      ctx.globalCompositeOperation = 'lighter';
      ctx.lineCap = 'round';

      // Halo de fondo
      const halo = ctx.createRadialGradient(cx, cy, R * 0.05, cx, cy, R);
      halo.addColorStop(0, rgba(main, 0.20 + smoothLevel * 0.2));
      halo.addColorStop(0.45, rgba(main, 0.06));
      halo.addColorStop(1, rgba(main, 0));
      ctx.fillStyle = halo;
      ctx.fillRect(0, 0, w, h);

      // Escala exterior: marcas cada 2°, más largas cada 10°
      ctx.save();
      ctx.translate(cx, cy);
      ctx.rotate(phase * 0.05);
      for (let i = 0; i < 180; i += 1) {
        const a = (i / 180) * Math.PI * 2;
        const long = i % 5 === 0;
        const r1 = R * 0.965;
        const r2 = R * (long ? 0.915 : 0.94);
        ctx.strokeStyle = rgba(main, long ? 0.55 : 0.22);
        ctx.lineWidth = long ? 1.4 : 1;
        ctx.beginPath();
        ctx.moveTo(Math.cos(a) * r1, Math.sin(a) * r1);
        ctx.lineTo(Math.cos(a) * r2, Math.sin(a) * r2);
        ctx.stroke();
      }
      ctx.restore();

      const arc = (radius, start, length, width, alpha, color = main) => {
        ctx.strokeStyle = rgba(color, alpha);
        ctx.lineWidth = width;
        ctx.beginPath();
        ctx.arc(cx, cy, radius, start, start + length);
        ctx.stroke();
      };

      // Anillo segmentado (gira a derechas)
      const segs = 14;
      for (let i = 0; i < segs; i += 1) {
        const start = phase * 0.22 + (i / segs) * Math.PI * 2;
        arc(R * 0.86, start, (Math.PI * 2 / segs) * 0.72, R * 0.035, i % 4 === 0 ? 0.85 : 0.45);
      }

      // Anillo discontinuo (a izquierdas)
      ctx.setLineDash([2, 7]);
      arc(R * 0.775, -phase * 0.35, Math.PI * 2, 1.4, 0.55);
      ctx.setLineDash([]);

      // Tres arcos largos que giran rápido
      for (let i = 0; i < 3; i += 1) {
        const start = phase * 0.9 + i * (Math.PI * 2 / 3);
        arc(R * 0.70, start, Math.PI * 0.42, 2.2, 0.8, hot);
        arc(R * 0.70, start, Math.PI * 0.42, 7, 0.10);
      }

      // Barrido de radar
      ctx.save();
      ctx.translate(cx, cy);
      ctx.rotate(phase * 1.1);
      const sweep = ctx.createLinearGradient(0, 0, R * 0.66, 0);
      sweep.addColorStop(0, rgba(main, 0));
      sweep.addColorStop(1, rgba(main, 0.22));
      ctx.fillStyle = sweep;
      ctx.beginPath();
      ctx.moveTo(0, 0);
      ctx.arc(0, 0, R * 0.66, -0.35, 0);
      ctx.closePath();
      ctx.fill();
      ctx.restore();

      // Anillo de onda: sigue la voz de JARVIS
      const waveR = R * 0.52;
      const amp = R * (0.012 + smoothLevel * 0.11);
      for (let layer = 0; layer < 2; layer += 1) {
        ctx.strokeStyle = rgba(layer ? hot : main, layer ? 0.9 : 0.35);
        ctx.lineWidth = layer ? 1.6 : 5;
        ctx.beginPath();
        for (let i = 0; i <= 200; i += 1) {
          const a = (i / 200) * Math.PI * 2;
          const n = Math.sin(a * 6 + t * 3.1) * 0.55 + Math.sin(a * 11 - t * 4.7) * 0.3 + Math.sin(a * 17 + t * 2.3) * 0.15;
          const r = waveR + n * amp;
          const x = cx + Math.cos(a) * r;
          const y = cy + Math.sin(a) * r;
          if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
        }
        ctx.closePath();
        ctx.stroke();
      }

      // Ondas al escuchar
      if (st === 'listening' && t - lastRipple > 0.7) {
        ripples.push({ born: t });
        lastRipple = t;
      }
      for (let i = ripples.length - 1; i >= 0; i -= 1) {
        const age = t - ripples[i].born;
        if (age > 1.8) {
          ripples.splice(i, 1);
        } else {
          arc(R * (0.3 + age * 0.38), 0, Math.PI * 2, 1.5, 0.5 * (1 - age / 1.8));
        }
      }

      // Partículas en órbita
      for (const p of particles) {
        p.a += p.v * dt * (SPEED[st] || 1);
        const r = R * p.r;
        const alpha = 0.25 + 0.55 * (0.5 + 0.5 * Math.sin(t * 2 + p.tw));
        ctx.fillStyle = rgba(hot, alpha);
        ctx.beginPath();
        ctx.arc(cx + Math.cos(p.a) * r, cy + Math.sin(p.a) * r, p.size, 0, Math.PI * 2);
        ctx.fill();
      }

      // Núcleo
      const pulse = 1 + 0.06 * Math.sin(t * 2.2) + smoothLevel * 0.22;
      const coreR = R * 0.24 * pulse;
      const core = ctx.createRadialGradient(cx, cy, 0, cx, cy, coreR * 1.9);
      core.addColorStop(0, 'rgba(255,255,255,0.95)');
      core.addColorStop(0.22, rgba(hot, 0.9));
      core.addColorStop(0.5, rgba(main, 0.45));
      core.addColorStop(1, rgba(main, 0));
      ctx.fillStyle = core;
      ctx.beginPath();
      ctx.arc(cx, cy, coreR * 1.9, 0, Math.PI * 2);
      ctx.fill();
      arc(coreR * 1.08, 0, Math.PI * 2, 1.2, 0.9, hot);
      ctx.setLineDash([R * 0.02, R * 0.03]);
      arc(coreR * 1.35, phase * -0.6, Math.PI * 2, 2.5, 0.5);
      ctx.setLineDash([]);

      // Rótulo sobre el anillo
      if (showLabel && R > 110) {
        const label = LABELS[st] || LABELS.ready;
        ctx.globalCompositeOperation = 'source-over';
        ctx.fillStyle = rgba(hot, 0.85);
        ctx.font = `600 ${Math.max(9, R * 0.045)}px "Share Tech Mono", ui-monospace, monospace`;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        const radius = R * 0.995;
        const spacing = (R * 0.05) / radius;
        const startAngle = -Math.PI / 2 - ((label.length - 1) * spacing) / 2;
        for (let i = 0; i < label.length; i += 1) {
          const a = startAngle + i * spacing;
          ctx.save();
          ctx.translate(cx + Math.cos(a) * radius, cy + Math.sin(a) * radius);
          ctx.rotate(a + Math.PI / 2);
          ctx.fillText(label[i], 0, 0);
          ctx.restore();
        }
      }
    };
    frame = requestAnimationFrame(draw);

    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
    };
  }, [showLabel]);

  return (
    <canvas
      ref={canvasRef}
      className="holo-core"
      style={{ width: size, height: size, maxWidth: '100%', aspectRatio: '1 / 1' }}
      aria-label={`JARVIS: ${LABELS[status] || ''}`}
      data-testid="holo-core"
      data-status={status}
    />
  );
};

export default HoloCore;
