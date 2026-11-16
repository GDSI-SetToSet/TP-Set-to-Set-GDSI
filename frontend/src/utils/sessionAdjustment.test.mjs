import assert from 'node:assert/strict';
import test from 'node:test';
import {
  adjustmentStatusMessage,
  countChanges,
  entryError,
  isAdjustedExercise,
  noticeForDay,
  painIntensityLabel,
  resolveInitialSetDraft,
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

test('DEF-06: entryError filtra por dayIndex cuando se especifica', () => {
  const errors = [{ field: 'days.1.blocks.0.exercises.0.exercise_id', message: 'Contraindicado en día 2' }];
  assert.equal(entryError(errors, 0, 0, 0), undefined);
  assert.equal(entryError(errors, 0, 0, 1), 'Contraindicado en día 2');
});

test('DEF-05: resolveInitialSetDraft prioriza prescripción ajustada sobre registro previo', () => {
  const adjustedItem = { reps: '12', target_weight_kg: 17.5 };
  const prevLog = { reps_completed: '8', weight_kg: 10 };

  assert.deepEqual(
    resolveInitialSetDraft(adjustedItem, prevLog, { isAdjusted: true, isHomeModality: false, nextSet: 1 }),
    { setNumber: '1', repsCompleted: '12', weightKg: '17.5' },
  );

  // Sin ajuste, mantiene referencia del registro anterior salvo en modalidad Casa/Viaje con peso null
  assert.deepEqual(
    resolveInitialSetDraft(adjustedItem, prevLog, { isAdjusted: false, isHomeModality: false, nextSet: 2 }),
    { setNumber: '2', repsCompleted: '8', weightKg: '10' },
  );

  // Sin registro previo y en modalidad Casa/Viaje
  assert.deepEqual(
    resolveInitialSetDraft({ reps: '15', target_weight_kg: null }, undefined, { isAdjusted: true, isHomeModality: true, nextSet: 1 }),
    { setNumber: '1', repsCompleted: '15', weightKg: '0' },
  );
});
