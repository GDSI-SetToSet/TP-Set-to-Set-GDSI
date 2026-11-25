import type { ConsistencyWeek, ExerciseEvolution } from '../types/studentProgress';
import { useEffect, useRef, useState } from 'react';
import { currentWeekLabel, isWeekDone, kg } from '../utils/studentProgress.mjs';
import { formatDay, formatNumber, formatRange, niceTicks, xLabelIndexes } from '../utils/trainingEvolution.mjs';

const MAX_W = 640;
const H = 220;
const PAD = { top: 36, right: 14, bottom: 30, left: 48 };
const BLUE = 'var(--student-chart-series, #1d4ed8)';
const GOLD = '#b45309';
const INNER_H = H - PAD.top - PAD.bottom;

function useChartWidth() {
  const containerRef = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(MAX_W);
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const updateWidth = () => setWidth(Math.max(220, Math.min(MAX_W, Math.round(container.clientWidth))));
    updateWidth();
    const observer = new ResizeObserver(updateWidth);
    observer.observe(container);
    return () => observer.disconnect();
  }, []);
  return { containerRef, width };
}

function Axis({ ticks, max, width }: { ticks: number[]; max: number; width: number }) {
  return (
    <>
      {ticks.map((tick) => {
        const y = PAD.top + INNER_H - (tick / max) * INNER_H;
        return (
          <g key={tick}>
            <line x1={PAD.left} x2={width - PAD.right} y1={y} y2={y} className="training-evolution__grid" />
            <text x={PAD.left - 6} y={y + 4} textAnchor="end" className="training-evolution__tick">{formatNumber(tick)}</text>
          </g>
        );
      })}
    </>
  );
}

/** Mejor serie de cada sesión (peso, o repeticiones si no lleva carga). Récords en ámbar; objetivo del entrenador punteado. */
export function LoadChart({ exercise }: { exercise: ExerciseEvolution }) {
  const { containerRef, width } = useChartWidth();
  const innerW = width - PAD.left - PAD.right;
  const { points } = exercise;
  const byWeight = exercise.metric === 'max_weight';
  const value = (p: ExerciseEvolution['points'][number]) => (byWeight ? p.weight ?? 0 : p.reps);
  const ticks = niceTicks(Math.max(...points.map(value), ...points.map((p) => (byWeight ? p.target_weight ?? 0 : 0))), { integer: !byWeight });
  const max = ticks[ticks.length - 1];
  const times = points.map((p) => Date.parse(p.date));
  const minT = Math.min(...times);
  const span = Math.max(...times) - minT || 1;
  const xs = times.map((t) => PAD.left + ((t - minT) / span) * innerW);
  const y = (v: number) => PAD.top + INNER_H - (v / max) * INNER_H;
  const tip = (p: ExerciseEvolution['points'][number]) =>
    `${formatDay(p.date)}: ${p.weight ? `${kg(p.weight)} × ${p.reps}` : `${p.reps} repeticiones`}${p.is_pr ? ' · ¡Récord!' : ''}`;
  const target = byWeight ? points.map((p, i) => (p.target_weight ? { x: xs[i], y: y(p.target_weight) } : null)).filter((t) => t !== null) : [];
  return (
    <div ref={containerRef} className="training-evolution__responsive-chart">
      <svg viewBox={`0 0 ${width} ${H}`} role="img" aria-label={`Evolución de ${exercise.name}. ${points.map(tip).join('; ')}`} className="training-evolution__svg">
        <Axis ticks={ticks} max={max} width={width} />
        <text x={PAD.left} y={10} className="training-evolution__unit">{byWeight ? 'kg' : 'repeticiones'}</text>
        <polyline points={xs.map((x, i) => `${x},${y(value(points[i]))}`).join(' ')} fill="none" stroke={BLUE} strokeWidth={2} />
        {target.length > 1 && <polyline points={target.map((t) => `${t.x},${t.y}`).join(' ')} fill="none" stroke={GOLD} strokeWidth={2} strokeDasharray="5 4"><title>Objetivo de tu entrenador</title></polyline>}
        {points.map((p, i) => (
          <g key={p.date}>
            {p.is_pr && <circle cx={xs[i]} cy={y(value(p))} r="7" fill="none" stroke={GOLD} strokeWidth="2" />}
            <circle cx={xs[i]} cy={y(value(p))} r="4" fill={BLUE}><title>{tip(p)}</title></circle>
          </g>
        ))}
        {xLabelIndexes(points.length).map((i) => (
          <text key={points[i].date} x={xs[i]} y={H - 8} textAnchor="middle" className="training-evolution__tick">{formatDay(points[i].date)}</text>
        ))}
      </svg>
    </div>
  );
}

/** Sesiones por semana: acordadas (fondo claro) y realizadas (sólido). Sin color de alerta; la semana en curso va punteada. */
export function ConsistencyChart({ weeks }: { weeks: ConsistencyWeek[] }) {
  const { containerRef, width } = useChartWidth();
  const innerW = width - PAD.left - PAD.right;
  const ticks = niceTicks(Math.max(...weeks.map((w) => Math.max(w.scheduled, w.completed))), { integer: true });
  const max = ticks[ticks.length - 1];
  const slot = innerW / weeks.length;
  const barW = Math.min(36, slot * 0.7);
  const y = (v: number) => PAD.top + INNER_H - (v / max) * INNER_H;
  const tip = (w: ConsistencyWeek) => `${formatRange(w.period_start, w.period_end)}: ${w.is_partial ? currentWeekLabel(w) : `${w.completed} de ${w.scheduled} sesiones`}`;
  return (
    <div ref={containerRef} className="training-evolution__responsive-chart">
      <svg viewBox={`0 0 ${width} ${H}`} role="img" aria-label={`Sesiones por semana. ${weeks.map(tip).join('; ')}`} className="training-evolution__svg">
        <Axis ticks={ticks} max={max} width={width} />
        {weeks.map((w, i) => {
          const x = PAD.left + slot * i + slot / 2;
          return (
            <g key={w.period_start}>
              <rect x={x - barW / 2} y={y(w.scheduled)} width={barW} height={INNER_H - (y(w.scheduled) - PAD.top)} fill="#e2e8f0"
                stroke={w.is_partial ? '#64748b' : 'none'} strokeWidth="1.5" strokeDasharray={w.is_partial ? '4 3' : undefined}><title>{tip(w)}</title></rect>
              {w.completed > 0 && <rect x={x - barW / 2} y={y(Math.min(w.completed, max))} width={barW} height={INNER_H - (y(Math.min(w.completed, max)) - PAD.top)} fill={BLUE}><title>{tip(w)}</title></rect>}
              {isWeekDone(w) && <text x={x} y={y(Math.max(w.scheduled, w.completed)) - 4} textAnchor="middle" className="training-evolution__tick">✓</text>}
              {w.is_partial && <text x={width - 2} y={12} textAnchor="end" className="training-evolution__partial">{currentWeekLabel(w)}</text>}
            </g>
          );
        })}
        {xLabelIndexes(weeks.length).map((i) => (
          <text key={weeks[i].period_start} x={PAD.left + slot * i + slot / 2} y={H - 8} textAnchor="middle" className="training-evolution__tick">{formatDay(weeks[i].period_start)}</text>
        ))}
      </svg>
    </div>
  );
}

export function LoadChartLegend({ exercise }: { exercise: ExerciseEvolution }) {
  const byWeight = exercise.metric === 'max_weight';
  const hasTarget = byWeight && exercise.points.some((point) => point.target_weight !== null);
  const hasRecord = exercise.points.some((point) => point.is_pr);
  return (
    <ul className="training-evolution__legend training-evolution__legend--student-chart" aria-label="Referencias del gráfico">
      <li><svg width="28" height="14" viewBox="0 0 28 14" aria-hidden="true" className="training-evolution__swatch"><line x1="2" y1="7" x2="26" y2="7" stroke={BLUE} strokeWidth="2" /></svg>{byWeight ? 'Mejor peso de cada sesión' : 'Mejores repeticiones de cada sesión'}</li>
      <li><svg width="28" height="14" viewBox="0 0 28 14" aria-hidden="true" className="training-evolution__swatch"><circle cx="14" cy="7" r="4" fill={BLUE} /></svg>Sesión registrada</li>
      {hasTarget && <li><svg width="28" height="14" viewBox="0 0 28 14" aria-hidden="true" className="training-evolution__swatch"><line x1="2" y1="7" x2="26" y2="7" stroke={GOLD} strokeWidth="2" strokeDasharray="5 4" /></svg>Objetivo programado por tu entrenador</li>}
      {hasRecord && <li><svg width="28" height="14" viewBox="0 0 28 14" aria-hidden="true" className="training-evolution__swatch"><circle cx="14" cy="7" r="6" fill="none" stroke={GOLD} strokeWidth="2" /><circle cx="14" cy="7" r="3" fill={BLUE} /></svg>Récord personal</li>}
    </ul>
  );
}
