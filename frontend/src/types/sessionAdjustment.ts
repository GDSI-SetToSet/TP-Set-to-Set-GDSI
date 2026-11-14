/** US-26: ajuste de la próxima sesión a partir de la sesión finalizada del alumno. */

export interface AdjustmentEntry {
  exercise_id: string;
  exercise_name: string;
  sets: number;
  reps: string;
  rest_seconds: number;
  target_weight_kg: number | null;
}

export interface AdjustmentBlock {
  name: string;
  estimated_duration_minutes: number | null;
  exercises: AdjustmentEntry[];
}

export interface AdjustmentView {
  id: string;
  status: 'PENDING' | 'APPLIED';
  note: string | null;
  changed_exercise_ids: string[];
  created_at: string;
  applied_at: string | null;
}

export interface SessionAdjustmentContext {
  session_id: string;
  day_name: string;
  started_at: string;
  finished_at: string | null;
  rpe: number | null;
  logged_exercises: {
    exercise_id: string;
    exercise_name: string;
    sets: { set_number: number; reps_completed: string; weight_kg: number | null }[];
  }[];
  pain_zones: {
    zone: string;
    zone_label: string;
    intensity: 'DISCOMFORT' | 'PAIN';
    exercise_name: string | null;
    context: string;
  }[];
  replacement_requests: {
    original_exercise_id: string;
    original_exercise_name: string;
    replacement_exercise_name: string | null;
  }[];
  blocks: AdjustmentBlock[];
  can_adjust: boolean;
  blocked_reason: string | null;
  current_adjustment: AdjustmentView | null;
}

export interface AdjustmentInput {
  note: string | null;
  blocks: {
    name: string;
    estimated_duration_minutes: number | null;
    exercises: Omit<AdjustmentEntry, 'exercise_name'>[];
  }[];
}

export interface StudentAdjustmentNotice {
  day_name: string;
  note: string | null;
  exercise_ids: string[];
  adjusted_at: string;
}
