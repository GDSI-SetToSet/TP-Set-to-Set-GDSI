export const LOAD_STUDENTS_ERROR = 'No pudimos cargar tus alumnos activos. Intentá nuevamente.';
export const LOAD_PLANS_ERROR = 'No pudimos cargar todos tus paquetes contratados; el filtro por paquete puede estar incompleto.';
export const LOAD_RISK_ERROR = 'No pudimos comprobar el riesgo de abandono de tus alumnos; el orden prioritario y las alertas pueden estar incompletos.';

export function resolveAssignmentLoadResults(studentsResult, plansResult, risksResult) {
  return {
    students: studentsResult.status === 'fulfilled' ? studentsResult.value : null,
    error: studentsResult.status === 'rejected' ? LOAD_STUDENTS_ERROR : '',
    trainerPlans: plansResult.status === 'fulfilled' ? plansResult.value : [],
    plansError: plansResult.status === 'rejected' ? LOAD_PLANS_ERROR : '',
    abandonmentRisks: risksResult.status === 'fulfilled' ? risksResult.value : [],
    riskError: risksResult.status === 'rejected' ? LOAD_RISK_ERROR : '',
  };
}

export function applyAuxiliaryRetry(currentState, plansResult, risksResult) {
  const next = { ...currentState };
  if (plansResult) {
    if (plansResult.status === 'fulfilled') {
      next.trainerPlans = plansResult.value;
      next.plansError = '';
    } else {
      next.plansError = LOAD_PLANS_ERROR;
    }
  }
  if (risksResult) {
    if (risksResult.status === 'fulfilled') {
      next.abandonmentRisks = risksResult.value;
      next.riskError = '';
    } else {
      next.riskError = LOAD_RISK_ERROR;
    }
  }
  return next;
}
