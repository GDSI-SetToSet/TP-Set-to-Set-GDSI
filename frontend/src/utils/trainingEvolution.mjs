export const EVOLUTION_GROUPINGS = { session: 'Por entrenamiento', week: 'Por semana' };
export const EVOLUTION_PERIODS = { '4w': '4 semanas', '12w': '12 semanas', all: 'Todo el historial' };

export const STATUS_ORDER = { declined: 0, stalled: 1, progressing: 2, unchanged: 3, few_data: 4, no_metric: 5 };
export const STATUS_LABELS = {
  progressing: '↗ Progresando',
  stalled: '⚠ Estancado',
  declined: '↘ Bajó',
  unchanged: '→ Sin cambios',
  few_data: 'Pocos datos',
  no_metric: 'Sin métrica',
};
export const LIGHT_LABELS = { green: 'En orden', yellow: 'Atención', red: 'Revisar' };
export const EFFORT_MESSAGES = {
  excessive_effort: '⚠ Hubo sesiones con esfuerzo excesivo',
  fatigue: '⚠ El esfuerzo sube sin mejora de carga: posible fatiga',
  room_for_more: 'Podría exigirse más',
  progressing_effort_rising: 'Progresa, pero el esfuerzo viene en aumento',
  progressing_with_margin: 'Progresa con buen margen de esfuerzo',
};
export const TREND_LABELS = { rising: 'subiendo', stable: 'estable', falling: 'bajando' };
export const REVIEW_HINT = {
  exercise_declined: 'Bajó',
  exercise_stalled: 'Estancado',
  fatigue: 'Esfuerzo',
  excessive_effort: 'Esfuerzo',
  exercise_skipped: 'Salteado',
  week_without_training: 'Adherencia',
};

const MONTHS = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];

/** Las fechas llegan como 'YYYY-MM-DD' (sin hora): se leen como texto para no depender de la zona horaria. */
function parts(isoDate) {
  const [, month, day] = isoDate.split('-').map(Number);
  return { day, month: MONTHS[month - 1] };
}

/** '14 sep' */
export function formatDay(isoDate) {
  const { day, month } = parts(isoDate);
  return `${day} ${month}`;
}

/** '14 sep' (un día), '14–20 sep' (mismo mes) o '29 sep – 5 oct' (meses distintos). */
export function formatRange(start, end) {
  if (start === end) return formatDay(start);
  const a = parts(start);
  const b = parts(end);
  return a.month === b.month ? `${a.day}–${b.day} ${b.month}` : `${a.day} ${a.month} – ${b.day} ${b.month}`;
}

/** Entre 3 y 5 marcas redondeadas desde 0 que cubren el máximo (2004 → 0, 1000, 2000, 3000). */
export function niceTicks(max, { integer = false, count = 4 } = {}) {
  if (!(max > 0)) return [0, 1, 2];
  const rough = max / count;
  const base = 10 ** Math.floor(Math.log10(rough));
  const fraction = rough / base;
  let step = (fraction <= 1 ? 1 : fraction <= 2 ? 2 : fraction <= 5 ? 5 : 10) * base;
  if (integer) step = Math.max(1, Math.ceil(step));
  const ticks = [];
  for (let value = 0; ; value += step) {
    ticks.push(Number(value.toFixed(10)));
    if (value >= max) return ticks;
  }
}

/** Índices de las etiquetas del eje X: todas si caben; si no, la primera, algunas intermedias y la última. */
export function xLabelIndexes(total, max = 5) {
  if (total <= max) return Array.from({ length: total }, (_, index) => index);
  const picked = new Set();
  for (let i = 0; i < max; i += 1) picked.add(Math.round((i * (total - 1)) / (max - 1)));
  return [...picked];
}

export function formatNumber(value) {
  return new Intl.NumberFormat('es-AR', { maximumFractionDigits: 1 }).format(value);
}

/** Primero lo que requiere atención: Bajó, Estancado, Progresando…; a igual estado, por nombre. */
export function sortByStatus(exercises) {
  return [...exercises].sort(
    (left, right) => STATUS_ORDER[left.status] - STATUS_ORDER[right.status] || left.name.localeCompare(right.name, 'es'),
  );
}

/** '72,5 kg × 8', '9 reps' (sin carga) o '—'. */
export function formatSet(set) {
  if (!set || set.reps === null || set.reps === undefined) return '—';
  return set.weight ? `${formatNumber(set.weight)} kg × ${set.reps}` : `${set.reps} reps`;
}

/** '+21 %', '−10 %', '0 %' o '—'. */
export function formatChange(pct) {
  if (pct === null || pct === undefined) return '—';
  if (pct === 0) return '0 %';
  return `${pct > 0 ? '+' : '−'}${formatNumber(Math.abs(pct))} %`;
}

export function daysBetween(fromIso, toIso) {
  const [ya, ma, da] = fromIso.split('-').map(Number);
  const [yb, mb, db] = toIso.split('-').map(Number);
  return Math.round((Date.UTC(yb, mb - 1, db) - Date.UTC(ya, ma - 1, da)) / 86_400_000);
}

/** 'hoy', 'hace 5 días' o 'hace 4 semanas'. */
export function formatAgo(isoDate, todayIso) {
  const days = daysBetween(isoDate, todayIso);
  if (days <= 0) return 'hoy';
  if (days === 1) return 'hace 1 día';
  if (days < 14) return `hace ${days} días`;
  return `hace ${Math.floor(days / 7)} semanas`;
}

/** Cantidad de ejercicios por estado, para la línea de respuesta. */
export function statusCounts(exercises) {
  const counts = { progressing: 0, stalled: 0, declined: 0 };
  for (const item of exercises) if (item.status in counts) counts[item.status] += 1;
  return counts;
}

/** Ejercicios cuya última mejora fue el récord vigente y ocurrió en la última semana. */
export function recentRecordCount(exercises, todayIso) {
  return exercises.filter((item) => item.last_improvement?.is_pr && daysBetween(item.last_improvement.date, todayIso) <= 7).length;
}

/** Tramos continuos de puntos con reporte: los huecos (sin reporte) cortan la línea. */
export function reportedRuns(points) {
  const runs = [];
  let current = [];
  for (const point of points) {
    if (point.has_report) current.push(point);
    else if (current.length) { runs.push(current); current = []; }
  }
  if (current.length) runs.push(current);
  return runs;
}

/** 'Tomás Castro' → 'Tomás' */
export function firstName(fullName) {
  return fullName.trim().split(/\s+/)[0] ?? fullName;
}
