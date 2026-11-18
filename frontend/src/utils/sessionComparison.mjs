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

/** Diferencia firmada de duración (`+5 min`, `−30 s`, `Sin cambios`); null si falta alguno de los valores. */
export function formatDurationDelta(currentSeconds, referenceSeconds) {
  if (!isNumber(currentSeconds) || !isNumber(referenceSeconds)) return null;
  const delta = Math.round(currentSeconds - referenceSeconds);
  if (delta === 0) return 'Sin cambios';
  const sign = delta > 0 ? '+' : '−';
  const abs = Math.abs(delta);
  const hours = Math.floor(abs / 3600);
  const minutes = Math.floor((abs % 3600) / 60);
  const secs = abs % 60;
  if (hours > 0) return `${sign}${hours} h ${String(minutes).padStart(2, '0')} min`;
  if (minutes > 0) return secs ? `${sign}${minutes} min ${secs} s` : `${sign}${minutes} min`;
  return `${sign}${secs} s`;
}

/** Tono neutro para deltas temporales: tardar menos no implica caída de rendimiento ni carga. */
export function durationDeltaTone(currentSeconds, referenceSeconds) {
  if (!isNumber(currentSeconds) || !isNumber(referenceSeconds)) return null;
  return 'neutral';
}

/**
 * Clasifica un ítem de SessionComparison distinguiendo:
 * - 'replaced': ejercicio planificado y reemplazado en la sesión actual
 * - 'planned': ejercicio planificado normalmente
 * - 'unplanned': ejercicio realizado fuera de lo planificado
 * - 'replaced_from_previous': ejercicio de la sesión previa reemplazado en esta sesión
 * - 'previous_only': ejercicio presente únicamente en la sesión previa
 */
export function classifyComparisonExercise(exercise, allExercises = []) {
  if (exercise?.replaced_exercise_name) return 'replaced';
  if (exercise?.planned) return 'planned';
  if (exercise?.performed) return 'unplanned';
  const replacedOriginalNames = new Set(
    (allExercises ?? []).map((item) => item?.replaced_exercise_name).filter(Boolean),
  );
  if (exercise?.previous && replacedOriginalNames.has(exercise.exercise_name)) {
    return 'replaced_from_previous';
  }
  if (exercise?.previous) return 'previous_only';
  return 'planned';
}

/** Subtítulo descriptivo según la clasificación del ejercicio en comparación; null si es planificado estándar. */
export function exerciseNoteLabel(exercise, allExercises = []) {
  const kind = classifyComparisonExercise(exercise, allExercises);
  if (kind === 'replaced') return `reemplazó a ${exercise.replaced_exercise_name}`;
  if (kind === 'unplanned') return 'fuera de lo planificado';
  if (kind === 'replaced_from_previous') return 'reemplazado en esta sesión';
  if (kind === 'previous_only') return 'solo en sesión previa';
  return null;
}
