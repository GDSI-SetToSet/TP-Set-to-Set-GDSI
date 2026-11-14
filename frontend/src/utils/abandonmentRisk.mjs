import { compareStudentNamesAlphabetically, groupPendingAlertsByRelationship } from './safetyAlerts.mjs';

/** US-29 + US-32: alumnos con alertas de seguridad pendientes primero, luego riesgo de abandono, desempatando alfabéticamente por nombre completo. */
export function sortByAbandonmentRisk(students, risks, safetyAlerts = []) {
  const riskByRelationship = new Map(risks.map((risk) => [risk.relationship_id, risk]));
  const alertsByRelationship = groupPendingAlertsByRelationship(safetyAlerts);
  return students
    .map((student, index) => {
      const pendingInfo = alertsByRelationship.get(student.relationship_id);
      const risk = riskByRelationship.get(student.relationship_id);
      return {
        student,
        index,
        pendingCount: pendingInfo?.count ?? 0,
        latestAlertMs: pendingInfo?.latestCreatedAtMs ?? 0,
        risk,
      };
    })
    .sort((a, b) => {
      const tierA = a.pendingCount > 0 ? 0 : a.risk?.at_risk ? 1 : 2;
      const tierB = b.pendingCount > 0 ? 0 : b.risk?.at_risk ? 1 : 2;
      if (tierA !== tierB) return tierA - tierB;
      if (tierA === 0) {
        return (b.pendingCount - a.pendingCount)
          || (b.latestAlertMs - a.latestAlertMs)
          || (Number(Boolean(b.risk?.at_risk)) - Number(Boolean(a.risk?.at_risk)))
          || ((b.risk?.days_without_report ?? 0) - (a.risk?.days_without_report ?? 0))
          || compareStudentNamesAlphabetically(a.student, b.student)
          || a.index - b.index;
      }
      if (tierA === 1) {
        return ((b.risk?.days_without_report ?? 0) - (a.risk?.days_without_report ?? 0))
          || compareStudentNamesAlphabetically(a.student, b.student)
          || a.index - b.index;
      }
      return compareStudentNamesAlphabetically(a.student, b.student) || a.index - b.index;
    })
    .map(({ student }) => student);
}

export function abandonmentRiskDescription(risk) {
  if (!risk?.at_risk) return '';
  if (risk.reason === 'MISSED_TRAININGS') {
    return `Lleva ${risk.missed_trainings} entrenamientos sin reportar.`;
  }
  return risk.last_report_at
    ? `No reporta entrenamientos hace ${risk.days_without_report} días.`
    : `No reportó ningún entrenamiento en ${risk.days_without_report} días.`;
}
