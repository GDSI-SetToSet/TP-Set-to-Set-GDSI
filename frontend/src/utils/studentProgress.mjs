// Frases de "Mi evolución": informan y motivan, nunca diagnostican (sin "estancado", "bajó" ni porcentajes).
import { formatNumber } from './trainingEvolution.mjs';

export const PERIOD_LABELS = { '4w': '4 semanas', '12w': '12 semanas', all: 'Todo' };
export const PROGRESS_HELP =
  'Progresar no es solo levantar más peso. También cuenta hacer más repeticiones con el mismo peso. Que una semana no haya mejora es normal: tu entrenador ajusta la rutina para que sigas avanzando.';
const IMPROVED = ['weight_increased', 'reps_increased', 'bodyweight_reps_increased'];

export const kg = (value) => `${formatNumber(value)} kg`;
export const weeksText = (n) => `${n} ${n === 1 ? 'semana' : 'semanas'}`;
const reps = (value) => `${value} ${value === 1 ? 'repetición' : 'repeticiones'}`;
const weeks = (n) => (n < 1 ? 'esta semana' : `hace ${n} ${n === 1 ? 'semana' : 'semanas'}`);
const bodyweight = (e) => e.metric === 'max_reps';

/** Mejor serie: '40 kg × 8' o, sin carga, '9 repeticiones'. */
export function formatMark(set) {
  if (!set) return '—';
  return set.weight ? `${kg(set.weight)} × ${set.reps}` : reps(set.reps);
}

/** Frase de una fila de la lista de ejercicios (sin el nombre). */
export function exercisePhrase(e) {
  const { start, current, best } = e;
  switch (e.message_key) {
    case 'weight_increased':
      return `subiste de ${kg(start.weight)} a ${kg(current.weight)}${e.last_improvement_is_pr ? ' 🏆' : ''}`;
    case 'reps_increased':
      return `mismo peso (${kg(current.weight)}), pero ahora hacés ${current.reps} repeticiones en lugar de ${start.reps}${e.last_improvement_is_pr ? ' 🏆' : ''}`;
    case 'bodyweight_reps_increased':
      return `pasaste de ${start.reps} a ${reps(current.reps)}${e.last_improvement_is_pr ? ' 🏆' : ''}`;
    case 'below_best':
      return bodyweight(e)
        ? `tu última sesión fue de ${reps(current.reps)}; tu mejor marca es ${reps(best.reps)}`
        : `tu última sesión fue con ${kg(current.weight)}; tu mejor marca es ${kg(best.weight)}`;
    case 'few_data': {
      const n = e.points.length;
      return `lo hiciste ${n} ${n === 1 ? 'vez' : 'veces'}. Con la próxima sesión vas a ver tu progreso`;
    }
    default:
      return `venís sosteniendo ${bodyweight(e) ? reps(current.reps) : kg(current.weight)} ${weeks(e.weeks_without_change)}`;
  }
}

/** Primero las mejoras y después el resto, por nombre (el backend ya ordena así; sirve de red de seguridad). */
export function sortExercises(list) {
  return [...list].sort((a, b) => Number(!IMPROVED.includes(a.message_key)) - Number(!IMPROVED.includes(b.message_key)) || a.name.localeCompare(b.name, 'es'));
}

/** Semanas completas (la en curso no cuenta). */
const full = (weeksList) => weeksList.filter((w) => !w.is_partial);

export function consistencyLine(weeksList) {
  const done = full(weeksList);
  const scheduled = done.reduce((sum, w) => sum + w.scheduled, 0);
  const completed = done.reduce((sum, w) => sum + Math.min(w.completed, w.scheduled), 0);
  if (!scheduled) return null;
  return `Entrenaste ${completed} de las ${scheduled} sesiones acordadas${completed === scheduled ? '' : '. ¡Cada sesión suma!'}`;
}

export const isWeekDone = (w) => !w.is_partial && w.scheduled > 0 && w.completed >= w.scheduled;
export const currentWeekLabel = (w) => `En curso: ${w.completed} de ${w.scheduled}`;

/** Tarjetas del encabezado: con 0, una frase de aliento en lugar del número. */
export function summaryCards(summary) {
  const { improving_exercises_last_4w: improving, streak, records_in_period: records } = summary;
  return [
    { id: 'mejorando', title: 'Mejorando', text: improving ? `${improving} ${improving === 1 ? 'ejercicio con mejoras' : 'ejercicios con mejoras'} este mes` : 'Cada sesión suma' },
    { id: 'constante', title: 'Constancia', text: streak.current_weeks ? `Racha: ${weeksText(streak.current_weeks)}` : 'Tu próxima racha empieza con una sesión' },
    { id: 'logros', title: 'Récords', text: records ? `${records} ${records === 1 ? 'récord' : 'récords'} en el período` : 'Tu primer récord está cerca' },
  ];
}

export function recordLine(record) {
  return `${formatMark({ weight: record.weight, reps: record.reps })} (antes ${formatMark(record.previous)})`;
}

/** Sin récords: la marca a superar del ejercicio con la sesión más reciente. */
export function markToBeat(exercises) {
  const latest = [...exercises].sort((a, b) => b.points.at(-1).date.localeCompare(a.points.at(-1).date) || a.name.localeCompare(b.name, 'es'))[0];
  return latest ? { name: latest.name, mark: formatMark(latest.best) } : null;
}
