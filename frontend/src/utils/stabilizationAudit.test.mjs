import assert from 'node:assert/strict';
import test from 'node:test';
import { resolveDialogTabTarget } from './dialogFocus.mjs';
import { formatNotificationTime, parseUtcIsoTimestamp } from './notificationFormat.mjs';
import {
  canStartExerciseSet,
  formatPersonalRecordMark,
  formatPersonalRecordPreviousMark,
  resolveEffectiveExercise,
  resolveRoutineAccessState,
  resolveWorkoutHistoryRoutineId,
  shouldClearPersonalRecordAlert,
} from '../pages/studentRoutineSessionState.mjs';

test('AUD-21: Shift+Tab inside a leading radio group wraps to last element', () => {
  const items = [
    { isRadio: true, name: 'reason', checked: false },
    { isRadio: true, name: 'reason', checked: true },
    { isRadio: true, name: 'reason', checked: false },
    { isRadio: false },
    { isRadio: false },
  ];
  assert.equal(resolveDialogTabTarget(items, 1, true), 4);
  assert.equal(resolveDialogTabTarget(items, 2, true), 4);
  assert.equal(resolveDialogTabTarget(items, 3, true), null);
  assert.equal(resolveDialogTabTarget(items, 4, false), 1);
});

test('AUD-21: Tab from a trailing radio group wraps to first focusable item', () => {
  const items = [
    { isRadio: false },
    { isRadio: true, name: 'choice', checked: false },
    { isRadio: true, name: 'choice', checked: true },
  ];
  assert.equal(resolveDialogTabTarget(items, 1, false), 0);
  assert.equal(resolveDialogTabTarget(items, 2, false), 0);
  assert.equal(resolveDialogTabTarget(items, 0, true), 2);
});

test('AUD-24: parseUtcIsoTimestamp treats naive ISO timestamps as UTC', () => {
  const naive = parseUtcIsoTimestamp('2026-11-20T15:30:00');
  const explicitZ = parseUtcIsoTimestamp('2026-11-20T15:30:00Z');
  assert.equal(naive.getTime(), explicitZ.getTime());
  assert.equal(
    parseUtcIsoTimestamp('2026-11-20T12:30:00-03:00').getTime(),
    explicitZ.getTime(),
  );
  assert.equal(formatNotificationTime('invalid-date'), 'invalid-date');
});

test('AUD-01/02: routine access state is fail-closed and preserves workout history routine ID', () => {
  assert.equal(
    resolveRoutineAccessState({ routineStatusCode: 409, subscription: null, subscriptionError: false }),
    'EXPIRED',
  );
  assert.equal(
    resolveRoutineAccessState({ routineStatusCode: null, subscription: { status: 'VENCIDA' }, subscriptionError: false }),
    'EXPIRED',
  );
  assert.equal(
    resolveRoutineAccessState({ routineStatusCode: null, subscription: null, subscriptionError: true }),
    'UNVERIFIED',
  );
  assert.equal(
    resolveRoutineAccessState({ routineStatusCode: null, subscription: { status: 'AL_DIA' }, subscriptionError: false }),
    'OK',
  );
  assert.equal(
    resolveWorkoutHistoryRoutineId(
      null,
      [{ routine_id: 'r-finished', finished_at: '2026-11-20T10:00:00Z' }],
      [{ routine_id: 'r-log' }],
    ),
    'r-finished',
  );
});

test('AUD-06/19: set start stays blocked fail-closed until notes load cleanly and uses replacement ID', () => {
  const item = { id: 'item-1', exercise: { id: 'orig-ex', name: 'Sentadilla' } };
  const replacements = { 'item-1': { exercise_id: 'alt-ex', name: 'Prensa' } };
  assert.deepEqual(resolveEffectiveExercise(item, replacements), { id: 'alt-ex', name: 'Prensa' });
  assert.deepEqual(resolveEffectiveExercise(item, {}), { id: 'orig-ex', name: 'Sentadilla' });

  const base = {
    sessionMode: true,
    notesLoaded: true,
    notesError: false,
    pendingNotesCount: 0,
    blocked: false,
    activeSet: null,
    finishedSet: null,
    activeRest: null,
  };
  assert.equal(canStartExerciseSet(base), true);
  assert.equal(canStartExerciseSet({ ...base, notesLoaded: false }), false);
  assert.equal(canStartExerciseSet({ ...base, notesError: true }), false);
  assert.equal(canStartExerciseSet({ ...base, pendingNotesCount: 1 }), false);
  assert.equal(canStartExerciseSet({ ...base, blocked: true }), false);
});

test('AUD-08: deleting a PR set log clears matching PR alerts and celebrations', () => {
  const alert = { logId: 'log-2', exerciseId: 'ex-1', sessionId: 'sess-2', dayName: 'Día 1' };
  assert.equal(shouldClearPersonalRecordAlert(alert, { id: 'log-2', exercise_id: 'ex-1', session_id: 'sess-2', is_personal_record: true }), true);
  assert.equal(shouldClearPersonalRecordAlert(alert, { id: 'log-1', exercise_id: 'ex-1', session_id: 'sess-2', is_personal_record: false }), false);
  assert.equal(
    shouldClearPersonalRecordAlert(
      { exerciseId: 'ex-1', sessionId: 'sess-2', dayName: 'Día 1' },
      { id: 'log-2', exercise_id: 'ex-1', session_id: 'sess-2', is_personal_record: true },
    ),
    true,
  );
});

test('AUD-08: formatPersonalRecordMark and formatPersonalRecordPreviousMark format same-weight rep PRs and bodyweight PRs', () => {
  assert.equal(formatPersonalRecordMark(60, '10'), '60 kg × 10');
  assert.equal(
    formatPersonalRecordPreviousMark({ weightKg: 60, previousWeightKg: 60, previousReps: 8 }),
    '60 kg × 8',
  );
  assert.equal(formatPersonalRecordMark(0, '12'), '12 reps (sin carga)');
  assert.equal(
    formatPersonalRecordPreviousMark({ weightKg: 0, previousWeightKg: 0, previousReps: 8 }),
    '8 reps sin carga',
  );
  assert.equal(
    formatPersonalRecordPreviousMark({ weightKg: 65, previousWeightKg: 60, previousReps: 8 }),
    '60 kg × 8',
  );
});
