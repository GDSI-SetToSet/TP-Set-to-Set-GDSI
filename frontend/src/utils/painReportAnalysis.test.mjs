import assert from 'node:assert/strict';
import test from 'node:test';
import { aggregatePain, groupByReport, painOnly } from './painReportAnalysis.mjs';

const base = { context: 'IN_EXERCISE', session_id: 's1', exercise_id: 'e1', action_taken: null };
const items = [
  { ...base, id: '1', report_id: 'r1', zone: 'Shoulder', zone_display: 'Hombro', intensity: 'PAIN', created_at: '2026-11-10T12:00:00Z', exercise_name: 'Press banca', exercise_muscle_group: 'Pecho', session_day_name: 'Día 1' },
  { ...base, id: '2', report_id: 'r1', zone: 'Elbow', zone_display: 'Codo', intensity: 'DISCOMFORT', created_at: '2026-11-10T12:00:00Z', exercise_name: 'Press banca', exercise_muscle_group: 'Pecho', session_day_name: 'Día 1' },
  { ...base, id: '3', report_id: 'r2', zone: 'Shoulder', zone_display: 'Hombro', intensity: 'DISCOMFORT', created_at: '2026-11-11T12:00:00Z', exercise_name: 'Remo', exercise_muscle_group: 'Espalda', session_day_name: 'Día 2' },
  { ...base, id: '4', report_id: 'r3', context: 'POST_SESSION', zone: 'Knee', zone_display: 'Rodilla', intensity: 'PAIN', created_at: '2026-11-12T12:00:00Z', exercise_name: null, exercise_id: null, exercise_muscle_group: null, session_day_name: 'Día 2' },
  { ...base, id: '5', report_id: 'r4', zone: 'Hip', zone_display: 'Cadera', intensity: 'NORMAL', created_at: '2026-11-12T13:00:00Z', exercise_name: 'Sentadilla', exercise_muscle_group: 'Piernas', session_day_name: 'Día 3' },
];

test('descarta zonas sin molestia', () => {
  assert.deepEqual(painOnly(items).map((item) => item.id), ['1', '2', '3', '4']);
});

test('agrupa molestias y dolor por zona corporal', () => {
  assert.deepEqual(aggregatePain(items, 'zone'), [
    { label: 'Hombro', discomfort: 1, pain: 1, total: 2 },
    { label: 'Rodilla', discomfort: 0, pain: 1, total: 1 },
    { label: 'Codo', discomfort: 1, pain: 0, total: 1 },
  ]);
});

test('agrupa por grupo muscular, ejercicio y día de rutina', () => {
  assert.deepEqual(aggregatePain(items, 'muscle_group').map((g) => [g.label, g.total]), [
    ['Pecho', 2],
    ['Reporte post-sesión (sin ejercicio)', 1],
    ['Espalda', 1],
  ]);
  assert.deepEqual(aggregatePain(items, 'exercise').map((g) => g.label), ['Press banca', 'Reporte post-sesión (sin ejercicio)', 'Remo']);
  assert.deepEqual(aggregatePain(items, 'routine_day').map((g) => [g.label, g.pain, g.discomfort]), [
    ['Día 1', 1, 1],
    ['Día 2', 1, 1],
  ]);
});

test('lista los reportes con su ejercicio y rutina, del más reciente al más antiguo', () => {
  const reports = groupByReport(items);
  assert.deepEqual(reports.map((report) => report.report_id), ['r3', 'r2', 'r1']);
  assert.deepEqual(reports[2].zones.map((zone) => zone.zone_display), ['Hombro', 'Codo']);
  assert.equal(reports[2].exercise_name, 'Press banca');
  assert.equal(reports[0].session_day_name, 'Día 2');
});

test('sin reportes de malestar no hay grupos', () => {
  assert.deepEqual(aggregatePain([items[4]]), []);
  assert.deepEqual(groupByReport([]), []);
});
