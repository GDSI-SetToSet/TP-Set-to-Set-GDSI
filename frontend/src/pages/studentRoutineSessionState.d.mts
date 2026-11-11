export interface SessionTimerState {
  sessionId: string | null;
  startedAtMs: number | null;
}

export interface PersonalRecordAlertContext {
  sessionId: string | null;
  dayName: string;
}

export function parseSessionTimestamp(value: string | null): number | null;
export function elapsedSessionSeconds(now: number, startedAtMs: number | null): number;
export function resolveSessionTimerState(
  sessionMode: boolean,
  sessionId: string | null,
  searchStartedAt: string | null,
  storedStartedAt: string | null,
  current: SessionTimerState,
): SessionTimerState;
export function shouldShowPersonalRecordAlert(
  alert: PersonalRecordAlertContext | null,
  context: { sessionMode: boolean; sessionId: string | null; dayName: string | undefined },
): boolean;
