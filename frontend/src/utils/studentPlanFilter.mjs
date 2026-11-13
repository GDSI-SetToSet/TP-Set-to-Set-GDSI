export const ALL_PLANS = '';

function compareTitles(a, b) {
  return a.title.localeCompare(b.title, 'es-AR', { sensitivity: 'base' });
}

/**
 * Arma las opciones del filtro por paquete (US-20): los paquetes vigentes del
 * entrenador más cualquier paquete que tenga contratado un alumno activo
 * (por ejemplo, un paquete archivado), con la cantidad de cupos ocupados.
 */
export function buildPlanFilterOptions(students, plans = []) {
  const options = new Map();

  for (const plan of plans) {
    if (plan.is_active) options.set(plan.id, { plan_id: plan.id, title: plan.title, student_count: 0 });
  }

  for (const student of students) {
    if (!student.plan_id) continue;
    const option = options.get(student.plan_id)
      ?? { plan_id: student.plan_id, title: student.plan_title || 'Paquete sin nombre', student_count: 0 };
    option.student_count += 1;
    options.set(student.plan_id, option);
  }

  return [...options.values()].sort(compareTitles);
}

/** El filtro solo tiene sentido con más de un paquete registrado. */
export function canFilterByPlan(options) {
  return options.length > 1;
}

export function filterStudentsByPlan(students, planId) {
  if (!planId) return students;
  return students.filter((student) => student.plan_id === planId);
}
