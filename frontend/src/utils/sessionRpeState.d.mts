import type { WorkoutSession, WorkoutSessionSummary } from '../types/routineTemplate';

export const RPE_UNREPORTED_LABEL: string;
export function shouldPromptForRpe(summary: Pick<WorkoutSessionSummary, 'rpe'> | null | undefined): boolean;
export function syncSessionAfterRpe<T extends Pick<WorkoutSession, 'id'>>(
  sessions: T[],
  updatedSession: T | null | undefined,
): T[];
export function findPendingRpeSession<T extends Pick<WorkoutSession, 'id' | 'finished_at' | 'rpe'>>(
  sessions: T[],
  activeSessionId: string | null | undefined,
): T | null;
export function sessionRpeStatusLabel(
  session: Pick<WorkoutSession, 'finished_at' | 'rpe'> | null | undefined,
): string;
