/** US-24: diferencias entre lo realizado en una sesión, lo planificado y la sesión previa. */

const NUMBER_FORMAT = { maximumFractionDigits: 2 };

function isNumber(value) {
  return typeof value === 'number' && Number.isFinite(value);
}

/** Diferencia firmada (`+2,5 kg`, `−1 kg`, `Sin cambios`); null si falta alguno de los dos valores. */
export function formatDelta(current, reference, unit = '') {
  if (!isNumber(current) || !isNumber(reference)) return null;
  const delta = Math.round((current - reference) * 100) / 100;
  if (delta === 0) return 'Sin cambios';
  const sign = delta > 0 ? '+' : '−';
  const amount = Math.abs(delta).toLocaleString('es-AR', NUMBER_FORMAT);
  return `${sign}${amount}${unit ? ` ${unit}` : ''}`;
}

/** 'up' | 'down' | 'same', o null si no hay con qué comparar. */
export function deltaTone(current, reference) {
  if (!isNumber(current) || !isNumber(reference)) return null;
  if (current > reference) return 'up';
  if (current < reference) return 'down';
  return 'same';
}

/** "2 de 3 series" frente a lo planificado; null si el ejercicio no estaba planificado. */
export function setsCompliance(exercise) {
  if (!exercise?.planned) return null;
  const done = exercise.performed?.sets_completed ?? 0;
  return `${done} de ${exercise.planned.sets} series`;
}

/** Repeticiones realizadas por serie, p. ej. "8 · 8 · 7"; guion si no registró series. */
export function formatReps(metrics) {
  if (!metrics || metrics.reps.length === 0) return '—';
  return metrics.reps.join(' · ');
}

export function formatKg(value) {
  if (!isNumber(value)) return '—';
  return `${value.toLocaleString('es-AR', NUMBER_FORMAT)} kg`;
}
