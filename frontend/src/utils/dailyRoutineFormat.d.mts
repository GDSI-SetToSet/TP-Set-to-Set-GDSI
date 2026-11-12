import type { DailyRoutineItem, DailyRoutineStatus } from '../types/trainerStudent';

export const DAILY_STATUS_LABELS: Record<DailyRoutineStatus, string>;
export function localDateInputValue(date?: Date): string;
export function formatDuration(seconds: number | null | undefined): string;
export function formatWeight(weight: number | null | undefined): string;
export function sortDailyRoutines<T extends Pick<DailyRoutineItem, 'status' | 'student_name'>>(items: T[]): T[];
export function countByStatus(items: Pick<DailyRoutineItem, 'status'>[]): Record<DailyRoutineStatus, number>;
export function totalSets(item: Pick<DailyRoutineItem, 'exercises'>): number;
