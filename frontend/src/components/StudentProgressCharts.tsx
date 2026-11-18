import type { ExerciseLoad, WeeklyVolume } from '../types/studentProgress';
import { formatDay, formatNumber, formatRange, niceTicks, xLabelIndexes } from '../utils/trainingEvolution.mjs';

const W = 640;
const H = 220;
const PAD = { top: 16, right: 14, bottom: 30, left: 48 };
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

/** Carga máxima de cada día para un ejercicio; los PRs se marcan con un círculo ámbar. */
export function LoadChart({ exercise }: { exercise: ExerciseLoad }) {
  const { points } = exercise;
  const ticks = niceTicks(Math.max(...points.map((p) => p.weight_kg)));
  const max = ticks[ticks.length - 1];
  const times = points.map((p) => Date.parse(p.date));
  const minT = Math.min(...times);
  const span = Math.max(...times) - minT || 1;
  const xs = times.map((t) => PAD.left + ((t - minT) / span) * INNER_W);
  const ys = points.map((p) => PAD.top + INNER_H - (p.weight_kg / max) * INNER_H);
  const summary = points.map((p) => `${formatDay(p.date)}: ${formatNumber(p.weight_kg)} kg`).join('; ');
  return (
    <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`Carga de ${exercise.name} a lo largo del tiempo. ${summary}`} className="training-evolution__svg">
      <Axis ticks={ticks} max={max} />
      <polyline points={xs.map((x, i) => `${x},${ys[i]}`).join(' ')} fill="none" stroke={BLUE} strokeWidth={2} />
      {points.map((p, i) => (
        <circle key={p.date} cx={xs[i]} cy={ys[i]} r={p.is_pr ? 6 : 4} fill={p.is_pr ? GOLD : BLUE}>
          <title>{`${formatDay(p.date)}: ${formatNumber(p.weight_kg)} kg × ${p.reps}${p.is_pr ? ' (PR)' : ''}`}</title>
        </circle>
      ))}
      {xLabelIndexes(points.length).map((i) => (
        <text key={points[i].date} x={xs[i]} y={H - 8} textAnchor="middle" className="training-evolution__tick">{formatDay(points[i].date)}</text>
      ))}
    </svg>
  );
}

/** Kilaje total por semana; la semana en curso se dibuja con trama porque aún no terminó. */
export function VolumeChart({ weeks }: { weeks: WeeklyVolume[] }) {
  const ticks = niceTicks(Math.max(...weeks.map((w) => w.volume_kg)));
  const max = ticks[ticks.length - 1];
  const slot = INNER_W / weeks.length;
  const barW = Math.max(4, slot * 0.7);
  const summary = weeks.map((w) => `${formatRange(w.week_start, w.week_end)}: ${formatNumber(w.volume_kg)} kg`).join('; ');
  return (
    <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`Kilaje total por semana. ${summary}`} className="training-evolution__svg">
      <Axis ticks={ticks} max={max} />
      {weeks.map((w, i) => {
        const h = (w.volume_kg / max) * INNER_H;
        const x = PAD.left + i * slot + (slot - barW) / 2;
        return (
          <rect key={w.week_start} x={x} y={PAD.top + INNER_H - h} width={barW} height={h} fill={BLUE} opacity={w.is_partial ? 0.5 : 1}>
            <title>{`${formatRange(w.week_start, w.week_end)}: ${formatNumber(w.volume_kg)} kg${w.is_partial ? ' (semana en curso)' : ''}`}</title>
          </rect>
        );
      })}
      {xLabelIndexes(weeks.length).map((i) => (
        <text key={weeks[i].week_start} x={PAD.left + i * slot + slot / 2} y={H - 8} textAnchor="middle" className="training-evolution__tick">{formatDay(weeks[i].week_start)}</text>
      ))}
    </svg>
  );
}
