import assert from 'node:assert/strict';
import test from 'node:test';
import {
  firstName,
  formatAgo,
  formatChange,
  formatRange,
  formatSet,
  niceTicks,
  recentRecordCount,
  reportedRuns,
  sortByStatus,
  statusCounts,
  xLabelIndexes,
} from './trainingEvolution.mjs';

const exercise = (name, status, extra = {}) => ({ exercise_id: name, name, status, last_improvement: null, ...extra });

test('formatRange arma "14–20 sep", "29 sep – 5 oct" y cruces de año', () => {
  assert.equal(formatRange('2026-09-14', '2026-09-20'), '14–20 sep');
  assert.equal(formatRange('2026-09-29', '2026-10-05'), '29 sep – 5 oct');
  assert.equal(formatRange('2026-12-29', '2027-01-04'), '29 dic – 4 ene');
  assert.equal(formatRange('2026-09-14', '2026-09-14'), '14 sep');
});

test('niceTicks da marcas redondeadas desde 0 que cubren el máximo', () => {
  assert.deepEqual(niceTicks(2004), [0, 1000, 2000, 3000]);
  assert.deepEqual(niceTicks(72.5), [0, 20, 40, 60, 80]);
  assert.deepEqual(niceTicks(7, { integer: true }), [0, 2, 4, 6, 8]);
  assert.deepEqual(niceTicks(0), [0, 1, 2]);
});

test('xLabelIndexes muestra todas si caben, o primera, intermedias y última', () => {
  assert.deepEqual(xLabelIndexes(3), [0, 1, 2]);
  assert.deepEqual(xLabelIndexes(12), [0, 3, 6, 8, 11]);
});

test('sortByStatus deja arriba lo que requiere atención: Bajó, Estancado y Progresando', () => {
  const sorted = sortByStatus([
    exercise('Dominadas', 'progressing'),
    exercise('Press banca', 'stalled'),
    exercise('Remo', 'declined'),
    exercise('Plancha', 'no_metric'),
    exercise('Biceps', 'few_data'),
    exercise('Abdominales', 'stalled'),
  ]);
  assert.deepEqual(sorted.map((item) => item.name), ['Remo', 'Abdominales', 'Press banca', 'Dominadas', 'Biceps', 'Plancha']);
});

test('formatSet y formatChange', () => {
  assert.equal(formatSet({ weight: 72.5, reps: 8 }), '72,5 kg × 8');
  assert.equal(formatSet({ weight: null, reps: 9 }), '9 reps');
  assert.equal(formatSet(null), '—');
  assert.equal(formatChange(20.8), '+20,8 %');
  assert.equal(formatChange(-10), '−10 %');
  assert.equal(formatChange(0), '0 %');
  assert.equal(formatChange(null), '—');
});

test('formatAgo', () => {
  assert.equal(formatAgo('2026-11-15', '2026-11-15'), 'hoy');
  assert.equal(formatAgo('2026-11-14', '2026-11-15'), 'hace 1 día');
  assert.equal(formatAgo('2026-11-10', '2026-11-15'), 'hace 5 días');
  assert.equal(formatAgo('2026-10-18', '2026-11-15'), 'hace 4 semanas');
  assert.equal(formatAgo('2026-10-31', '2026-11-15'), 'hace 2 semanas');
});

test('statusCounts y recentRecordCount', () => {
  const list = [
    exercise('A', 'progressing', { last_improvement: { date: '2026-11-12', is_pr: true } }),
    exercise('B', 'progressing', { last_improvement: { date: '2026-10-01', is_pr: true } }),
    exercise('C', 'stalled'),
    exercise('D', 'few_data'),
  ];
  assert.deepEqual(statusCounts(list), { progressing: 2, stalled: 1, declined: 0 });
  assert.equal(recentRecordCount(list, '2026-11-15'), 1);
});

test('reportedRuns corta la línea de RPE en las sesiones sin reporte', () => {
  const point = (key, has_report) => ({ key, has_report });
  const runs = reportedRuns([point(1, true), point(2, true), point(3, false), point(4, true), point(5, false)]);
  assert.deepEqual(runs.map((run) => run.map((p) => p.key)), [[1, 2], [4]]);
  assert.deepEqual(reportedRuns([]), []);
});

test('firstName', () => {
  assert.equal(firstName('Tomás Castro'), 'Tomás');
  assert.equal(firstName('  Ana '), 'Ana');
});
