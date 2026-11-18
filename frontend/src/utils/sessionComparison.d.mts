import type { ExerciseComparison, PerformedMetrics } from '../types/trainerStudent';

export type DeltaTone = 'up' | 'down' | 'same';
export type DurationDeltaTone = 'neutral';
export type ComparisonExerciseKind = 'planned' | 'replaced' | 'unplanned' | 'replaced_from_previous' | 'previous_only';
export function formatDelta(current: number | null | undefined, reference: number | null | undefined, unit?: string): string | null;
export function deltaTone(current: number | null | undefined, reference: number | null | undefined): DeltaTone | null;
export function durationDeltaTone(currentSeconds: number | null | undefined, referenceSeconds: number | null | undefined): DurationDeltaTone | null;
export function setsCompliance(exercise: Pick<ExerciseComparison, 'planned' | 'performed'> | null | undefined): string | null;
export function formatReps(metrics: Pick<PerformedMetrics, 'reps'> | null | undefined): string;
export function formatKg(value: number | null | undefined): string;
export function formatDurationDelta(currentSeconds: number | null | undefined, referenceSeconds: number | null | undefined): string | null;
export function classifyComparisonExercise(
  exercise: ExerciseComparison | null | undefined,
  allExercises?: ExerciseComparison[],
): ComparisonExerciseKind;
export function exerciseNoteLabel(
  exercise: ExerciseComparison | null | undefined,
  allExercises?: ExerciseComparison[],
): string | null;
