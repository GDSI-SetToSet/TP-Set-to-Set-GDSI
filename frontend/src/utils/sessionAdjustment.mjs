/** US-26: lógica de la pantalla de ajuste de la próxima sesión y de la marca para el alumno. */

export const ADJUSTED_LABEL = 'Ajustado por tu entrenador';

const PAIN_LABELS = { DISCOMFORT: 'Molestia', PAIN: 'Dolor' };

export function painIntensityLabel(intensity) {
  return PAIN_LABELS[intensity] ?? intensity;
}

function sameEntry(left, right) {
  return Boolean(left) && Boolean(right)
    && left.exercise_id === right.exercise_id
    && left.sets === right.sets
    && left.reps === right.reps
    && left.rest_seconds === right.rest_seconds
    && (left.target_weight_kg ?? null) === (right.target_weight_kg ?? null);
}

/** Cantidad de ejercicios cuya posición o parámetros cambiaron respecto del día original. */
export function countChanges(original, edited) {
  return edited.reduce((total, block, b) => total + block.exercises
    .filter((entry, e) => !sameEntry(entry, original[b]?.exercises[e])).length, 0);
}

/** Cuerpo del PUT: sin nombres de ejercicio y con la nota vacía como null. */
export function toAdjustmentInput(blocks, note) {
  const trimmed = (note ?? '').trim();
  return {
    note: trimmed || null,
    blocks: blocks.map((block) => ({
      name: block.name,
      estimated_duration_minutes: block.estimated_duration_minutes ?? null,
      exercises: block.exercises.map(({ exercise_id, sets, reps, rest_seconds, target_weight_kg }) => ({
        exercise_id, sets, reps, rest_seconds, target_weight_kg: target_weight_kg ?? null,
      })),
    })),
  };
}

/** Error del backend para un ejercicio (los campos llegan como `days.N.blocks.B.exercises.E...`). */
export function entryError(errors, blockIndex, exerciseIndex) {
  const path = `blocks.${blockIndex}.exercises.${exerciseIndex}`;
  return errors.find((error) => error.field.includes(`${path}.`) || error.field.endsWith(path))?.message;
}

export function adjustmentStatusMessage(adjustment) {
  if (!adjustment) return null;
  if (adjustment.status === 'PENDING') {
    return 'Ajuste pendiente: el alumno está entrenando y se aplicará cuando termine su sesión en curso.';
  }
  return 'Ajuste aplicado: el alumno lo verá marcado hasta que entrene este día.';
}

export function noticeForDay(notices, dayName) {
  return notices.find((notice) => notice.day_name === dayName) ?? null;
}

export function isAdjustedExercise(notice, exerciseId) {
  return Boolean(notice?.exercise_ids.includes(exerciseId));
}
