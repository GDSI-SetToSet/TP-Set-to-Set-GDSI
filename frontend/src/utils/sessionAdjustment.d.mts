import type { AdjustmentBlock, AdjustmentInput, AdjustmentView, StudentAdjustmentNotice } from '../types/sessionAdjustment';

export const ADJUSTED_LABEL: string;
export function painIntensityLabel(intensity: string): string;
export function countChanges(original: AdjustmentBlock[], edited: AdjustmentBlock[]): number;
export function toAdjustmentInput(blocks: AdjustmentBlock[], note: string | null | undefined): AdjustmentInput;
export function entryError(errors: { field: string; message: string }[], blockIndex: number, exerciseIndex: number, dayIndex?: number): string | undefined;
export function adjustmentStatusMessage(adjustment: AdjustmentView | null | undefined): string | null;
export function noticeForDay(notices: StudentAdjustmentNotice[], dayName: string | undefined): StudentAdjustmentNotice | null;
export function isAdjustedExercise(notice: StudentAdjustmentNotice | null | undefined, exerciseId: string): boolean;
export function resolveInitialSetDraft(
  item: { reps: string; target_weight_kg: number | null },
  previousLog: { reps_completed: string; weight_kg: number | null } | null | undefined,
  options?: { isAdjusted?: boolean; isHomeModality?: boolean; nextSet?: number },
): { setNumber: string; repsCompleted: string; weightKg: string };
