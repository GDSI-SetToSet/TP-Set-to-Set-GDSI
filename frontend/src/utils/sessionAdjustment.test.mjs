import assert from 'node:assert/strict';
import test from 'node:test';
import {
  adjustmentStatusMessage,
  countChanges,
  entryError,
  isAdjustedExercise,
  noticeForDay,
  painIntensityLabel,
  toAdjustmentInput,
} from './sessionAdjustment.mjs';

const entry = { exercise_id: 'squat', exercise_name: 'Sentadilla', sets: 3, reps: '8', rest_seconds: 60, target_weight_kg: 10 };
const day = [{ name: 'Principal', estimated_duration_minutes: null, exercises: [entry] }];

test('countChanges detecta cambios de parámetros y de ejercicio', () => {
  assert.equal(countChanges(day, day), 0);
  assert.equal(countChanges(day, [{ ...day[0], exercises: [{ ...entry, sets: 4 }] }]), 1);
  assert.equal(countChanges(day, [{ ...day[0], exercises: [{ ...entry, exercise_id: 'lunge' }] }]), 1);
  assert.equal(countChanges(day, [{ ...day[0], exercises: [{ ...entry, target_weight_kg: null }] }]), 1);
  assert.equal(countChanges(day, [{ ...day[0], exercises: [entry, { ...entry, exercise_id: 'plank' }] }]), 1);
});

test('toAdjustmentInput quita nombres y normaliza la nota', () => {
  assert.deepEqual(toAdjustmentInput(day, '  Subí la carga '), {
    note: 'Subí la carga',
    blocks: [{
      name: 'Principal',
      estimated_duration_minutes: null,
      exercises: [{ exercise_id: 'squat', sets: 3, reps: '8', rest_seconds: 60, target_weight_kg: 10 }],
    }],
  });
  assert.equal(toAdjustmentInput(day, '   ').note, null);
  assert.equal(toAdjustmentInput(day, undefined).note, null);
});

test('entryError ubica el error del backend en el ejercicio', () => {
  const errors = [{ field: 'days.0.blocks.1.exercises.2.exercise_id', message: 'Contraindicado' }];
  assert.equal(entryError(errors, 1, 2), 'Contraindicado');
  assert.equal(entryError(errors, 0, 2), undefined);
  assert.equal(entryError([{ field: 'days.0.blocks.1.exercises.12.exercise_id', message: 'x' }], 1, 1), undefined);
});

test('adjustmentStatusMessage según el estado', () => {
  assert.equal(adjustmentStatusMessage(null), null);
  assert.match(adjustmentStatusMessage({ status: 'PENDING' }), /pendiente/);
  assert.match(adjustmentStatusMessage({ status: 'APPLIED' }), /aplicado/);
});

test('marca de ajuste para el alumno', () => {
  const notices = [{ day_name: 'Día 1', note: null, exercise_ids: ['squat'], adjusted_at: '2026-11-13T10:00:00Z' }];
  const notice = noticeForDay(notices, 'Día 1');
  assert.equal(noticeForDay(notices, 'Día 2'), null);
  assert.equal(isAdjustedExercise(notice, 'squat'), true);
  assert.equal(isAdjustedExercise(notice, 'lunge'), false);
  assert.equal(isAdjustedExercise(null, 'squat'), false);
});

test('painIntensityLabel', () => {
  assert.equal(painIntensityLabel('PAIN'), 'Dolor');
  assert.equal(painIntensityLabel('DISCOMFORT'), 'Molestia');
});
