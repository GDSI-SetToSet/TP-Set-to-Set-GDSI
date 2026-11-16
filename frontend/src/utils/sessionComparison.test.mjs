import assert from 'node:assert/strict';
import test from 'node:test';
import {
  classifyComparisonExercise,
  deltaTone,
  durationDeltaTone,
  exerciseNoteLabel,
  formatDelta,
  formatDurationDelta,
  formatKg,
  formatReps,
  setsCompliance,
} from './sessionComparison.mjs';

test('formatDelta muestra la diferencia con signo y unidad', () => {
  assert.equal(formatDelta(15, 12.5, 'kg'), '+2,5 kg');
  assert.equal(formatDelta(10, 12, 'kg'), '−2 kg');
  assert.equal(formatDelta(3, 3), 'Sin cambios');
  assert.equal(formatDelta(0.1 + 0.2, 0.3, 'kg'), 'Sin cambios');
  assert.equal(formatDelta(4, 3), '+1');
});

test('formatDelta y deltaTone no comparan si falta un valor', () => {
  assert.equal(formatDelta(10, null, 'kg'), null);
  assert.equal(formatDelta(undefined, 10), null);
  assert.equal(deltaTone(null, 5), null);
});

test('deltaTone indica si subió, bajó o se mantuvo', () => {
  assert.equal(deltaTone(20, 10), 'up');
  assert.equal(deltaTone(5, 10), 'down');
  assert.equal(deltaTone(10, 10), 'same');
});

test('setsCompliance compara series realizadas con las planificadas', () => {
  assert.equal(setsCompliance({ planned: { sets: 3, reps: '8', target_weight_kg: 10 }, performed: { sets_completed: 2 } }), '2 de 3 series');
  assert.equal(setsCompliance({ planned: { sets: 4, reps: '6', target_weight_kg: null }, performed: null }), '0 de 4 series');
  assert.equal(setsCompliance({ planned: null, performed: { sets_completed: 1 } }), null);
});

test('formatReps y formatKg', () => {
  assert.equal(formatReps({ reps: ['8', '8', '7'] }), '8 · 8 · 7');
  assert.equal(formatReps({ reps: [] }), '—');
  assert.equal(formatReps(null), '—');
  assert.equal(formatKg(22.5), '22,5 kg');
  assert.equal(formatKg(null), '—');
});

test('formatDurationDelta compara duraciones en segundos y distingue null de 0', () => {
  assert.equal(formatDurationDelta(1800, 1500), '+5 min');
  assert.equal(formatDurationDelta(1200, 1500), '−5 min');
  assert.equal(formatDurationDelta(0, 0), 'Sin cambios');
  assert.equal(formatDurationDelta(90, 60), '+30 s');
  assert.equal(formatDurationDelta(null, 60), null);
  assert.equal(formatDurationDelta(60, null), null);
});

test('DEF-UX-02: durationDeltaTone mantiene estilo neutro para duraciones', () => {
  assert.equal(durationDeltaTone(1200, 1500), 'neutral');
  assert.equal(durationDeltaTone(1800, 1500), 'neutral');
  assert.equal(durationDeltaTone(1500, 1500), 'neutral');
  assert.equal(durationDeltaTone(null, 1500), null);
  assert.equal(durationDeltaTone(1200, undefined), null);
  // Cargas/volumen mantienen deltaTone intacto
  assert.equal(deltaTone(40, 45), 'down');
  assert.equal(deltaTone(50, 45), 'up');
});

test('DEF-UX-01: classifyComparisonExercise y exerciseNoteLabel distinguen los 4 casos', () => {
  const plannedNormal = {
    exercise_id: 'sq',
    exercise_name: 'Sentadilla',
    replaced_exercise_name: null,
    planned: { sets: 3, reps: '8', target_weight_kg: 40 },
    performed: { sets_completed: 3, reps: ['8', '8', '8'], max_weight_kg: 45, volume_kg: 1080, total_duration_seconds: 90 },
    previous: null,
  };
  const replacedToday = {
    exercise_id: 'fly',
    exercise_name: 'Apertura Mancuernas',
    replaced_exercise_name: 'Press Banca',
    planned: { sets: 3, reps: '10', target_weight_kg: 30 },
    performed: { sets_completed: 2, reps: ['12', '12'], max_weight_kg: 12.5, volume_kg: 300, total_duration_seconds: 0 },
    previous: null,
  };
  const replacedFromPrevious = {
    exercise_id: 'bench',
    exercise_name: 'Press Banca',
    replaced_exercise_name: null,
    planned: null,
    performed: null,
    previous: { sets_completed: 3, reps: ['10', '10', '10'], max_weight_kg: 30, volume_kg: 900, total_duration_seconds: null },
  };
  const unplannedPerformed = {
    exercise_id: 'plank',
    exercise_name: 'Plancha',
    replaced_exercise_name: null,
    planned: null,
    performed: { sets_completed: 1, reps: ['al fallo'], max_weight_kg: null, volume_kg: 0, total_duration_seconds: 30 },
    previous: null,
  };
  const previousOnly = {
    exercise_id: 'curl',
    exercise_name: 'Curl Bíceps',
    replaced_exercise_name: null,
    planned: null,
    performed: null,
    previous: { sets_completed: 2, reps: ['12', '12'], max_weight_kg: 10, volume_kg: 240, total_duration_seconds: 40 },
  };

  const all = [plannedNormal, replacedToday, replacedFromPrevious, unplannedPerformed, previousOnly];

  assert.equal(classifyComparisonExercise(plannedNormal, all), 'planned');
  assert.equal(exerciseNoteLabel(plannedNormal, all), null);

  assert.equal(classifyComparisonExercise(replacedToday, all), 'replaced');
  assert.equal(exerciseNoteLabel(replacedToday, all), 'reemplazó a Press Banca');

  assert.equal(classifyComparisonExercise(unplannedPerformed, all), 'unplanned');
  assert.equal(exerciseNoteLabel(unplannedPerformed, all), 'fuera de lo planificado');

  assert.equal(classifyComparisonExercise(replacedFromPrevious, all), 'replaced_from_previous');
  assert.equal(exerciseNoteLabel(replacedFromPrevious, all), 'reemplazado en esta sesión');

  assert.equal(classifyComparisonExercise(previousOnly, all), 'previous_only');
  assert.equal(exerciseNoteLabel(previousOnly, all), 'solo en sesión previa');
});
