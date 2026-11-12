export const DAILY_STATUS_LABELS = {
  NOT_STARTED: 'No comenzada',
  TRAINING: 'Entrenando',
  FINISHED: 'Finalizada',
};

const STATUS_ORDER = { TRAINING: 0, FINISHED: 1, NOT_STARTED: 2 };

export function localDateInputValue(date = new Date()) {
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${date.getFullYear()}-${month}-${day}`;
}

export function formatDuration(seconds) {
  if (seconds === null || seconds === undefined) return '—';
  const total = Math.max(0, Math.round(seconds));
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const rest = total % 60;
  if (hours > 0) return `${hours} h ${String(minutes).padStart(2, '0')} min`;
  if (minutes > 0) return rest ? `${minutes} min ${rest} s` : `${minutes} min`;
  return `${rest} s`;
}

export function formatWeight(weight) {
  if (weight === null || weight === undefined) return 'Sin carga';
  return `${Number(weight).toLocaleString('es-AR', { maximumFractionDigits: 2 })} kg`;
}

/** Entrenando primero, luego finalizadas y al final las no comenzadas; alfabético dentro de cada estado. */
export function sortDailyRoutines(items) {
  return [...items].sort((left, right) => (STATUS_ORDER[left.status] ?? 3) - (STATUS_ORDER[right.status] ?? 3)
    || left.student_name.localeCompare(right.student_name, 'es-AR'));
}

export function countByStatus(items) {
  return items.reduce(
    (counts, item) => ({ ...counts, [item.status]: (counts[item.status] ?? 0) + 1 }),
    { NOT_STARTED: 0, TRAINING: 0, FINISHED: 0 },
  );
}

export function totalSets(item) {
  return item.exercises.reduce((total, exercise) => total + exercise.sets.length, 0);
}
