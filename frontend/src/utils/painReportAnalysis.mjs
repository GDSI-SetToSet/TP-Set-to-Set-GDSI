export const PAIN_GROUPINGS = {
  zone: 'Zona corporal',
  muscle_group: 'Grupo muscular',
  exercise: 'Ejercicio',
  routine_day: 'Día de rutina',
};

const NO_EXERCISE = 'Reporte post-sesión (sin ejercicio)';
const NO_DAY = 'Sin sesión asociada';

/** Solo interesan las zonas con molestia o dolor; NORMAL no es un reporte de malestar. */
export function painOnly(items) {
  return items.filter((item) => item.intensity === 'DISCOMFORT' || item.intensity === 'PAIN');
}

function groupLabel(item, grouping) {
  switch (grouping) {
    case 'muscle_group':
      return item.exercise_muscle_group || NO_EXERCISE;
    case 'exercise':
      return item.exercise_name || NO_EXERCISE;
    case 'routine_day':
      return item.session_day_name || NO_DAY;
    default:
      return item.zone_display || item.zone;
  }
}

/** Cuenta molestias y dolores por grupo; ordena por dolor, luego total y nombre. */
export function aggregatePain(items, grouping = 'zone') {
  const groups = new Map();
  for (const item of painOnly(items)) {
    const label = groupLabel(item, grouping);
    const group = groups.get(label) ?? { label, discomfort: 0, pain: 0, total: 0 };
    if (item.intensity === 'PAIN') group.pain += 1;
    else group.discomfort += 1;
    group.total += 1;
    groups.set(label, group);
  }
  return [...groups.values()].sort((a, b) => b.pain - a.pain
    || b.total - a.total
    || a.label.localeCompare(b.label, 'es-AR'));
}

/** Agrupa las zonas por reporte para listarlos con su ejercicio/rutina (más recientes primero). */
export function groupByReport(items) {
  const reports = new Map();
  for (const item of painOnly(items)) {
    const report = reports.get(item.report_id) ?? {
      report_id: item.report_id,
      created_at: item.created_at,
      context: item.context,
      exercise_name: item.exercise_name,
      exercise_muscle_group: item.exercise_muscle_group ?? null,
      session_day_name: item.session_day_name,
      zones: [],
    };
    report.zones.push({ zone: item.zone, zone_display: item.zone_display, intensity: item.intensity });
    reports.set(item.report_id, report);
  }
  return [...reports.values()]
    .map((report) => ({
      ...report,
      zones: report.zones.sort((a, b) => (a.intensity === b.intensity ? a.zone_display.localeCompare(b.zone_display, 'es-AR') : a.intensity === 'PAIN' ? -1 : 1)),
    }))
    .sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at));
}
