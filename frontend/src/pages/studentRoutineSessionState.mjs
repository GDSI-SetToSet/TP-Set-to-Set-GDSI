/**
 * @param {string | null} value
 * @returns {number | null}
 */
export function parseSessionTimestamp(value) {
  if (!value) return null;
  const numeric = Number(value);
  if (Number.isFinite(numeric) && numeric > 0) return numeric;
  const timestamp = /(?:Z|[+-]\d{2}:\d{2})$/i.test(value) ? value : `${value}Z`;
  const parsed = Date.parse(timestamp);
  return Number.isFinite(parsed) ? parsed : null;
}

/**
 * @param {number} now
 * @param {number | null} startedAtMs
 * @returns {number}
 */
export function elapsedSessionSeconds(now, startedAtMs) {
  return startedAtMs === null ? 0 : Math.max(0, Math.floor((now - startedAtMs) / 1000));
}

/**
 * @param {boolean} sessionMode
 * @param {string | null} sessionId
 * @param {string | null} searchStartedAt
 * @param {string | null} storedStartedAt
 * @param {{ sessionId: string | null, startedAtMs: number | null }} current
 * @returns {{ sessionId: string | null, startedAtMs: number | null }}
 */
export function resolveSessionTimerState(sessionMode, sessionId, searchStartedAt, storedStartedAt, current) {
  if (!sessionMode || !sessionId) return { sessionId: null, startedAtMs: null };

  const startedAtMs = parseSessionTimestamp(searchStartedAt)
    ?? (current.sessionId === sessionId ? current.startedAtMs : null)
    ?? parseSessionTimestamp(storedStartedAt);

  return { sessionId, startedAtMs };
}

/**
 * @param {{ sessionId: string | null, dayName: string } | null} alert
 * @param {{ sessionMode: boolean, sessionId: string | null, dayName: string | undefined }} context
 * @returns {boolean}
 */
export function shouldShowPersonalRecordAlert(alert, context) {
  if (!alert || alert.dayName !== context.dayName) return false;
  if (alert.sessionId) return context.sessionMode && alert.sessionId === context.sessionId;
  return !context.sessionMode;
}

/**
 * Resolves the effective exercise ID and display name for a routine item,
 * honoring any temporary in-session replacement (US-54 / US-62).
 *
 * @param {{ id: string, exercise: { id: string, name: string } }} item
 * @param {Record<string, { exercise_id: string, name: string } | undefined>} replacements
 * @returns {{ id: string, name: string }}
 */
export function resolveEffectiveExercise(item, replacements) {
  const replacement = replacements?.[item.id];
  return {
    id: replacement?.exercise_id ?? item.exercise.id,
    name: replacement?.name ?? item.exercise.name,
  };
}

/**
 * Computes fail-closed subscription access state on the routines page (AUD-01 / AUD-02).
 *
 * @param {{ routineStatusCode: number | null, subscription: { status: string } | null, subscriptionError: boolean }} input
 * @returns {'OK' | 'EXPIRED' | 'UNVERIFIED'}
 */
export function resolveRoutineAccessState({ routineStatusCode, subscription, subscriptionError }) {
  if (routineStatusCode === 409 || subscription?.status === 'VENCIDA') return 'EXPIRED';
  if (subscriptionError) return 'UNVERIFIED';
  return 'OK';
}

/**
 * Determines whether "Iniciar serie" can be shown/triggered fail-closed (AUD-06).
 *
 * @param {{
 *   sessionMode: boolean,
 *   notesLoaded: boolean,
 *   notesError: boolean,
 *   pendingNotesCount: number,
 *   blocked: boolean,
 *   activeSet: unknown,
 *   finishedSet: unknown,
 *   activeRest: unknown,
 * }} state
 * @returns {boolean}
 */
export function canStartExerciseSet(state) {
  return Boolean(
    state.sessionMode
    && state.notesLoaded
    && !state.notesError
    && state.pendingNotesCount === 0
    && !state.blocked
    && !state.activeSet
    && !state.finishedSet
    && !state.activeRest,
  );
}

/**
 * Returns whether an active PR banner/celebration should be cleared when deleting a set log (AUD-08).
 *
 * @param {{ logId?: string, exerciseId?: string, sessionId: string | null } | null} alert
 * @param {{ id: string, exercise_id: string, session_id: string | null, is_personal_record?: boolean }} deletedLog
 * @returns {boolean}
 */
export function shouldClearPersonalRecordAlert(alert, deletedLog) {
  if (!alert) return false;
  if (alert.logId) return alert.logId === deletedLog.id;
  return Boolean(
    deletedLog.is_personal_record
    && alert.exerciseId === deletedLog.exercise_id
    && alert.sessionId === deletedLog.session_id,
  );
}

/**
 * Picks the routine ID used to display read-only workout summaries even when GET /assigned returns 409 (AUD-02).
 *
 * @param {{ id: string } | null} routine
 * @param {Array<{ routine_id?: string | null, finished_at?: string | null }>} workoutSessions
 * @param {Array<{ routine_id?: string | null }>} workoutLogs
 * @returns {string | null}
 */
export function resolveWorkoutHistoryRoutineId(routine, workoutSessions, workoutLogs) {
  if (routine?.id) return routine.id;
  const sessionRoutineId = workoutSessions?.find((session) => Boolean(session.finished_at) && Boolean(session.routine_id))?.routine_id;
  if (sessionRoutineId) return sessionRoutineId;
  return workoutLogs?.find((log) => Boolean(log.routine_id))?.routine_id ?? null;
}
