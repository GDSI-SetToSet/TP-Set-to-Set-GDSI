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

test('prioriza alertas de seguridad PENDING de US-29 por encima del riesgo de abandono (US-32)', () => {
  const risks = [
    { relationship_id: 'd', at_risk: true, days_without_report: 30 },
    { relationship_id: 'c', at_risk: true, days_without_report: 15 },
  ];
  const safetyAlerts = [
    { relationship_id: 'b', status: 'PENDING', created_at: '2026-11-10T10:00:00Z' },
    { relationship_id: 'a', status: 'REVIEWED', created_at: '2026-11-11T10:00:00Z' },
  ];
  assert.deepEqual(
    sortByAbandonmentRisk(students, risks, safetyAlerts).map((s) => s.relationship_id),
    ['b', 'd', 'c', 'a'],
  );
});

test('LOW-01: unifica desempate y tercer nivel alfabético por apellido y nombre igual que backend y panel de asignaciones', () => {
  const mixedStudents = [
    { relationship_id: 'alba-z', student_name: 'Alba Zeta' },
    { relationship_id: 'zoe-a', student_name: 'Zoe Alpha' },
    { relationship_id: 'ana-a', student_name: 'Ana Alpha' },
    { relationship_id: 'bruno-r', student_name: 'Bruno Zeta' },
    { relationship_id: 'dario-r', student_name: 'Dario Alpha' },
  ];
  const risks = [
    { relationship_id: 'bruno-r', at_risk: true, days_without_report: 15 },
    { relationship_id: 'dario-r', at_risk: true, days_without_report: 15 },
  ];
  assert.deepEqual(
    sortByAbandonmentRisk(mixedStudents, risks, []).map((s) => s.relationship_id),
    ['dario-r', 'bruno-r', 'ana-a', 'zoe-a', 'alba-z'],
  );
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
