import assert from 'node:assert/strict';
import test from 'node:test';
import { consistencyLine, exercisePhrase, markToBeat, recordLine, sortExercises, summaryCards } from './studentProgress.mjs';

const ex = (name, message_key, extra = {}) => ({
  name, message_key, metric: 'max_weight', weeks_without_change: 0, last_improvement_is_pr: false,
  start: { weight: 22.5, reps: 8 }, current: { weight: 40, reps: 8 }, best: { weight: 50, reps: 8 },
  points: [{ date: '2026-11-07' }], ...extra,
});
const KEYS = ['weight_increased', 'reps_increased', 'no_change', 'below_best', 'bodyweight_reps_increased', 'few_data'];

test('cada message_key da su frase y ninguna usa palabras de alerta ni porcentajes', () => {
  const phrases = KEYS.flatMap((key) => [exercisePhrase(ex('A', key, { last_improvement_is_pr: true })), exercisePhrase(ex('A', key, { metric: 'max_reps', weeks_without_change: 3 }))]);
  for (const phrase of phrases) assert.doesNotMatch(phrase, /estancad|baj[oó]|fallaste|abandono|%|undefined|null|NaN/i);
  assert.equal(exercisePhrase(ex('A', 'weight_increased', { last_improvement_is_pr: true })), 'subiste de 22,5 kg a 40 kg 🏆');
  assert.equal(exercisePhrase(ex('A', 'no_change', { weeks_without_change: 3 })), 'venís sosteniendo 40 kg hace 3 semanas');
  assert.equal(exercisePhrase(ex('A', 'below_best')), 'tu última sesión fue con 40 kg; tu mejor marca es 50 kg');
  assert.equal(exercisePhrase(ex('A', 'bodyweight_reps_increased', { start: { weight: null, reps: 6 }, current: { weight: null, reps: 9 } })), 'pasaste de 6 a 9 repeticiones');
});

test('las mejoras van primero y el resto por nombre', () => {
  const names = sortExercises([ex('Zeta', 'no_change'), ex('Beta', 'few_data'), ex('Omega', 'weight_increased'), ex('Alfa', 'reps_increased')]).map((e) => e.name);
  assert.deepEqual(names, ['Alfa', 'Omega', 'Beta', 'Zeta']);
});

test('constancia ignora la semana en curso', () => {
  const week = (completed, is_partial = false) => ({ scheduled: 4, completed, is_partial });
  assert.equal(consistencyLine([week(4), week(4), week(1, true)]), 'Entrenaste 8 de las 8 sesiones acordadas');
  assert.equal(consistencyLine([week(4), week(0)]), 'Entrenaste 4 de las 8 sesiones acordadas. ¡Cada sesión suma!');
  assert.equal(consistencyLine([week(1, true)]), null);
});

test('encabezado: aliento con 0 y récord con marca anterior', () => {
  const cards = summaryCards({ improving_exercises_last_4w: 0, streak: { current_weeks: 0, best_weeks: 0 }, records_in_period: 0 });
  assert.equal(cards[2].text, 'Tu primer récord está cerca');
  assert.equal(summaryCards({ improving_exercises_last_4w: 4, streak: { current_weeks: 6, best_weeks: 8 }, records_in_period: 3 })[1].text, 'Racha: 6 semanas');
  assert.equal(recordLine({ weight: 40, reps: 8, previous: { weight: 35, reps: 8 } }), '40 kg × 8 (antes 35 kg × 8)');
  assert.deepEqual(markToBeat([ex('Sentadilla', 'few_data')]), { name: 'Sentadilla', mark: '50 kg × 8' });
  assert.equal(markToBeat([]), null);
});
