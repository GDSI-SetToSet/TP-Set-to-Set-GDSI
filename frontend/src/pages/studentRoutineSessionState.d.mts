export interface SessionTimerState {
  sessionId: string | null;
  startedAtMs: number | null;
}

export interface PersonalRecordAlertContext {
  logId?: string;
  exerciseId?: string;
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
export function resolveEffectiveExercise(
  item: { id: string; exercise: { id: string; name: string } },
  replacements: Record<string, { exercise_id: string; name: string } | undefined>,
): { id: string; name: string };
export function resolveRoutineAccessState(input: {
  routineStatusCode: number | null;
  subscription: { status: string } | null;
  subscriptionError: boolean;
}): 'OK' | 'EXPIRED' | 'UNVERIFIED';
export function canStartExerciseSet(state: {
  sessionMode: boolean;
  notesLoaded: boolean;
  notesError: boolean;
  pendingNotesCount: number;
  blocked: boolean;
  activeSet: unknown;
  finishedSet: unknown;
  activeRest: unknown;
}): boolean;
export function shouldClearPersonalRecordAlert(
  alert: PersonalRecordAlertContext | null,
  deletedLog: { id: string; exercise_id: string; session_id: string | null; is_personal_record?: boolean },
): boolean;
export function resolveWorkoutHistoryRoutineId(
  routine: { id: string } | null,
  workoutSessions: Array<{ routine_id?: string | null; finished_at?: string | null }>,
  workoutLogs: Array<{ routine_id?: string | null }>,
): string | null;
