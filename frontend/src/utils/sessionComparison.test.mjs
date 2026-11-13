import assert from 'node:assert/strict';
import test from 'node:test';
import { deltaTone, formatDelta, formatKg, formatReps, setsCompliance } from './sessionComparison.mjs';

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
