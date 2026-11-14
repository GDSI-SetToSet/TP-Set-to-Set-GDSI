export const SAFETY_ALERT_TYPE_LABELS = {
  PAIN: 'Dolor reportado',
  REPEATED_DISCOMFORT: 'Molestia repetida',
  EXCESSIVE_EFFORT: 'Esfuerzo excesivo',
};

export const SAFETY_ALERT_ACTION_OPTIONS = [
  { value: 'ADJUSTED_ROUTINE', label: 'Ajusté la rutina' },
  { value: 'CONTACTED_STUDENT', label: 'Contacté al alumno' },
  { value: 'NO_ACTION', label: 'Sin acción' },
];

export const SAFETY_ALERT_ACTION_LABELS = Object.fromEntries(
  SAFETY_ALERT_ACTION_OPTIONS.map((option) => [option.value, option.label]),
);

function timestampMs(value) {
  if (!value) return 0;
  const parsed = Date.parse(value);
  return Number.isNaN(parsed) ? 0 : parsed;
}

function compareAlphabetically(leftName, rightName) {
  return String(leftName || '').localeCompare(String(rightName || ''), 'es', {
    sensitivity: 'base',
  });
}

function extractStudentSortParts(student) {
  if (student && typeof student === 'object' && ('last_name' in student || 'first_name' in student)) {
    const firstName = String(student.first_name ?? '').trim();
    const lastName = String(student.last_name ?? '').trim();
    const fullName = String(student.student_name ?? student.full_name ?? `${firstName} ${lastName}`).trim();
    return { lastName, firstName, fullName };
  }
  const rawName = (
    typeof student === 'string'
      ? student
      : String(student?.student_name ?? student?.full_name ?? '')
  ).trim();
  if (!rawName || rawName.includes('@')) {
    return { lastName: rawName, firstName: '', fullName: rawName };
  }
  const parts = rawName.split(/\s+/);
  if (parts.length > 1) {
    return {
      lastName: parts.slice(1).join(' '),
      firstName: parts[0],
      fullName: rawName,
    };
  }
  return { lastName: parts[0] ?? '', firstName: '', fullName: rawName };
}

export function compareStudentNamesAlphabetically(leftStudent, rightStudent) {
  const left = extractStudentSortParts(leftStudent);
  const right = extractStudentSortParts(rightStudent);
  return (
    compareAlphabetically(left.lastName, right.lastName)
    || compareAlphabetically(left.firstName, right.firstName)
    || compareAlphabetically(left.fullName, right.fullName)
  );
}

/**
 * MED-01: coordina peticiones asíncronas con identificador monotónico y cancelación al desmontar
 * para evitar que respuestas obsoletas o post-desmontaje sobrescriban el estado visible.
 */
export function createScopedRequestTracker() {
  let disposed = false;
  let sequence = 0;
  const latestByScope = new Map();

  return {
    begin(scopeKey = 'default') {
      sequence += 1;
      const requestId = sequence;
      latestByScope.set(scopeKey, requestId);
      return {
        requestId,
        scopeKey,
        isCurrent(expectedScopeKey = scopeKey) {
          return !disposed
            && expectedScopeKey === scopeKey
            && latestByScope.get(scopeKey) === requestId;
        },
      };
    },
    invalidate(scopeKey = 'default') {
      sequence += 1;
      latestByScope.set(scopeKey, sequence);
    },
    isActive() {
      return !disposed;
    },
    dispose() {
      disposed = true;
      latestByScope.clear();
    },
  };
}

export function executeStudentDetailRequest({
  studentId,
  tracker,
  isSelectedStudent,
  fetchDetail,
  onSuccess,
  onError,
  onFinally,
}) {
  const req = tracker.begin('detail');
  const canApply = () => req.isCurrent() && (!isSelectedStudent || isSelectedStudent(studentId));
  return Promise.resolve()
    .then(() => fetchDetail(studentId))
    .then((detail) => {
      if (!canApply()) return;
      onSuccess(detail);
    })
    .catch((err) => {
      if (!canApply()) return;
      onError?.(err);
    })
    .finally(() => {
      if (!canApply()) return;
      onFinally?.();
    });
}

export function executeStudentSafetyAlertsRequest({
  studentId,
  tracker,
  isCurrentStudent,
  fetchAlerts,
  onSuccess,
  onError,
  onFinally,
}) {
  const req = tracker.begin(studentId);
  const canApply = () => req.isCurrent(studentId) && (!isCurrentStudent || isCurrentStudent(studentId));
  return Promise.resolve()
    .then(() => fetchAlerts(studentId))
    .then((items) => {
      if (!canApply()) return;
      onSuccess(items);
    })
    .catch((err) => {
      if (!canApply()) return;
      onError?.(err);
    })
    .finally(() => {
      if (!canApply()) return;
      onFinally?.();
    });
}

export function runSafetyRefreshTransition({
  safetyRefreshKey,
  openRelationshipId,
  students,
  globalTracker,
  fetchPendingAlerts,
  onPendingSuccess,
  onPendingError,
  loadStudentAlerts,
}) {
  if (!safetyRefreshKey) return Promise.resolve();
  const globalReq = globalTracker.begin('global-pending');
  const pendingPromise = Promise.resolve()
    .then(() => fetchPendingAlerts())
    .then((alerts) => {
      if (!globalReq.isCurrent()) return;
      onPendingSuccess(alerts);
    })
    .catch((err) => {
      if (!globalReq.isCurrent()) return;
      onPendingError?.(err);
    });

  let studentPromise = Promise.resolve();
  if (openRelationshipId) {
    const openStudent = students.find((item) => item.relationship_id === openRelationshipId);
    if (openStudent) {
      studentPromise = Promise.resolve(loadStudentAlerts(openStudent.student_id));
    }
  }
  return Promise.all([pendingPromise, studentPromise]);
}

export function runOpenProgressSafetyTransition({
  openRelationshipId,
  students,
  loadStudentAlerts,
}) {
  if (!openRelationshipId) return Promise.resolve();
  const openStudent = students.find((item) => item.relationship_id === openRelationshipId);
  if (!openStudent) return Promise.resolve();
  return Promise.resolve(loadStudentAlerts(openStudent.student_id));
}

export function focusSafetyAlertsTransition({
  student,
  openRelationshipId,
  setOpenProgressFor,
  loadStudentAlerts,
}) {
  if (openRelationshipId === student.relationship_id) {
    return Promise.resolve(loadStudentAlerts(student.student_id));
  }
  setOpenProgressFor(student.relationship_id);
  return Promise.resolve();
}

export function resolvePainAlertHighlightId(alerts = [], reportId = null) {
  if (!reportId || !Array.isArray(alerts)) return null;
  const match = alerts.find(
    (alert) => alert && alert.alert_type === 'PAIN' && alert.report_id === reportId,
  );
  return match ? match.id : null;
}

export function getReviewSubmitButtonState(alertId, selectedAction, submittingId) {
  const isSubmittingCurrent = Boolean(submittingId) && submittingId === alertId;
  return {
    disabled: !selectedAction || Boolean(submittingId),
    isSubmittingCurrent,
    label: isSubmittingCurrent ? 'Guardando revisión…' : 'Marcar como revisada',
  };
}

export async function executeAlertReviewSubmit({
  alertId,
  actionTaken,
  trainerNote,
  inFlightGuard,
  isMounted,
  reviewAlert,
  setSubmittingId,
  clearAlertError,
  setAlertError,
  onReviewed,
  onSuccessCleanup,
}) {
  if (!actionTaken || inFlightGuard.current) return false;
  inFlightGuard.current = true;
  setSubmittingId(alertId);
  clearAlertError(alertId);
  try {
    const trimmedNote = (trainerNote ?? '').trim();
    const updated = await reviewAlert(alertId, {
      action_taken: actionTaken,
      trainer_note: trimmedNote || null,
    });
    if (!isMounted()) return false;
    onReviewed(updated);
    onSuccessCleanup(alertId);
    return true;
  } catch {
    if (isMounted()) {
      setAlertError(alertId, 'No pudimos guardar la revisión de esta alerta. Intentá nuevamente.');
    }
    return false;
  } finally {
    inFlightGuard.current = false;
    if (isMounted()) {
      setSubmittingId(null);
    }
  }
}

export function groupPendingAlertsByRelationship(alerts = []) {
  const grouped = new Map();
  alerts.forEach((alert) => {
    if (!alert || alert.status !== 'PENDING' || !alert.relationship_id) return;
    const current = grouped.get(alert.relationship_id) ?? {
      count: 0,
      latestCreatedAtMs: 0,
      alerts: [],
    };
    current.count += 1;
    current.latestCreatedAtMs = Math.max(current.latestCreatedAtMs, timestampMs(alert.created_at));
    current.alerts.push(alert);
    grouped.set(alert.relationship_id, current);
  });
  return grouped;
}

/**
 * US-29 (Decisión A):
 * (1) Alumnos con alertas PENDING de US-29 primero (mayor cantidad, más reciente, riesgo, alfabético);
 * (2) Alumnos con riesgo de abandono (US-32) después (conservando su cálculo/orden);
 * (3) Demás alumnos alfabéticamente.
 */
export function sortAssignmentsByPriority(
  students = [],
  abandonmentRisks = [],
  pendingAlerts = [],
) {
  const riskByRelationship = new Map(
    abandonmentRisks.map((risk) => [risk.relationship_id, risk]),
  );
  const alertsByRelationship = groupPendingAlertsByRelationship(pendingAlerts);

  return students
    .map((student, index) => {
      const pendingInfo = alertsByRelationship.get(student.relationship_id);
      const risk = riskByRelationship.get(student.relationship_id);
      const pendingCount = pendingInfo?.count ?? 0;
      const hasRisk = Boolean(risk?.at_risk);
      const tier = pendingCount > 0 ? 0 : hasRisk ? 1 : 2;
      return {
        student,
        index,
        tier,
        pendingCount,
        latestCreatedAtMs: pendingInfo?.latestCreatedAtMs ?? 0,
        hasRisk,
        daysWithoutReport: risk?.days_without_report ?? 0,
      };
    })
    .sort((a, b) => {
      if (a.tier !== b.tier) return a.tier - b.tier;
      if (a.tier === 0) {
        return (
          b.pendingCount - a.pendingCount
          || b.latestCreatedAtMs - a.latestCreatedAtMs
          || Number(b.hasRisk) - Number(a.hasRisk)
          || b.daysWithoutReport - a.daysWithoutReport
          || compareStudentNamesAlphabetically(a.student, b.student)
          || a.index - b.index
        );
      }
      if (a.tier === 1) {
        return (
          b.daysWithoutReport - a.daysWithoutReport
          || compareStudentNamesAlphabetically(a.student, b.student)
          || a.index - b.index
        );
      }
      return compareStudentNamesAlphabetically(a.student, b.student) || a.index - b.index;
    })
    .map(({ student }) => student);
}

export function formatSafetyAlertSummary(alert) {
  if (!alert) {
    return {
      typeLabel: '',
      detailText: '',
      statusLabel: '',
      actionLabel: '',
      note: null,
    };
  }

  const typeLabel = SAFETY_ALERT_TYPE_LABELS[alert.alert_type] ?? alert.alert_type;
  const parts = [];
  if (alert.alert_type === 'EXCESSIVE_EFFORT') {
    if (alert.rpe !== null && alert.rpe !== undefined) {
      parts.push(`RPE ${alert.rpe}/10`);
    }
  } else {
    const zoneLabel = alert.zone_display_name || alert.zone;
    if (zoneLabel) parts.push(zoneLabel);
    if (alert.alert_type === 'REPEATED_DISCOMFORT') {
      parts.push('2 sesiones consecutivas');
    }
    if (alert.exercise_name) parts.push(alert.exercise_name);
  }
  if (alert.session_day_name) parts.push(alert.session_day_name);

  const trimmedNote = typeof alert.trainer_note === 'string'
    ? alert.trainer_note.trim() || null
    : null;

  return {
    typeLabel,
    detailText: parts.join(' · '),
    statusLabel: alert.status === 'REVIEWED' ? 'Revisada' : 'Pendiente',
    actionLabel: alert.action_taken
      ? (SAFETY_ALERT_ACTION_LABELS[alert.action_taken] ?? alert.action_taken)
      : '',
    note: trimmedNote,
  };
}

/**
 * CA-5: formatea avisos al alumno exclusivamente de alertas de dolor (PAIN) revisadas.
 */
export function formatStudentPainReviewedNotice(notice) {
  if (!notice) return null;
  if ('alert_type' in notice && notice.alert_type && notice.alert_type !== 'PAIN') {
    return null;
  }
  const zoneLabel = notice.zone_display_name || notice.zone;
  const contextParts = [];
  if (zoneLabel) contextParts.push(`Zona: ${zoneLabel}`);
  if (notice.exercise_name) contextParts.push(notice.exercise_name);
  if (notice.session_day_name) contextParts.push(notice.session_day_name);

  const trainerNote = typeof notice.trainer_note === 'string'
    ? notice.trainer_note.trim() || null
    : null;

  return {
    id: notice.id,
    title: 'Tu entrenador revisó tu reporte de dolor',
    contextText: contextParts.join(' · '),
    actionLabel: SAFETY_ALERT_ACTION_LABELS[notice.action_taken] ?? notice.action_taken,
    trainerNote,
    reviewedAt: notice.reviewed_at,
  };
}
