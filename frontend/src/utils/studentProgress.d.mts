import type { ConsistencyWeek, ExerciseEvolution, RecordEntry, SetResult, StudentProgress } from '../types/studentProgress';

export const PERIOD_LABELS: Record<'4w' | '12w' | 'all', string>;
export const PROGRESS_HELP: string;
export function weeksText(n: number): string;
export function kg(value: number): string;
export function formatMark(set: SetResult | null | undefined): string;
export function exercisePhrase(exercise: ExerciseEvolution): string;
export function sortExercises(list: ExerciseEvolution[]): ExerciseEvolution[];
export function consistencyLine(weeks: ConsistencyWeek[]): string | null;
export function isWeekDone(week: ConsistencyWeek): boolean;
export function currentWeekLabel(week: ConsistencyWeek): string;
export function summaryCards(summary: StudentProgress['summary']): { id: string; title: string; text: string }[];
export function recordLine(record: RecordEntry): string;
export function markToBeat(exercises: ExerciseEvolution[]): { name: string; mark: string } | null;
