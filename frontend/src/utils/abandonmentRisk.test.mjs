import assert from 'node:assert/strict';
import test from 'node:test';
import { abandonmentRiskDescription, sortByAbandonmentRisk } from './abandonmentRisk.mjs';

const students = [
  { relationship_id: 'a', student_name: 'Ana' },
  { relationship_id: 'b', student_name: 'Bruno' },
  { relationship_id: 'c', student_name: 'Carla' },
  { relationship_id: 'd', student_name: 'Diego' },
];

test('muestra primero a los alumnos con riesgo de abandono, el más inactivo antes', () => {
  const risks = [
    { relationship_id: 'a', at_risk: false, days_without_report: 2 },
    { relationship_id: 'c', at_risk: true, days_without_report: 15 },
    { relationship_id: 'd', at_risk: true, days_without_report: 30 },
  ];
  assert.deepEqual(sortByAbandonmentRisk(students, risks).map((s) => s.relationship_id), ['d', 'c', 'a', 'b']);
});

test('sin riesgos conserva el orden original', () => {
  assert.deepEqual(sortByAbandonmentRisk(students, []), students);
});

test('describe el motivo del riesgo', () => {
  assert.equal(abandonmentRiskDescription(undefined), '');
  assert.equal(abandonmentRiskDescription({ at_risk: false }), '');
  assert.equal(
    abandonmentRiskDescription({ at_risk: true, reason: 'MISSED_TRAININGS', missed_trainings: 5, days_without_report: 12, last_report_at: '2026-11-01T10:00:00Z' }),
    'Lleva 5 entrenamientos sin reportar.',
  );
  assert.equal(
    abandonmentRiskDescription({ at_risk: true, reason: 'INACTIVE_TWO_WEEKS', missed_trainings: 2, days_without_report: 15, last_report_at: '2026-10-28T10:00:00Z' }),
    'No reporta entrenamientos hace 15 días.',
  );
  assert.equal(
    abandonmentRiskDescription({ at_risk: true, reason: 'INACTIVE_TWO_WEEKS', missed_trainings: 2, days_without_report: 16, last_report_at: null }),
    'No reportó ningún entrenamiento en 16 días.',
  );
});
