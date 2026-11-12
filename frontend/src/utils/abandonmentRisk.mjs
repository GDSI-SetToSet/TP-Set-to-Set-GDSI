/** US-32: los alumnos con riesgo de abandono se muestran primero, manteniendo el orden original entre pares. */
export function sortByAbandonmentRisk(students, risks) {
  const riskByRelationship = new Map(risks.map((risk) => [risk.relationship_id, risk]));
  return students
    .map((student, index) => ({ student, index, risk: riskByRelationship.get(student.relationship_id) }))
    .sort((a, b) => Number(Boolean(b.risk?.at_risk)) - Number(Boolean(a.risk?.at_risk))
      || (a.risk?.at_risk ? (b.risk.days_without_report - a.risk.days_without_report) : 0)
      || a.index - b.index)
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
