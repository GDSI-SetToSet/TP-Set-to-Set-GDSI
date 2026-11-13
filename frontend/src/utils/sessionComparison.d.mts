import type { ExerciseComparison, PerformedMetrics } from '../types/trainerStudent';

export type DeltaTone = 'up' | 'down' | 'same';
export function formatDelta(current: number | null | undefined, reference: number | null | undefined, unit?: string): string | null;
export function deltaTone(current: number | null | undefined, reference: number | null | undefined): DeltaTone | null;
export function setsCompliance(exercise: Pick<ExerciseComparison, 'planned' | 'performed'> | null | undefined): string | null;
export function formatReps(metrics: Pick<PerformedMetrics, 'reps'> | null | undefined): string;
export function formatKg(value: number | null | undefined): string;
