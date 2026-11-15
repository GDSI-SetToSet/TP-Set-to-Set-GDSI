import assert from 'node:assert/strict';
import test from 'node:test';
import {
  SAFETY_ALERT_ACTION_LABELS,
  SAFETY_ALERT_ACTION_OPTIONS,
  SAFETY_ALERT_TYPE_LABELS,
  compareStudentNamesAlphabetically,
  createScopedRequestTracker,
  executeAlertReviewSubmit,
  executeStudentDetailRequest,
  executeStudentSafetyAlertsRequest,
  focusSafetyAlertsTransition,
  formatSafetyAlertSummary,
  formatStudentPainReviewedNotice,
  getReviewSubmitButtonState,
  groupPendingAlertsByRelationship,
  resolvePainAlertHighlightId,
  runOpenProgressSafetyTransition,
  runSafetyRefreshTransition,
  sortAssignmentsByPriority,
} from './safetyAlerts.mjs';

function createDeferred() {
  let resolve;
  let reject;
  const promise = new Promise((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

test('sortAssignmentsByPriority respeta US-29 > US-32 > alfabético e ignora alertas ya revisadas', () => {
  const students = [
    { relationship_id: 'rel-z', student_name: 'Zoe López' },
    { relationship_id: 'rel-risk-low', student_name: 'Ana Pérez' },
    { relationship_id: 'rel-alpha', student_name: 'Bruno Díaz' },
    { relationship_id: 'rel-alert-1', student_name: 'Carlos Gómez' },
    { relationship_id: 'rel-risk-high', student_name: 'Elena Ruiz' },
    { relationship_id: 'rel-alert-2', student_name: 'Diego Sosa' },
  ];
  const risks = [
    { relationship_id: 'rel-risk-low', at_risk: true, days_without_report: 15 },
    { relationship_id: 'rel-risk-high', at_risk: true, days_without_report: 28 },
    { relationship_id: 'rel-alert-1', at_risk: false, days_without_report: 1 },
  ];
  const alerts = [
    { id: 'a1', relationship_id: 'rel-alert-1', status: 'PENDING', created_at: '2026-11-10T10:00:00Z' },
    { id: 'a2', relationship_id: 'rel-alert-2', status: 'PENDING', created_at: '2026-11-09T10:00:00Z' },
    { id: 'a3', relationship_id: 'rel-alert-2', status: 'PENDING', created_at: '2026-11-11T10:00:00Z' },
    { id: 'a4', relationship_id: 'rel-z', status: 'REVIEWED', created_at: '2026-11-12T10:00:00Z' },
  ];

  const ordered = sortAssignmentsByPriority(students, risks, alerts);
  assert.deepEqual(
    ordered.map((item) => item.relationship_id),
    ['rel-alert-2', 'rel-alert-1', 'rel-risk-high', 'rel-risk-low', 'rel-alpha', 'rel-z'],
  );
});

test('groupPendingAlertsByRelationship agrupa solo alertas PENDING', () => {
  const grouped = groupPendingAlertsByRelationship([
    { id: '1', relationship_id: 'r1', status: 'PENDING', created_at: '2026-11-10T10:00:00Z' },
    { id: '2', relationship_id: 'r1', status: 'PENDING', created_at: '2026-11-10T12:00:00Z' },
    { id: '3', relationship_id: 'r1', status: 'REVIEWED', created_at: '2026-11-11T12:00:00Z' },
  ]);
  assert.equal(grouped.get('r1').count, 2);
  assert.equal(grouped.get('r1').latestCreatedAtMs, Date.parse('2026-11-10T12:00:00Z'));
});

test('formatSafetyAlertSummary genera etiquetas y contexto por tipo y acción', () => {
  assert.equal(SAFETY_ALERT_ACTION_OPTIONS.length, 3);
  assert.equal(SAFETY_ALERT_ACTION_LABELS.ADJUSTED_ROUTINE, 'Ajusté la rutina');
  assert.equal(SAFETY_ALERT_TYPE_LABELS.EXCESSIVE_EFFORT, 'Esfuerzo excesivo');

  const painSummary = formatSafetyAlertSummary({
    alert_type: 'PAIN',
    zone: 'Shoulder',
    zone_display_name: 'Hombro',
    exercise_name: 'Press militar',
    session_day_name: 'Día 1 - Torso',
    status: 'PENDING',
    action_taken: null,
    trainer_note: '  ',
  });
  assert.equal(painSummary.typeLabel, 'Dolor reportado');
  assert.equal(painSummary.detailText, 'Hombro · Press militar · Día 1 - Torso');
  assert.equal(painSummary.statusLabel, 'Pendiente');
  assert.equal(painSummary.note, null);

  const discomfortSummary = formatSafetyAlertSummary({
    alert_type: 'REPEATED_DISCOMFORT',
    zone: 'Knee',
    zone_display_name: 'Rodilla',
    session_day_name: 'Día 2 - Piernas',
    status: 'REVIEWED',
    action_taken: 'CONTACTED_STUDENT',
    trainer_note: 'Revisar técnica antes de cargar',
  });
  assert.equal(discomfortSummary.detailText, 'Rodilla · 2 sesiones consecutivas · Día 2 - Piernas');
  assert.equal(discomfortSummary.statusLabel, 'Revisada');
  assert.equal(discomfortSummary.actionLabel, 'Contacté al alumno');
  assert.equal(discomfortSummary.note, 'Revisar técnica antes de cargar');

  const rpeSummary = formatSafetyAlertSummary({
    alert_type: 'EXCESSIVE_EFFORT',
    rpe: 10,
    session_day_name: 'Día 3 - Full body',
    status: 'REVIEWED',
    action_taken: 'NO_ACTION',
    trainer_note: null,
  });
  assert.equal(rpeSummary.detailText, 'RPE 10/10 · Día 3 - Full body');
  assert.equal(rpeSummary.actionLabel, 'Sin acción');
});

test('formatStudentPainReviewedNotice muestra nota solo si existe y excluye otros tipos de alerta (CA-5)', () => {
  const withNote = formatStudentPainReviewedNotice({
    id: 'n1',
    zone: 'Lower back',
    zone_display_name: 'Espalda baja',
    exercise_name: 'Peso muerto',
    session_day_name: 'Día 2',
    action_taken: 'ADJUSTED_ROUTINE',
    trainer_note: '  Bajamos el peso esta semana  ',
    reviewed_at: '2026-11-11T10:00:00Z',
  });
  assert.equal(withNote.title, 'Tu entrenador revisó tu reporte de dolor');
  assert.equal(withNote.actionLabel, 'Ajusté la rutina');
  assert.equal(withNote.trainerNote, 'Bajamos el peso esta semana');
  assert.equal(withNote.contextText, 'Zona: Espalda baja · Peso muerto · Día 2');

  const withoutNote = formatStudentPainReviewedNotice({
    id: 'n2',
    zone_display_name: 'Hombro',
    action_taken: 'CONTACTED_STUDENT',
    trainer_note: '   ',
    reviewed_at: '2026-11-11T10:00:00Z',
  });
  assert.equal(withoutNote.trainerNote, null);

  assert.equal(
    formatStudentPainReviewedNotice({ id: 'n3', alert_type: 'REPEATED_DISCOMFORT', action_taken: 'NO_ACTION', reviewed_at: '2026-11-11T10:00:00Z' }),
    null,
  );
  assert.equal(
    formatStudentPainReviewedNotice({ id: 'n4', alert_type: 'EXCESSIVE_EFFORT', action_taken: 'NO_ACTION', reviewed_at: '2026-11-11T10:00:00Z' }),
    null,
  );
});

test('MED-01: alumno A responde después de alumno B sin sobrescribir estado visible ni mezclar alertas', async () => {
  const detailTracker = createScopedRequestTracker();
  const alertsTracker = createScopedRequestTracker();
  const deferredDetail = { A: createDeferred(), B: createDeferred() };
  const deferredAlerts = { A: createDeferred(), B: createDeferred() };

  const visibleState = {
    selectedStudentId: null,
    detailStudentId: null,
    studentDetail: null,
    detailLoading: false,
    detailError: '',
    safetyAlerts: [],
    alertsLoading: false,
    alertsError: '',
  };

  function selectAndLoad(studentId) {
    visibleState.selectedStudentId = studentId;
    visibleState.studentDetail = null;
    visibleState.detailStudentId = null;
    visibleState.detailError = '';
    visibleState.detailLoading = true;
    visibleState.safetyAlerts = [];
    visibleState.alertsError = '';
    visibleState.alertsLoading = true;

    const pDetail = executeStudentDetailRequest({
      studentId,
      tracker: detailTracker,
      isSelectedStudent: (id) => visibleState.selectedStudentId === id,
      fetchDetail: (id) => deferredDetail[id].promise,
      onSuccess: (detail) => {
        visibleState.studentDetail = detail;
        visibleState.detailStudentId = studentId;
      },
      onError: () => {
        visibleState.detailError = `Error detalle ${studentId}`;
      },
      onFinally: () => {
        visibleState.detailLoading = false;
      },
    });

    const pAlerts = executeStudentSafetyAlertsRequest({
      studentId,
      tracker: alertsTracker,
      isCurrentStudent: (id) => visibleState.selectedStudentId === id,
      fetchAlerts: (id) => deferredAlerts[id].promise,
      onSuccess: (items) => {
        visibleState.safetyAlerts = items;
      },
      onError: () => {
        visibleState.alertsError = `Error alertas ${studentId}`;
      },
      onFinally: () => {
        visibleState.alertsLoading = false;
      },
    });

    return { pDetail, pAlerts };
  }

  // Entrenador selecciona rápido Alumno A y luego Alumno B antes de recibir respuesta de A.
  const reqA = selectAndLoad('A');
  const reqB = selectAndLoad('B');

  // B responde primero y actualiza el estado visible.
  deferredDetail.B.resolve({ profile: { id: 'B', first_name: 'Bruno', last_name: 'Díaz' } });
  deferredAlerts.B.resolve([{ id: 'alert-B', student_id: 'B', status: 'PENDING' }]);
  await Promise.all([reqB.pDetail, reqB.pAlerts]);

  assert.equal(visibleState.selectedStudentId, 'B');
  assert.equal(visibleState.detailStudentId, 'B');
  assert.equal(visibleState.studentDetail.profile.first_name, 'Bruno');
  assert.equal(visibleState.detailLoading, false);
  assert.equal(visibleState.detailError, '');
  assert.deepEqual(visibleState.safetyAlerts.map((a) => a.id), ['alert-B']);

  // Luego responde A tarde (detalle con datos de A y alertas de A): no debe tocar nada visible de B.
  deferredDetail.A.resolve({ profile: { id: 'A', first_name: 'Ana', last_name: 'Pérez' } });
  deferredAlerts.A.resolve([{ id: 'alert-A', student_id: 'A', status: 'PENDING' }]);
  await Promise.all([reqA.pDetail, reqA.pAlerts]);

  assert.equal(visibleState.selectedStudentId, 'B');
  assert.equal(visibleState.detailStudentId, 'B');
  assert.equal(visibleState.studentDetail.profile.id, 'B');
  assert.equal(visibleState.studentDetail.profile.first_name, 'Bruno');
  assert.deepEqual(visibleState.safetyAlerts.map((a) => a.id), ['alert-B']);
  assert.equal(visibleState.detailError, '');
  assert.equal(visibleState.alertsError, '');
});

test('MED-01: petición anterior de alertas finalizada después de una actualización más reciente se ignora', async () => {
  const studentTracker = createScopedRequestTracker();
  const globalTracker = createScopedRequestTracker();
  const oldStudentReq = createDeferred();
  const freshStudentReq = createDeferred();
  const oldGlobalReq = createDeferred();
  const freshGlobalReq = createDeferred();

  const visible = {
    studentAlerts: [],
    pendingAlerts: [],
    studentError: '',
  };

  let studentFetchIndex = 0;
  const loadStudent = () => executeStudentSafetyAlertsRequest({
    studentId: 'stu-1',
    tracker: studentTracker,
    fetchAlerts: () => (++studentFetchIndex === 1 ? oldStudentReq.promise : freshStudentReq.promise),
    onSuccess: (items) => { visible.studentAlerts = items; },
    onError: () => { visible.studentError = 'error'; },
  });

  // 1) Dispara petición vieja q1 que queda lenta y luego se revisa una alerta / llega q2 más reciente.
  const pOldStudent = loadStudent();
  studentTracker.invalidate('stu-1');
  visible.studentAlerts = [{ id: 'al-1', status: 'REVIEWED' }];

  const pFreshStudent = loadStudent();
  freshStudentReq.resolve([{ id: 'al-1', status: 'REVIEWED', action_taken: 'CONTACTED_STUDENT' }]);
  await pFreshStudent;
  assert.equal(visible.studentAlerts[0].status, 'REVIEWED');

  // La petición vieja rechaza o devuelve PENDING tarde: el estado visible permanece REVIEWED sin error.
  oldStudentReq.resolve([{ id: 'al-1', status: 'PENDING' }]);
  await pOldStudent;
  assert.equal(visible.studentAlerts[0].status, 'REVIEWED');
  assert.equal(visible.studentAlerts[0].action_taken, 'CONTACTED_STUDENT');
  assert.equal(visible.studentError, '');

  // Mismo escenario en alertas globales PENDING ante safetyRefreshKey 1 -> 2.
  let globalIdx = 0;
  const fetchGlobal = () => (++globalIdx === 1 ? oldGlobalReq.promise : freshGlobalReq.promise);
  const pOldGlobal = runSafetyRefreshTransition({
    safetyRefreshKey: 1,
    openRelationshipId: null,
    students: [],
    globalTracker,
    fetchPendingAlerts: fetchGlobal,
    onPendingSuccess: (items) => { visible.pendingAlerts = items; },
    loadStudentAlerts: () => undefined,
  });
  const pFreshGlobal = runSafetyRefreshTransition({
    safetyRefreshKey: 2,
    openRelationshipId: null,
    students: [],
    globalTracker,
    fetchPendingAlerts: fetchGlobal,
    onPendingSuccess: (items) => { visible.pendingAlerts = items; },
    loadStudentAlerts: () => undefined,
  });

  freshGlobalReq.resolve([]); // ya se revisó la última alerta
  await pFreshGlobal;
  assert.deepEqual(visible.pendingAlerts, []);

  oldGlobalReq.resolve([{ id: 'stale-pending', status: 'PENDING' }]);
  await pOldGlobal;
  assert.deepEqual(visible.pendingAlerts, []);
});

test('MED-01: al desmontar mientras hay peticiones pendientes no ejecuta cambios de estado', async () => {
  const detailTracker = createScopedRequestTracker();
  const alertsTracker = createScopedRequestTracker();
  const pendingDetail = createDeferred();
  const pendingAlerts = createDeferred();
  let stateMutations = 0;

  const visible = {
    detail: null,
    alerts: [],
    loading: true,
    error: '',
  };

  const pDetail = executeStudentDetailRequest({
    studentId: 'A',
    tracker: detailTracker,
    isSelectedStudent: () => true,
    fetchDetail: () => pendingDetail.promise,
    onSuccess: (d) => { stateMutations += 1; visible.detail = d; },
    onError: () => { stateMutations += 1; visible.error = 'err'; },
    onFinally: () => { stateMutations += 1; visible.loading = false; },
  });
  const pAlerts = executeStudentSafetyAlertsRequest({
    studentId: 'A',
    tracker: alertsTracker,
    isCurrentStudent: () => true,
    fetchAlerts: () => pendingAlerts.promise,
    onSuccess: (a) => { stateMutations += 1; visible.alerts = a; },
    onError: () => { stateMutations += 1; visible.error = 'err'; },
    onFinally: () => { stateMutations += 1; visible.loading = false; },
  });

  // Se desmonta el componente antes de que respondan las promesas.
  detailTracker.dispose();
  alertsTracker.dispose();

  pendingDetail.resolve({ profile: { id: 'A' } });
  pendingAlerts.reject(new Error('network error'));
  await Promise.all([pDetail, pAlerts]);

  assert.equal(stateMutations, 0);
  assert.equal(visible.detail, null);
  assert.deepEqual(visible.alerts, []);
  assert.equal(visible.error, '');
  assert.equal(visible.loading, true);
});

test('MED-02: cantidad exacta de solicitudes por transición evita recargas globales duplicadas al abrir/cerrar progreso', async () => {
  const globalTracker = createScopedRequestTracker();
  const studentTracker = createScopedRequestTracker();
  const students = [
    { relationship_id: 'rel-1', student_id: 'stu-1' },
    { relationship_id: 'rel-2', student_id: 'stu-2' },
  ];

  let globalCalls = 0;
  const studentCalls = [];
  const fetchPendingAlerts = async () => {
    globalCalls += 1;
    return [];
  };
  const loadStudentAlerts = (studentId) => executeStudentSafetyAlertsRequest({
    studentId,
    tracker: studentTracker,
    fetchAlerts: async (id) => {
      studentCalls.push(id);
      return [];
    },
    onSuccess: () => undefined,
  });

  // 1. Montaje inicial con safetyRefreshKey = 0 -> efecto safetyRefreshKey no dispara.
  await runSafetyRefreshTransition({
    safetyRefreshKey: 0,
    openRelationshipId: null,
    students,
    globalTracker,
    fetchPendingAlerts,
    onPendingSuccess: () => undefined,
    loadStudentAlerts,
  });
  assert.equal(globalCalls, 0);
  assert.deepEqual(studentCalls, []);

  // 2. Abrir panel de progreso del alumno 1 -> 0 globales, 1 carga individual ('stu-1').
  await runOpenProgressSafetyTransition({
    openRelationshipId: 'rel-1',
    students,
    loadStudentAlerts,
  });
  assert.equal(globalCalls, 0);
  assert.deepEqual(studentCalls, ['stu-1']);

  // 3. Cerrar panel de progreso -> 0 solicitudes.
  await runOpenProgressSafetyTransition({
    openRelationshipId: null,
    students,
    loadStudentAlerts,
  });
  assert.equal(globalCalls, 0);
  assert.deepEqual(studentCalls, ['stu-1']);

  // 4. Se revisa una alerta (safetyRefreshKey pasa a 1) con progreso cerrado -> 1 global, 0 alumno.
  await runSafetyRefreshTransition({
    safetyRefreshKey: 1,
    openRelationshipId: null,
    students,
    globalTracker,
    fetchPendingAlerts,
    onPendingSuccess: () => undefined,
    loadStudentAlerts,
  });
  assert.equal(globalCalls, 1);
  assert.deepEqual(studentCalls, ['stu-1']);

  // 5. Con safetyRefreshKey > 0, abrir y cerrar progreso de alumno 2 NO debe re-disparar alertas globales.
  await runOpenProgressSafetyTransition({
    openRelationshipId: 'rel-2',
    students,
    loadStudentAlerts,
  });
  await runOpenProgressSafetyTransition({
    openRelationshipId: null,
    students,
    loadStudentAlerts,
  });
  assert.equal(globalCalls, 1);
  assert.deepEqual(studentCalls, ['stu-1', 'stu-2']);

  // 6. Con alumno 2 abierto, incrementar safetyRefreshKey a 2 recarga 1 global + 1 de alumno 2.
  await runSafetyRefreshTransition({
    safetyRefreshKey: 2,
    openRelationshipId: 'rel-2',
    students,
    globalTracker,
    fetchPendingAlerts,
    onPendingSuccess: () => undefined,
    loadStudentAlerts,
  });
  assert.equal(globalCalls, 2);
  assert.deepEqual(studentCalls, ['stu-1', 'stu-2', 'stu-2']);

  // 7. Clic en badge de seguridad: si está cerrado solo abre (evita duplicado); si ya está abierto recarga una vez.
  let openRel = null;
  await focusSafetyAlertsTransition({
    student: students[0],
    openRelationshipId: openRel,
    setOpenProgressFor: (rel) => { openRel = rel; },
    loadStudentAlerts,
  });
  assert.equal(openRel, 'rel-1');
  assert.deepEqual(studentCalls, ['stu-1', 'stu-2', 'stu-2']);

  await focusSafetyAlertsTransition({
    student: students[0],
    openRelationshipId: 'rel-1',
    setOpenProgressFor: (rel) => { openRel = rel; },
    loadStudentAlerts,
  });
  assert.deepEqual(studentCalls, ['stu-1', 'stu-2', 'stu-2', 'stu-1']);
});

test('LOW-01: orden alfabético consistente por apellido y nombre en desempates y tercer nivel', () => {
  assert.equal(
    compareStudentNamesAlphabetically({ student_name: 'Zoe Alpha' }, { student_name: 'Alba Zeta' }) < 0,
    true,
  );
  assert.equal(
    compareStudentNamesAlphabetically({ student_name: 'Ana Alpha' }, { student_name: 'Zoe Alpha' }) < 0,
    true,
  );

  const list = [
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
  const ordered = sortAssignmentsByPriority(list, risks, []);
  assert.deepEqual(
    ordered.map((item) => item.relationship_id),
    ['dario-r', 'bruno-r', 'ana-a', 'zoe-a', 'alba-z'],
  );
});

test('LOW-02: resolvePainAlertHighlightId busca SafetyAlert(PAIN) por report_id sin confundirlo con alert.id', () => {
  const alerts = [
    { id: 'rep-pain-1', alert_type: 'REPEATED_DISCOMFORT', report_id: 'rep-other' },
    { id: 'sa-pain-99', alert_type: 'PAIN', report_id: 'rep-pain-1' },
  ];

  assert.equal(resolvePainAlertHighlightId(alerts, 'rep-pain-1'), 'sa-pain-99');
  assert.equal(resolvePainAlertHighlightId(alerts, 'missing-report'), null);
  assert.equal(resolvePainAlertHighlightId([], 'rep-pain-1'), null);
});

test('LOW-03: mientras se envía una revisión deshabilita los demás botones y bloquea envíos concurrentes', async () => {
  const idle1 = getReviewSubmitButtonState('alert-1', 'ADJUSTED_ROUTINE', null);
  const idle2 = getReviewSubmitButtonState('alert-2', 'CONTACTED_STUDENT', null);
  assert.deepEqual(idle1, { disabled: false, isSubmittingCurrent: false, label: 'Marcar como revisada' });
  assert.deepEqual(idle2, { disabled: false, isSubmittingCurrent: false, label: 'Marcar como revisada' });

  const inFlightGuard = { current: false };
  let mounted = true;
  const reviewDeferred = createDeferred();
  const apiCalls = [];
  let submittingId = null;
  const reviewed = [];
  const errors = {};

  const pFirst = executeAlertReviewSubmit({
    alertId: 'alert-1',
    actionTaken: 'ADJUSTED_ROUTINE',
    trainerNote: '  Reducir carga ',
    inFlightGuard,
    isMounted: () => mounted,
    reviewAlert: (alertId, payload) => {
      apiCalls.push({ alertId, payload });
      return reviewDeferred.promise;
    },
    setSubmittingId: (id) => { submittingId = id; },
    clearAlertError: (id) => { errors[id] = ''; },
    setAlertError: (id, msg) => { errors[id] = msg; },
    onReviewed: (item) => reviewed.push(item),
    onSuccessCleanup: () => undefined,
  });

  // Mientras alert-1 está en curso: botón 1 muestra carga y botón 2 también queda deshabilitado.
  assert.equal(submittingId, 'alert-1');
  assert.deepEqual(
    getReviewSubmitButtonState('alert-1', 'ADJUSTED_ROUTINE', submittingId),
    { disabled: true, isSubmittingCurrent: true, label: 'Guardando revisión…' },
  );
  assert.deepEqual(
    getReviewSubmitButtonState('alert-2', 'CONTACTED_STUDENT', submittingId),
    { disabled: true, isSubmittingCurrent: false, label: 'Marcar como revisada' },
  );

  // Intentar enviar alert-2 de forma concurrente queda bloqueado.
  const secondAllowed = await executeAlertReviewSubmit({
    alertId: 'alert-2',
    actionTaken: 'CONTACTED_STUDENT',
    trainerNote: '',
    inFlightGuard,
    isMounted: () => mounted,
    reviewAlert: (alertId, payload) => {
      apiCalls.push({ alertId, payload });
      return Promise.resolve({ id: alertId });
    },
    setSubmittingId: (id) => { submittingId = id; },
    clearAlertError: () => undefined,
    setAlertError: () => undefined,
    onReviewed: () => undefined,
    onSuccessCleanup: () => undefined,
  });
  assert.equal(secondAllowed, false);
  assert.equal(apiCalls.length, 1);

  reviewDeferred.resolve({ id: 'alert-1', status: 'REVIEWED', action_taken: 'ADJUSTED_ROUTINE' });
  const firstCompleted = await pFirst;
  assert.equal(firstCompleted, true);
  assert.equal(submittingId, null);
  assert.equal(reviewed.length, 1);

  // Verificar guardia post-desmontaje en executeAlertReviewSubmit.
  const postUnmountDeferred = createDeferred();
  let postUnmountMutations = 0;
  const pThird = executeAlertReviewSubmit({
    alertId: 'alert-2',
    actionTaken: 'NO_ACTION',
    inFlightGuard,
    isMounted: () => mounted,
    reviewAlert: () => postUnmountDeferred.promise,
    setSubmittingId: (id) => {
      submittingId = id;
      if (id === null) postUnmountMutations += 1;
    },
    clearAlertError: () => undefined,
    setAlertError: () => { postUnmountMutations += 1; },
    onReviewed: () => { postUnmountMutations += 1; },
    onSuccessCleanup: () => { postUnmountMutations += 1; },
  });
  mounted = false;
  postUnmountDeferred.resolve({ id: 'alert-2', status: 'REVIEWED' });
  const thirdCompleted = await pThird;
  assert.equal(thirdCompleted, false);
  assert.equal(postUnmountMutations, 0);
});
