import assert from 'node:assert/strict';
import test from 'node:test';
import {
  RPE_UNREPORTED_LABEL,
  countByStatus,
  dailyRoutineStatusLabel,
  formatDuration,
  formatWeight,
  isFinishedWithoutRpe,
  localDateInputValue,
  sortDailyRoutines,
  totalSets,
} from './dailyRoutineFormat.mjs';

const items = [
  { student_name: 'Zoe', status: 'NOT_STARTED', exercises: [] },
  { student_name: 'Ana', status: 'FINISHED', exercises: [{ sets: [{}, {}] }, { sets: [{}] }] },
  { student_name: 'Bruno', status: 'TRAINING', exercises: [{ sets: [{}] }] },
  { student_name: 'Ariel', status: 'NOT_STARTED', exercises: [] },
];

test('ordena entrenando, finalizadas y no comenzadas', () => {
  assert.deepEqual(sortDailyRoutines(items).map((item) => item.student_name), ['Bruno', 'Ana', 'Ariel', 'Zoe']);
});

test('cuenta alumnos por estado', () => {
  assert.deepEqual(countByStatus(items), { NOT_STARTED: 2, TRAINING: 1, FINISHED: 1 });
});

test('suma las series registradas', () => {
  assert.equal(totalSets(items[1]), 3);
  assert.equal(totalSets(items[0]), 0);
});

test('formatea duraciones y cargas', () => {
  assert.equal(formatDuration(null), '—');
  assert.equal(formatDuration(35), '35 s');
  assert.equal(formatDuration(95), '1 min 35 s');
  assert.equal(formatDuration(2700), '45 min');
  assert.equal(formatDuration(3900), '1 h 05 min');
  assert.equal(formatWeight(null), 'Sin carga');
  assert.equal(formatWeight(22.5), '22,5 kg');
});

test('genera la fecha local para el selector', () => {
  assert.equal(localDateInputValue(new Date(2026, 10, 2, 23, 30)), '2026-11-02');
});

test('identifica sesiones finalizadas sin reporte RPE sin confundirlas con no comenzadas o en curso', () => {
  assert.equal(dailyRoutineStatusLabel({ status: 'NOT_STARTED', session: null }), 'No comenzada');
  assert.equal(dailyRoutineStatusLabel({ status: 'TRAINING', session: { rpe: null } }), 'Entrenando');
  assert.equal(dailyRoutineStatusLabel({ status: 'FINISHED', session: { rpe: 8 } }), 'Finalizada');
  assert.equal(dailyRoutineStatusLabel({ status: 'FINISHED', session: { rpe: null } }), RPE_UNREPORTED_LABEL);
  assert.equal(isFinishedWithoutRpe({ status: 'TRAINING', session: { rpe: null } }), false);
  assert.equal(isFinishedWithoutRpe({ status: 'FINISHED', session: { rpe: null } }), true);
});
