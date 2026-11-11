import assert from 'node:assert/strict';
import test from 'node:test';
import {
  elapsedSessionSeconds,
  parseSessionTimestamp,
  resolveSessionTimerState,
  shouldShowPersonalRecordAlert,
} from './studentRoutineSessionState.mjs';

test('each new session starts its timer from its own server timestamp', () => {
  const dayOne = resolveSessionTimerState(true, 'session-day-1', '1000', null, {
    sessionId: null,
    startedAtMs: null,
  });
  const dayTwo = resolveSessionTimerState(true, 'session-day-2', '2000', null, dayOne);

  assert.equal(dayOne.startedAtMs, 1000);
  assert.deepEqual(dayTwo, { sessionId: 'session-day-2', startedAtMs: 2000 });
});

test('reload restores an active session from its URL or its session-keyed storage value', () => {
  const current = { sessionId: null, startedAtMs: null };
  assert.deepEqual(
    resolveSessionTimerState(true, 'session-day-2', '2026-11-10T12:00:00Z', null, current),
    { sessionId: 'session-day-2', startedAtMs: Date.parse('2026-11-10T12:00:00Z') },
  );
  assert.deepEqual(
    resolveSessionTimerState(true, 'session-day-2', null, '2000', current),
    { sessionId: 'session-day-2', startedAtMs: 2000 },
  );
});

test('a new session never inherits a prior session timestamp', () => {
  assert.deepEqual(
    resolveSessionTimerState(true, 'session-day-2', null, null, {
      sessionId: 'session-day-1',
      startedAtMs: 1000,
    }),
    { sessionId: 'session-day-2', startedAtMs: null },
  );
});

test('backend timestamps without an explicit timezone are parsed as UTC', () => {
  assert.equal(
    parseSessionTimestamp('2026-11-10T12:00:00'),
    Date.parse('2026-11-10T12:00:00Z'),
  );
});

test('elapsed time starts at zero and advances from the active session start', () => {
  assert.equal(elapsedSessionSeconds(2000, 2000), 0);
  assert.equal(elapsedSessionSeconds(7000, 2000), 5);
});

test('a PR alert appears only in its originating session and day', () => {
  const alert = { sessionId: 'session-day-1', dayName: 'Día 1 - Fuerza' };
  const dayTwoAlert = { sessionId: 'session-day-2', dayName: 'Día 2 - Cardio' };

  assert.equal(shouldShowPersonalRecordAlert(alert, {
    sessionMode: true,
    sessionId: 'session-day-1',
    dayName: 'Día 1 - Fuerza',
  }), true);
  assert.equal(shouldShowPersonalRecordAlert(alert, {
    sessionMode: true,
    sessionId: 'session-day-2',
    dayName: 'Día 2 - Cardio',
  }), false);
  assert.equal(shouldShowPersonalRecordAlert(alert, {
    sessionMode: false,
    sessionId: null,
    dayName: 'Día 2 - Cardio',
  }), false);
  assert.equal(shouldShowPersonalRecordAlert(alert, {
    sessionMode: true,
    sessionId: 'session-day-1',
    dayName: 'Día 2 - Cardio',
  }), false);
  assert.equal(shouldShowPersonalRecordAlert(dayTwoAlert, {
    sessionMode: true,
    sessionId: 'session-day-2',
    dayName: 'Día 2 - Cardio',
  }), true);
});
