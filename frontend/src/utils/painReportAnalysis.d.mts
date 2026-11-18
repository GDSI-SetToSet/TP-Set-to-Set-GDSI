import type { BodyMapZoneHistoryItem, IntensityLevel, ReportContext } from '../types/bodyMapReport';

export type PainGrouping = 'zone' | 'muscle_group' | 'exercise' | 'routine_day';

export interface PainGroup {
  label: string;
  discomfort: number;
  pain: number;
  total: number;
}

export interface PainReportSummary {
  report_id: string;
  created_at: string;
  context: ReportContext;
  exercise_name: string | null;
  exercise_muscle_group: string | null;
  session_day_name: string | null;
  zones: { zone: string; zone_display: string; intensity: IntensityLevel }[];
}

export const PAIN_GROUPINGS: Record<PainGrouping, string>;
export function painOnly<T extends Pick<BodyMapZoneHistoryItem, 'intensity'>>(items: T[]): T[];
export function aggregatePain(items: BodyMapZoneHistoryItem[], grouping?: PainGrouping): PainGroup[];
export function groupByReport(items: BodyMapZoneHistoryItem[]): PainReportSummary[];
