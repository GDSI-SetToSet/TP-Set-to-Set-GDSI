export type SafetyAlertType = 'PAIN' | 'REPEATED_DISCOMFORT' | 'EXCESSIVE_EFFORT';
export type SafetyAlertStatus = 'PENDING' | 'REVIEWED';
export type SafetyAlertAction = 'ADJUSTED_ROUTINE' | 'CONTACTED_STUDENT' | 'NO_ACTION';

export interface SafetyAlertReviewRequest {
  action_taken: SafetyAlertAction;
  trainer_note?: string | null;
}

export interface SafetyAlertView {
  id: string;
  relationship_id: string;
  student_id: string;
  student_name: string;
  session_id: string | null;
  session_day_name: string | null;
  report_id: string | null;
  exercise_id: string | null;
  exercise_name: string | null;
  alert_type: SafetyAlertType;
  zone: string | null;
  zone_display_name: string | null;
  rpe: number | null;
  status: SafetyAlertStatus;
  action_taken: SafetyAlertAction | null;
  trainer_note: string | null;
  created_at: string;
  reviewed_at: string | null;
  student_seen_at: string | null;
}

export interface StudentPainAlertReviewedNotice {
  id: string;
  session_id: string | null;
  session_day_name: string | null;
  exercise_name: string | null;
  zone: string | null;
  zone_display_name: string | null;
  action_taken: SafetyAlertAction;
  trainer_note: string | null;
  reviewed_at: string;
}
