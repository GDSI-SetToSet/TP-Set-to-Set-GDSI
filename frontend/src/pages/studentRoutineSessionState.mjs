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
