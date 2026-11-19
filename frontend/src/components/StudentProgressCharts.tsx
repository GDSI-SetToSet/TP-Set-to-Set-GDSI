import type { ConsistencyWeek, ExerciseEvolution } from '../types/studentProgress';
import { currentWeekLabel, isWeekDone, kg } from '../utils/studentProgress.mjs';
import { formatDay, formatNumber, formatRange, niceTicks, xLabelIndexes } from '../utils/trainingEvolution.mjs';

const W = 640;
const H = 220;
const PAD = { top: 20, right: 14, bottom: 30, left: 48 };
const BLUE = '#1d4ed8';
const GOLD = '#b45309';
const INNER_W = W - PAD.left - PAD.right;
const INNER_H = H - PAD.top - PAD.bottom;

function Axis({ ticks, max }: { ticks: number[]; max: number }) {
  return (
    <>
      {ticks.map((tick) => {
        const y = PAD.top + INNER_H - (tick / max) * INNER_H;
        return (
          <g key={tick}>
            <line x1={PAD.left} x2={W - PAD.right} y1={y} y2={y} className="training-evolution__grid" />
            <text x={PAD.left - 6} y={y + 4} textAnchor="end" className="training-evolution__tick">{formatNumber(tick)}</text>
          </g>
        );
      })}
    </>
  );
}

/** Mejor serie de cada sesión (peso, o repeticiones si no lleva carga). Récords en ámbar; objetivo del entrenador punteado. */
export function LoadChart({ exercise }: { exercise: ExerciseEvolution }) {
  const { points } = exercise;
  const byWeight = exercise.metric === 'max_weight';
  const value = (p: ExerciseEvolution['points'][number]) => (byWeight ? p.weight ?? 0 : p.reps);
  const ticks = niceTicks(Math.max(...points.map(value), ...points.map((p) => (byWeight ? p.target_weight ?? 0 : 0))), { integer: !byWeight });
  const max = ticks[ticks.length - 1];
  const times = points.map((p) => Date.parse(p.date));
  const minT = Math.min(...times);
  const span = Math.max(...times) - minT || 1;
  const xs = times.map((t) => PAD.left + ((t - minT) / span) * INNER_W);
  const y = (v: number) => PAD.top + INNER_H - (v / max) * INNER_H;
  const tip = (p: ExerciseEvolution['points'][number]) =>
    `${formatDay(p.date)}: ${p.weight ? `${kg(p.weight)} × ${p.reps}` : `${p.reps} repeticiones`}${p.is_pr ? ' · ¡Récord!' : ''}`;
  const target = byWeight ? points.map((p, i) => (p.target_weight ? { x: xs[i], y: y(p.target_weight) } : null)).filter((t) => t !== null) : [];
  return (
    <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`Evolución de ${exercise.name}. ${points.map(tip).join('; ')}`} className="training-evolution__svg">
      <Axis ticks={ticks} max={max} />
      <text x={PAD.left} y={10} className="training-evolution__unit">{byWeight ? 'kg' : 'repeticiones'}</text>
      <polyline points={xs.map((x, i) => `${x},${y(value(points[i]))}`).join(' ')} fill="none" stroke={BLUE} strokeWidth={2} />
      {target.length > 1 && <polyline points={target.map((t) => `${t.x},${t.y}`).join(' ')} fill="none" stroke={GOLD} strokeWidth={2} strokeDasharray="5 4"><title>Objetivo de tu entrenador</title></polyline>}
      {points.map((p, i) => (
        <circle key={p.date} cx={xs[i]} cy={y(value(p))} r={p.is_pr ? 6 : 4} fill={p.is_pr ? GOLD : BLUE}><title>{tip(p)}</title></circle>
      ))}
      {xLabelIndexes(points.length).map((i) => (
        <text key={points[i].date} x={xs[i]} y={H - 8} textAnchor="middle" className="training-evolution__tick">{formatDay(points[i].date)}</text>
      ))}
    </svg>
  );
}

/** Sesiones por semana: acordadas (fondo claro) y realizadas (sólido). Sin color de alerta; la semana en curso va punteada. */
export function ConsistencyChart({ weeks }: { weeks: ConsistencyWeek[] }) {
  const ticks = niceTicks(Math.max(...weeks.map((w) => Math.max(w.scheduled, w.completed))), { integer: true });
  const max = ticks[ticks.length - 1];
  const slot = INNER_W / weeks.length;
  const barW = Math.min(36, slot * 0.7);
  const y = (v: number) => PAD.top + INNER_H - (v / max) * INNER_H;
  const tip = (w: ConsistencyWeek) => `${formatRange(w.period_start, w.period_end)}: ${w.is_partial ? currentWeekLabel(w) : `${w.completed} de ${w.scheduled} sesiones`}`;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`Sesiones por semana. ${weeks.map(tip).join('; ')}`} className="training-evolution__svg">
      <Axis ticks={ticks} max={max} />
      {weeks.map((w, i) => {
        const x = PAD.left + slot * i + slot / 2;
        return (
          <g key={w.period_start}>
            <rect x={x - barW / 2} y={y(w.scheduled)} width={barW} height={INNER_H - (y(w.scheduled) - PAD.top)} fill="#e2e8f0"
              stroke={w.is_partial ? '#64748b' : 'none'} strokeWidth="1.5" strokeDasharray={w.is_partial ? '4 3' : undefined}><title>{tip(w)}</title></rect>
            {w.completed > 0 && <rect x={x - barW / 2} y={y(Math.min(w.completed, max))} width={barW} height={INNER_H - (y(Math.min(w.completed, max)) - PAD.top)} fill={BLUE}><title>{tip(w)}</title></rect>}
            {isWeekDone(w) && <text x={x} y={y(Math.max(w.scheduled, w.completed)) - 4} textAnchor="middle" className="training-evolution__tick">✓</text>}
            {w.is_partial && <text x={x} y={PAD.top - 6} textAnchor="end" className="training-evolution__partial">{currentWeekLabel(w)}</text>}
          </g>
        );
      })}
      {xLabelIndexes(weeks.length).map((i) => (
        <text key={weeks[i].period_start} x={PAD.left + slot * i + slot / 2} y={H - 8} textAnchor="middle" className="training-evolution__tick">{formatDay(weeks[i].period_start)}</text>
      ))}
    </svg>
  );
}
