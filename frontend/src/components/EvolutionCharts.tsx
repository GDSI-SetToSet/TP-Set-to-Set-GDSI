import type {
  AdherenceWeek,
  EvolutionGrouping,
  ExercisePoint,
  MuscleGroupSets,
  RpePoint,
} from '../types/trainerStudent';
import { formatDay, formatNumber, formatRange, niceTicks, reportedRuns, xLabelIndexes } from '../utils/trainingEvolution.mjs';

const W = 640;
const PAD = { top: 16, right: 14, bottom: 30, left: 44 };
const BLUE = '#1d4ed8';
const GOLD = '#b45309';
const RED = '#b42318';
const last = <T,>(list: T[]): T | undefined => list[list.length - 1];

function rangeOf(point: { period_start: string; period_end: string }, groupBy: EvolutionGrouping) {
  return formatRange(point.period_start, groupBy === 'session' ? point.period_start : point.period_end);
}

function Frame({ height, ariaLabel, children }: { height: number; ariaLabel: string; children: React.ReactNode }) {
  return <svg viewBox={`0 0 ${W} ${height}`} role="img" aria-label={ariaLabel} className="training-evolution__svg">{children}</svg>;
}

function YAxis({ ticks, max, height, innerH }: { ticks: number[]; max: number; height: number; innerH: number }) {
  return (
    <>
      {ticks.map((tick) => {
        const y = PAD.top + innerH - (tick / max) * innerH;
        return (
          <g key={tick}>
            <line x1={PAD.left} x2={W - PAD.right} y1={y} y2={y} className="training-evolution__grid" />
            <text x={PAD.left - 6} y={y + 4} textAnchor="end" className="training-evolution__tick">{formatNumber(tick)}</text>
          </g>
        );
      })}
      <text x={PAD.left} y={height - 2} className="training-evolution__tick" aria-hidden="true" />
    </>
  );
}

function XLabels({ days, xs, height }: { days: string[]; xs: number[]; height: number }) {
  const picked = xLabelIndexes(days.length);
  return (
    <>
      {picked.map((index) => (
        <text key={days[index] + index} x={xs[index]} y={height - 8}
          textAnchor={index === 0 ? 'start' : index === days.length - 1 ? 'end' : 'middle'} className="training-evolution__tick">
          {formatDay(days[index])}
        </text>
      ))}
    </>
  );
}

/** Evolución de un ejercicio: mejor serie por sesión o semana, récords destacados y peso objetivo punteado. */
export function ExerciseChart({ points, groupBy, kind, ariaLabel }: {
  points: ExercisePoint[]; groupBy: EvolutionGrouping; kind: 'max_weight' | 'max_reps'; ariaLabel: string;
}) {
  const height = 250;
  const innerW = W - PAD.left - PAD.right;
  const innerH = height - PAD.top - PAD.bottom;
  const value = (p: ExercisePoint) => (kind === 'max_weight' ? p.weight ?? 0 : p.reps ?? 0);
  const peak = Math.max(0, ...points.map(value), ...(kind === 'max_weight' ? points.map((p) => p.target_weight ?? 0) : []));
  const ticks = niceTicks(peak, { integer: kind === 'max_reps' });
  const max = last(ticks) ?? 1;
  const times = points.map((p) => Date.parse(p.period_start));
  const minT = Math.min(...times);
  const span = Math.max(...times) - minT || 1;
  const xs = times.map((t) => PAD.left + ((t - minT) / span) * innerW);
  const y = (v: number) => PAD.top + innerH - (v / max) * innerH;
  const partial = last(points)?.is_partial === true && points.length > 1;
  const solid = partial ? points.slice(0, -1) : points;
  const targets = points.map((p, i) => ({ p, i })).filter(({ p }) => kind === 'max_weight' && p.target_weight !== null);
  const unit = kind === 'max_weight' ? 'kg' : 'reps';

  return (
    <Frame height={height} ariaLabel={ariaLabel}>
      <YAxis ticks={ticks} max={max} height={height} innerH={innerH} />
      <XLabels days={points.map((p) => p.period_start)} xs={xs} height={height} />
      {targets.length > 1 && (
        <polyline fill="none" stroke="#94a3b8" strokeWidth="1.5" strokeDasharray="2 4"
          points={targets.map(({ p, i }) => `${xs[i]},${y(p.target_weight as number)}`).join(' ')}>
          <title>Peso objetivo programado</title>
        </polyline>
      )}
      {solid.length > 1 && <polyline fill="none" stroke={BLUE} strokeWidth="2" points={solid.map((p, i) => `${xs[i]},${y(value(p))}`).join(' ')} />}
      {partial && (
        <line stroke={BLUE} strokeWidth="2" strokeDasharray="5 4" x1={xs[points.length - 2]} y1={y(value(points[points.length - 2]))}
          x2={xs[points.length - 1]} y2={y(value(points[points.length - 1]))} />
      )}
      {points.map((p, i) => {
        const set = kind === 'max_weight' ? `${formatNumber(p.weight ?? 0)} kg × ${p.reps}` : `${p.reps} reps`;
        const tip = `${rangeOf(p, groupBy)} · ${set}${p.rpe !== null ? ` · RPE ${p.rpe}` : ''}${p.is_pr ? ' · récord personal' : ''}${p.is_partial ? ' (en curso)' : ''}`;
        return (
          <g key={p.key}>
            {p.is_pr && <circle cx={xs[i]} cy={y(value(p))} r="8" fill="none" stroke={GOLD} strokeWidth="2" />}
            <circle cx={xs[i]} cy={y(value(p))} r="4" stroke={BLUE} strokeWidth="2" fill={p.is_partial ? '#fff' : BLUE}><title>{tip}</title></circle>
          </g>
        );
      })}
      {last(points)?.is_partial && <text x={xs[points.length - 1]} y={PAD.top - 4} textAnchor="end" className="training-evolution__partial">en curso</text>}
      <text x={PAD.left} y={10} className="training-evolution__unit">{unit}</text>
    </Frame>
  );
}

/** Barras por semana: sesiones programadas (fondo) y finalizadas (sólido). */
export function AdherenceChart({ weeks, ariaLabel }: { weeks: AdherenceWeek[]; ariaLabel: string }) {
  const height = 200;
  const innerW = W - PAD.left - PAD.right;
  const innerH = height - PAD.top - PAD.bottom;
  const ticks = niceTicks(Math.max(0, ...weeks.map((w) => Math.max(w.scheduled, w.completed))), { integer: true });
  const max = last(ticks) ?? 1;
  const slot = innerW / weeks.length;
  const barW = Math.min(36, slot * 0.7);
  const xs = weeks.map((_, i) => PAD.left + slot * i + slot / 2);
  const y = (v: number) => PAD.top + innerH - (v / max) * innerH;
  return (
    <Frame height={height} ariaLabel={ariaLabel}>
      <YAxis ticks={ticks} max={max} height={height} innerH={innerH} />
      <XLabels days={weeks.map((w) => w.period_start)} xs={xs} height={height} />
      {weeks.map((w, i) => {
        const missed = !w.is_partial && w.completed === 0;
        const tip = `${formatRange(w.period_start, w.period_end)} · ${w.completed}/${w.scheduled} sesiones${w.is_partial ? ' (en curso)' : ''}${missed ? ' · sin entrenar' : ''}`;
        return (
          <g key={w.period_start}>
            <rect x={xs[i] - barW / 2} y={y(w.scheduled)} width={barW} height={innerH - (y(w.scheduled) - PAD.top)} fill="#e2e8f0"
              stroke={w.is_partial ? '#64748b' : missed ? RED : 'none'} strokeWidth="1.5" strokeDasharray={w.is_partial ? '4 3' : undefined}>
              <title>{tip}</title>
            </rect>
            {w.completed > 0 && <rect x={xs[i] - barW / 2} y={y(Math.min(w.completed, max))} width={barW} height={innerH - (y(Math.min(w.completed, max)) - PAD.top)} fill={BLUE}><title>{tip}</title></rect>}
            {missed && <text x={xs[i]} y={y(0) - 4} textAnchor="middle" className="training-evolution__missed">0</text>}
          </g>
        );
      })}
      {last(weeks)?.is_partial && <text x={xs[weeks.length - 1]} y={PAD.top - 4} textAnchor="end" className="training-evolution__partial">en curso</text>}
    </Frame>
  );
}

/** RPE de 1 a 10 con la banda de trabajo recomendada (6–8) y huecos donde no hubo reporte. */
export function RpeChart({ points, groupBy, ariaLabel }: { points: RpePoint[]; groupBy: EvolutionGrouping; ariaLabel: string }) {
  const height = 220;
  const innerW = W - PAD.left - PAD.right;
  const innerH = height - PAD.top - PAD.bottom;
  const times = points.map((p) => Date.parse(p.period_start));
  const minT = Math.min(...times);
  const span = Math.max(...times) - minT || 1;
  const xs = times.map((t) => PAD.left + ((t - minT) / span) * innerW);
  const y = (v: number) => PAD.top + innerH - ((v - 1) / 9) * innerH;
  const indexOf = new Map(points.map((p, i) => [p.key, i]));
  const tip = (p: RpePoint) => `${rangeOf(p, groupBy)} · ${p.has_report ? `RPE ${formatNumber(p.rpe as number)}` : 'sin reporte'}${p.trainer_feedback ? ` · Devolución: ${p.trainer_feedback}` : ''}${p.is_partial ? ' (en curso)' : ''}`;
  return (
    <Frame height={height} ariaLabel={ariaLabel}>
      <rect x={PAD.left} y={y(8)} width={innerW} height={y(6) - y(8)} fill="#dcfce7" opacity="0.7"><title>Zona de trabajo recomendada (RPE 6–8)</title></rect>
      {[2, 4, 6, 8, 10].map((tick) => (
        <g key={tick}>
          <line x1={PAD.left} x2={W - PAD.right} y1={y(tick)} y2={y(tick)} className="training-evolution__grid" />
          <text x={PAD.left - 6} y={y(tick) + 4} textAnchor="end" className="training-evolution__tick">{tick}</text>
        </g>
      ))}
      <XLabels days={points.map((p) => p.period_start)} xs={xs} height={height} />
      {reportedRuns(points).map((run) => run.length > 1 && (
        <polyline key={run[0].key} fill="none" stroke={BLUE} strokeWidth="2" points={run.map((p) => `${xs[indexOf.get(p.key) as number]},${y(p.rpe as number)}`).join(' ')} />
      ))}
      {points.map((p, i) => p.has_report ? (
        <circle key={p.key} cx={xs[i]} cy={y(p.rpe as number)} r="4" stroke={BLUE} strokeWidth="2" fill={p.is_partial ? '#fff' : BLUE}><title>{tip(p)}</title></circle>
      ) : (
        <g key={p.key}>
          <text x={xs[i]} y={y(1) - 4} textAnchor="middle" className="training-evolution__nogap">×</text>
          <title>{tip(p)}</title>
        </g>
      ))}
    </Frame>
  );
}

/** Series completadas por semana (barra) contra las programadas (marca), un grupo muscular por fila. */
export function SetsByGroupChart({ groups, ariaLabel }: { groups: MuscleGroupSets[]; ariaLabel: string }) {
  const rowH = 30;
  const labelW = 120;
  const height = groups.length * rowH + 20;
  const max = Math.max(1, ...groups.map((g) => Math.max(g.avg_completed_per_week, g.avg_scheduled_per_week)));
  const innerW = W - labelW - 60;
  const x = (v: number) => labelW + (v / max) * innerW;
  return (
    <Frame height={height} ariaLabel={ariaLabel}>
      {groups.map((g, i) => {
        const top = 10 + i * rowH;
        const tip = `${g.muscle_group} · ${formatNumber(g.avg_completed_per_week)} series por semana de ${formatNumber(g.avg_scheduled_per_week)} programadas`;
        return (
          <g key={g.muscle_group}>
            <text x={labelW - 8} y={top + 15} textAnchor="end" className="training-evolution__tick">{g.muscle_group.length > 16 ? `${g.muscle_group.slice(0, 15)}…` : g.muscle_group}</text>
            <rect x={labelW} y={top + 4} width={Math.max(0, x(g.avg_completed_per_week) - labelW)} height="14" rx="3" fill={BLUE}><title>{tip}</title></rect>
            {g.avg_scheduled_per_week > 0 && <line x1={x(g.avg_scheduled_per_week)} x2={x(g.avg_scheduled_per_week)} y1={top} y2={top + 22} stroke={GOLD} strokeWidth="3"><title>{tip}</title></line>}
            <text x={x(Math.max(g.avg_completed_per_week, g.avg_scheduled_per_week)) + 8} y={top + 15} className="training-evolution__tick">{formatNumber(g.avg_completed_per_week)}/{formatNumber(g.avg_scheduled_per_week)}</text>
          </g>
        );
      })}
    </Frame>
  );
}

type Swatch = 'line' | 'dashed' | 'dotted' | 'dot' | 'hollow' | 'ring' | 'bar-gray' | 'bar-blue' | 'bar-red' | 'bar-partial' | 'band' | 'cross' | 'mark';

function SwatchIcon({ kind }: { kind: Swatch }) {
  const common = { width: 28, height: 14, viewBox: '0 0 28 14', 'aria-hidden': true, className: 'training-evolution__swatch' } as const;
  return (
    <svg {...common}>
      {kind === 'line' && <line x1="2" y1="7" x2="26" y2="7" stroke={BLUE} strokeWidth="2" />}
      {kind === 'dashed' && <><line x1="2" y1="7" x2="17" y2="7" stroke={BLUE} strokeWidth="2" strokeDasharray="5 4" /><circle cx="22" cy="7" r="3.5" fill="#fff" stroke={BLUE} strokeWidth="2" /></>}
      {kind === 'dotted' && <line x1="2" y1="7" x2="26" y2="7" stroke="#94a3b8" strokeWidth="1.5" strokeDasharray="2 4" />}
      {kind === 'dot' && <circle cx="14" cy="7" r="4" fill={BLUE} stroke={BLUE} strokeWidth="2" />}
      {kind === 'hollow' && <circle cx="14" cy="7" r="4" fill="#fff" stroke={BLUE} strokeWidth="2" />}
      {kind === 'ring' && <><circle cx="14" cy="7" r="6" fill="none" stroke={GOLD} strokeWidth="2" /><circle cx="14" cy="7" r="3" fill={BLUE} /></>}
      {kind === 'bar-gray' && <rect x="8" y="1" width="12" height="12" fill="#e2e8f0" />}
      {kind === 'bar-blue' && <rect x="8" y="1" width="12" height="12" fill={BLUE} />}
      {kind === 'bar-red' && <rect x="8" y="1" width="12" height="12" fill="#e2e8f0" stroke={RED} strokeWidth="1.5" />}
      {kind === 'bar-partial' && <rect x="8" y="1" width="12" height="12" fill="#e2e8f0" stroke="#64748b" strokeWidth="1.5" strokeDasharray="4 3" />}
      {kind === 'band' && <rect x="2" y="2" width="24" height="10" fill="#dcfce7" />}
      {kind === 'cross' && <text x="14" y="11" textAnchor="middle" fontSize="12" fill="#475569">×</text>}
      {kind === 'mark' && <line x1="14" y1="0" x2="14" y2="14" stroke={GOLD} strokeWidth="3" />}
    </svg>
  );
}

/** Leyenda con la muestra dibujada igual que en el gráfico: línea continua, entrecortada, punteada, puntos, barras… */
export function Legend({ items }: { items: [Swatch, string][] }) {
  return (
    <ul className="training-evolution__legend">
      {items.map(([kind, text]) => <li key={text}><SwatchIcon kind={kind} />{text}</li>)}
    </ul>
  );
}
