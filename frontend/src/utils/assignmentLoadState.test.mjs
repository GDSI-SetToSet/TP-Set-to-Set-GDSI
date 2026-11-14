import assert from 'node:assert/strict';
import test from 'node:test';
import {
  LOAD_PLANS_ERROR,
  LOAD_RISK_ERROR,
  LOAD_SAFETY_ALERTS_ERROR,
  LOAD_STUDENTS_ERROR,
  applyAuxiliaryRetry,
  resolveAssignmentLoadResults,
} from './assignmentLoadState.mjs';

test('diferencia listado vacío real de error al cargar alumnos', () => {
  const emptySuccess = resolveAssignmentLoadResults(
    { status: 'fulfilled', value: [] },
    { status: 'fulfilled', value: [] },
    { status: 'fulfilled', value: [] },
  );
  assert.deepEqual(emptySuccess.students, []);
  assert.equal(emptySuccess.error, '');
  assert.equal(emptySuccess.plansError, '');
  assert.equal(emptySuccess.riskError, '');

  const failedStudents = resolveAssignmentLoadResults(
    { status: 'rejected', reason: new Error('network') },
    { status: 'fulfilled', value: [] },
    { status: 'fulfilled', value: [] },
  );
  assert.equal(failedStudents.students, null);
  assert.equal(failedStudents.error, LOAD_STUDENTS_ERROR);
});

test('informa errores al cargar planes y riesgo de abandono sin silenciarlos', () => {
  const partialFailure = resolveAssignmentLoadResults(
    { status: 'fulfilled', value: [{ relationship_id: 'r1', student_name: 'Ana' }] },
    { status: 'rejected', reason: new Error('plans down') },
    { status: 'rejected', reason: new Error('risk down') },
  );
  assert.equal(partialFailure.students.length, 1);
  assert.equal(partialFailure.error, '');
  assert.equal(partialFailure.plansError, LOAD_PLANS_ERROR);
  assert.equal(partialFailure.riskError, LOAD_RISK_ERROR);
});

test('permite reintentar consultas auxiliares fallidas manteniendo las exitosas', () => {
  const initial = {
    trainerPlans: [],
    plansError: LOAD_PLANS_ERROR,
    abandonmentRisks: [],
    riskError: LOAD_RISK_ERROR,
  };
  const afterPartialRetry = applyAuxiliaryRetry(
    initial,
    { status: 'fulfilled', value: [{ id: 'p1', title: 'Mensual' }] },
    { status: 'rejected', reason: new Error('still down') },
  );
  assert.deepEqual(afterPartialRetry.trainerPlans, [{ id: 'p1', title: 'Mensual' }]);
  assert.equal(afterPartialRetry.plansError, '');
  assert.equal(afterPartialRetry.riskError, LOAD_RISK_ERROR);

  const afterFullRetry = applyAuxiliaryRetry(
    afterPartialRetry,
    null,
    { status: 'fulfilled', value: [{ relationship_id: 'r1', at_risk: true }] },
  );
  assert.equal(afterFullRetry.trainerPlans.length, 1);
  assert.equal(afterFullRetry.abandonmentRisks.length, 1);
  assert.equal(afterFullRetry.riskError, '');
});

test('informa y reintenta fallas al cargar alertas de seguridad pendientes (US-29)', () => {
  const initial = resolveAssignmentLoadResults(
    { status: 'fulfilled', value: [{ relationship_id: 'r1', student_name: 'Ana' }] },
    { status: 'fulfilled', value: [] },
    { status: 'fulfilled', value: [] },
    { status: 'rejected', reason: new Error('safety alerts unavailable') },
  );
  assert.deepEqual(initial.safetyAlerts, []);
  assert.equal(initial.safetyAlertsError, LOAD_SAFETY_ALERTS_ERROR);

  const afterRetry = applyAuxiliaryRetry(
    initial,
    null,
    null,
    { status: 'fulfilled', value: [{ id: 'sa-1', relationship_id: 'r1', status: 'PENDING' }] },
  );
  assert.equal(afterRetry.safetyAlerts.length, 1);
  assert.equal(afterRetry.safetyAlertsError, '');
});
