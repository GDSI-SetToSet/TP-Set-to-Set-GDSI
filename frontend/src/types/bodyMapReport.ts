export type IntensityLevel = 'NORMAL' | 'DISCOMFORT' | 'PAIN';

export type ReportContext = 'POST_SESSION' | 'IN_EXERCISE';

export type ActionTaken = 'NONE' | 'VARIANT_OFFERED' | 'VARIANT_ACCEPTED' | 'EXERCISE_SKIPPED';

export interface ReportZoneInput {
  zone: string;
  intensity: IntensityLevel;
}

export interface ReportZoneOutput {
  id: string;
  zone: string;
  zone_display: string;
  intensity: IntensityLevel;
  created_at: string;
}

export interface SafeVariantSnippet {
  exercise_id: string;
  name: string;
  description: string | null;
  video_url: string | null;
  video_platform: string | null;
}

export interface SafeVariantEvaluation {
  status: 'SAFE' | 'VARIANT' | 'BLOCKED';
  variant: SafeVariantSnippet | null;
  message: string | null;
  can_skip: boolean;
}

export interface BodyMapReportCreate {
  session_id?: string | null;
  exercise_id?: string | null;
  context: ReportContext;
  action_taken?: ActionTaken | null;
  idempotency_key?: string | null;
  zones: ReportZoneInput[];
}

export interface BodyMapReportResponse {
  id: string;
  student_id: string;
  session_id: string | null;
  exercise_id: string | null;
  exercise_name: string | null;
  context: ReportContext;
  action_taken: ActionTaken | null;
  created_at: string;
  zones: ReportZoneOutput[];
  safe_variant?: SafeVariantEvaluation | null;
}

export interface BodyMapZoneHistoryItem {
  id: string;
  report_id: string;
  zone: string;
  zone_display: string;
  intensity: IntensityLevel;
  created_at: string;
  session_id: string | null;
  session_day_name: string | null;
  exercise_id: string | null;
  exercise_name: string | null;
  exercise_muscle_group?: string | null;
  context: ReportContext;
  action_taken: ActionTaken | null;
}
